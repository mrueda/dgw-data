"""Create a checksum-verified index for staged DGW release archives."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.parse import quote


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive_metadata(path, root, base_url=None):
    expected = path.with_suffix(path.suffix + '.sha256')
    if not expected.is_file():
        raise ValueError(f'Missing checksum sidecar: {path}')
    fields = expected.read_text().strip().split()
    if len(fields) != 2 or fields[1] != path.name or fields[0] != digest(path):
        raise ValueError(f'Archive checksum failed: {path}')
    manifest_bytes = None
    with tarfile.open(path, 'r:gz') as packed:
        for member in packed:
            if member.isfile() and member.name.endswith('/manifest.json'):
                if manifest_bytes is not None:
                    raise ValueError(f'Multiple manifests in {path}')
                manifest_bytes = packed.extractfile(member).read()
    if manifest_bytes is None:
        raise ValueError(f'Missing manifest in {path}')
    manifest = json.loads(manifest_bytes)
    if path.name != f"{manifest['id']}.tar.gz" or manifest.get('schemaVersion') != 1:
        raise ValueError(f'Archive and manifest identity differ: {path}')
    relative = path.relative_to(root).as_posix()
    artifact = {
        'id': manifest['id'],
        'kind': 'tools' if manifest.get('platform') else 'data',
        'file': relative,
        'bytes': path.stat().st_size,
        'sha256': fields[0],
        'manifestSha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'unpackedBytes': sum(item['bytes'] for item in manifest['files']),
    }
    for key in ('platform', 'assembly', 'contigStyle'):
        if key in manifest:
            artifact[key] = manifest[key]
    if base_url:
        artifact['url'] = base_url.rstrip('/') + '/' + '/'.join(quote(part) for part in relative.split('/'))
    return artifact


def main(args):
    root = args.directory.resolve()
    archives = sorted(root.rglob('*.tar.gz'))
    if not archives:
        raise ValueError(f'No release archives in {root}')
    artifacts = [archive_metadata(path, root, args.base_url) for path in archives]
    ids = [item['id'] for item in artifacts]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate package IDs')
    payload = {'schemaVersion': 1, 'artifacts': artifacts}
    data = (json.dumps(payload, indent=2) + '\n')
    args.output.write_text(data)
    args.output.with_suffix(args.output.suffix + '.sha256').write_text(
        f'{hashlib.sha256(data.encode()).hexdigest()}  {args.output.name}\n')
    print(f'Indexed {len(artifacts)} archives in {args.output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url')
    main(parser.parse_args())
