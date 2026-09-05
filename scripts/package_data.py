"""Build and verify assembly data archives from an existing DGW resource descriptor."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tarfile

MAX_FILES = 32
CHUNK = 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_source(path):
    path = path.resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Expected a regular source file: {path}')
    return path


def inputs(bundle):
    required = [
        ('reference', 'reference/genome.fa.gz', bundle['referencePath']),
        ('reference-index', 'reference/genome.fa.gz.fai', bundle['referenceFaiPath']),
        ('reference-bgzf-index', 'reference/genome.fa.gz.gzi', bundle['referenceGziPath']),
        ('clinvar', 'evidence/clinvar.vcf.gz', bundle['clinvar']['path']),
        ('clinvar-index', 'evidence/clinvar.vcf.gz.tbi', bundle['clinvar']['indexPath']),
    ]
    gene = bundle.get('geneAnnotation')
    consequence = bundle.get('consequenceAnnotation')
    if not gene or not consequence:
        raise ValueError('Gene and consequence annotations are required for a DGW data package')
    required.extend([
        ('genes', 'genes/genes.gtf.gz', gene['path']),
        ('gene-index', 'genes/genes.sqlite', gene['indexPath']),
        ('consequences', 'consequence/transcripts.gff3.gz', consequence['path']),
    ])
    return required


def archive_member(output, source, name):
    info = output.gettarinfo(str(source), arcname=name)
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    info.mtime = 0
    info.mode = 0o644
    with source.open('rb') as stream:
        output.addfile(info, stream)


def validate_gene_index(bundle, sources):
    source = next(item for item in sources if item['role'] == 'genes')
    index = next(item for item in sources if item['role'] == 'gene-index')['source']
    wal = Path(str(index) + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError(f'Gene index has uncheckpointed WAL data: {wal}')
    connection = sqlite3.connect(f'file:{index}?mode=ro', uri=True)
    try:
        if connection.execute('pragma integrity_check').fetchone()[0] != 'ok':
            raise ValueError(f'Gene index integrity check failed: {index}')
        row = connection.execute('select payload from metadata where singleton = 1').fetchone()
        metadata = json.loads(row[0]) if row else None
    finally:
        connection.close()
    gene = bundle['geneAnnotation']
    if not metadata or metadata.get('sourceSha256') != source['sha256'] \
            or metadata.get('sourceSize') != source['bytes'] \
            or metadata.get('assembly') != gene['assembly'] \
            or metadata.get('contigStyle') != gene['contigStyle']:
        raise ValueError('Gene index metadata does not match its packaged GTF')


def byte_member(output, data, name):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    output.addfile(info, io.BytesIO(data))


def package(args):
    bundle = json.loads(args.bundle.read_text())
    if bundle.get('schemaVersion') != 1 or bundle.get('assembly') not in {'b37', 'hg38'}:
        raise ValueError('Expected a schema-v1 b37 or hg38 DGW bundle')
    specs = json.loads(args.specs.read_text())
    if specs.get('schemaVersion') != 1:
        raise ValueError('Unsupported data-package specification')
    spec = specs['packages'].get(bundle['assembly'])
    if not spec or spec['contigStyle'] != bundle['contigStyle']:
        raise ValueError('No matching package specification for this bundle')
    root_name = f"dgw-data-{bundle['assembly']}-{spec['revision']}"
    sources = []
    for role, target, raw in inputs(bundle):
        expected = spec['files'][role]
        source = checked_source(Path(raw))
        actual = {'bytes': source.stat().st_size, 'sha256': digest(source)}
        if actual != {key: expected[key] for key in ('bytes', 'sha256')}:
            raise ValueError(f'Pinned input mismatch for {role}: {source}')
        sources.append({'role': role, 'path': target, 'source': source, **expected})
    validate_gene_index(bundle, sources)
    manifest = {
        'schemaVersion': 1,
        'id': root_name,
        'assembly': bundle['assembly'],
        'contigStyle': bundle['contigStyle'],
        'packageSpecificationSha256': digest(args.specs),
        'files': [{key: value for key, value in item.items() if key != 'source'} for item in sources],
        'excluded': ['COSMIC (user-supplied; redistribution not permitted by this package)'],
    }
    notice = (
        'DGW assembly data package\n\n'
        'This archive contains third-party scientific data. Source URLs, releases and '
        'checksums are recorded in manifest.json. Cite and comply with each upstream '
        'provider. Clinical assertions are not medical advice. COSMIC is not included.\n'
    ).encode()
    manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / f'{root_name}.tar.gz'
    if archive.exists():
        raise ValueError(f'Refusing to replace existing archive: {archive}')
    temporary = archive.with_suffix('.partial')
    with (temporary.open('xb') as raw,
          gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=1, mtime=0) as compressed,
          tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as output):
        for item in sources:
            archive_member(output, item['source'], f"{root_name}/{item['path']}")
        byte_member(output, manifest_bytes, f'{root_name}/manifest.json')
        byte_member(output, notice, f'{root_name}/NOTICE.txt')
    temporary.rename(archive)
    checksum = digest(archive)
    archive.with_suffix(archive.suffix + '.sha256').write_text(f'{checksum}  {archive.name}\n')
    verify(archive)
    print(json.dumps({'archive': str(archive), 'sha256': checksum,
                      'bytes': archive.stat().st_size, 'unpackedBytes': sum(x['bytes'] for x in sources)}, indent=2))


def safe_member(name, root):
    path = Path(name)
    return (not path.is_absolute() and len(path.parts) > 1 and path.parts[0] == root
            and '\\' not in name and ':' not in name
            and all(part not in {'', '.', '..'} for part in path.parts))


def verify(archive):
    expected_root = archive.name.removesuffix('.tar.gz')
    seen = set()
    manifest = None
    observed = {}
    with tarfile.open(archive, 'r:gz') as packed:
        members = packed.getmembers()
        if len(members) > MAX_FILES:
            raise ValueError('Too many archive entries')
        for member in members:
            if (not member.isfile() or member.issym() or member.islnk()
                    or not safe_member(member.name, expected_root) or member.name in seen):
                raise ValueError(f'Unsafe archive entry: {member.name}')
            seen.add(member.name)
            stream = packed.extractfile(member)
            if member.name.endswith('/manifest.json'):
                manifest = json.load(stream)
            else:
                hasher = hashlib.sha256()
                while chunk := stream.read(CHUNK):
                    hasher.update(chunk)
                observed[member.name.removeprefix(expected_root + '/')] = (member.size, hasher.hexdigest())
    if not manifest or manifest.get('id') != expected_root:
        raise ValueError('Missing or mismatched data manifest')
    for item in manifest['files']:
        if observed.get(item['path']) != (item['bytes'], item['sha256']):
            raise ValueError(f"Archive file mismatch: {item['path']}")
    expected = {item['path'] for item in manifest['files']} | {'NOTICE.txt'}
    if set(observed) != expected:
        raise ValueError('Archive contains unrecorded or missing files')
    print(f'Verified {archive}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--bundle', type=Path, required=True)
    build.add_argument('--output', type=Path, default=Path('dist'))
    build.add_argument('--specs', type=Path, default=ROOT / 'data-packages.json')
    check = sub.add_parser('verify')
    check.add_argument('archive', type=Path)
    args = parser.parse_args()
    if args.command == 'build': package(args)
    else: verify(args.archive)
