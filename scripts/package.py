"""Verified source downloads and relocatable, tested tool artifacts."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from smoke import smoke

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / 'sources.json').read_text())


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare():
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    for name, source in SOURCES.items():
        archive = work / source['url'].rsplit('/', 1)[1]
        if not archive.exists():
            partial = archive.with_suffix('.partial')
            with urllib.request.urlopen(source['url'], timeout=60) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output)
            if digest(partial) != source['sha256']:
                raise ValueError(f'Checksum mismatch: {name}')
            partial.rename(archive)
        if digest(archive) != source['sha256']:
            raise ValueError(f'Checksum mismatch: {archive}')
        destination = work / f"{name}-{source['version']}"
        if destination.exists():
            raise ValueError(f'Use a fresh work directory; source already exists: {destination}')
        with tarfile.open(archive) as source_tar:
            source_tar.extractall(work, filter='data')


def audit_runtime(binary, target):
    if target.startswith('linux-'):
        text = subprocess.check_output(['ldd', str(binary)], text=True)
        allowed = ('libc.so.', 'libm.so.', 'libpthread.so.', 'libdl.so.', 'librt.so.',
                   'linux-vdso', 'ld-linux')
        for line in text.splitlines():
            dependency = line.strip().split()[0]
            if not any(item in dependency for item in allowed) or 'not found' in line:
                raise ValueError(f'Unpackaged runtime dependency: {line}')
    elif target.startswith('darwin-'):
        text = subprocess.check_output(['otool', '-L', str(binary)], text=True)
        for line in text.splitlines()[1:]:
            if not line.strip().startswith(('/usr/lib/', '/System/Library/')):
                raise ValueError(f'Unpackaged runtime dependency: {line}')
    else:
        text = subprocess.check_output(['objdump', '-p', str(binary)], text=True)
        allowed = {'kernel32.dll', 'msvcrt.dll', 'ucrtbase.dll', 'advapi32.dll',
                   'ws2_32.dll', 'bcrypt.dll', 'user32.dll', 'shell32.dll', 'ntdll.dll'}
        for dependency in re.findall(r'DLL Name:\s*(\S+)', text):
            if dependency.lower() not in allowed and not dependency.lower().startswith('api-ms-win-'):
                raise ValueError(f'Unpackaged Windows DLL: {dependency}')
    return text


def package(target):
    system = {'Linux': 'linux', 'Darwin': 'darwin', 'Windows': 'windows'}[platform.system()]
    arch = {'arm64': 'aarch64', 'AMD64': 'x86_64'}.get(platform.machine(), platform.machine())
    if target != f'{system}-{arch}':
        raise ValueError(f'Native build expected {system}-{arch}, not {target}')
    name = f'dgw-tools-1.24-2-{target}'
    stage = ROOT / 'work' / name
    (stage / 'bin').mkdir(parents=True, exist_ok=False)
    (stage / 'licenses').mkdir()
    source = ROOT / 'work' / 'bcftools-1.24'
    suffix = '.exe' if system == 'windows' else ''
    runtime = {}
    for tool, directory in [('bcftools', source), ('bgzip', source / 'htslib-1.24'),
                            ('tabix', source / 'htslib-1.24')]:
        destination = stage / 'bin' / (tool + suffix)
        shutil.copy2(directory / (tool + suffix), destination)
        runtime[tool] = audit_runtime(destination, target)
    for label, path in [('bcftools', source / 'LICENSE'),
                        ('htslib', source / 'htslib-1.24' / 'LICENSE'),
                        ('htscodecs', source / 'htslib-1.24' / 'htscodecs' / 'LICENSE.md'),
                        ('zlib', ROOT / 'work' / 'zlib-1.3.2' / 'LICENSE'),
                        ('libdeflate', ROOT / 'work' / 'libdeflate-1.26' / 'COPYING')]:
        shutil.copy2(path, stage / 'licenses' / f'{label}.txt')
    if system == 'windows':
        # Include notices for the static regex/pthread/compiler runtime packages.
        license_root = Path(subprocess.check_output(
            ['cygpath', '-w', '/mingw64/share/licenses'], text=True).strip())
        shutil.copytree(license_root, stage / 'licenses' / 'mingw-runtime')
        (stage / 'build-packages.txt').write_text(subprocess.check_output(['pacman', '-Q'], text=True))
    (stage / 'sources.json').write_text(json.dumps(SOURCES, indent=2) + '\n')
    # Test outside the build tree. The package must not rely on its original path.
    with tempfile.TemporaryDirectory(prefix='dgw relocated package ') as temporary:
        relocated = Path(temporary) / name
        shutil.copytree(stage, relocated)
        report = smoke(relocated / 'bin')
    manifest = {'schemaVersion': 1, 'id': name, 'platform': target,
                'source': SOURCES, 'runtimeAudit': runtime, 'smokeTest': report,
                'buildHost': platform.platform(),
                'compiler': subprocess.check_output(['cc', '--version'], text=True).splitlines()[0],
                'buildConfig': {name: path.read_text() for name, path in [
                    ('bcftools', source / 'config.mk'),
                    ('htslib', source / 'htslib-1.24' / 'config.mk')]},
                'scope': 'Local VCF/BCF operations with static zlib and libdeflate; no remote HTSlib access, plugins or bz2/lzma CRAM',
                'files': [{'path': str(p.relative_to(stage)).replace('\\', '/'),
                           'sha256': digest(p), 'bytes': p.stat().st_size}
                          for p in sorted(stage.rglob('*')) if p.is_file()]}
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / (name + '.tar.gz')
    if archive.exists():
        raise ValueError(f'Artifact already exists: {archive}')
    with tarfile.open(archive, 'w:gz') as output:
        output.add(stage, arcname=name)
    with tempfile.TemporaryDirectory(prefix='dgw extracted package ') as temporary:
        with tarfile.open(archive) as packed:
            packed.extractall(temporary, filter='data')
        assert smoke(Path(temporary) / name / 'bin') == report
    archive.with_suffix(archive.suffix + '.sha256').write_text(f'{digest(archive)}  {archive.name}\n')
    print(json.dumps(report, indent=2))
    print(f'Created {archive}')


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']:
        prepare()
    elif len(sys.argv) == 3 and sys.argv[1] == 'package':
        package(sys.argv[2])
    else:
        raise SystemExit('Usage: package.py prepare | package PLATFORM')
