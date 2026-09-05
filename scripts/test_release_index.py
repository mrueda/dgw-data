import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('release_index.py')


class ReleaseIndexTest(unittest.TestCase):
    def test_indexes_verified_archive_and_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'tools' / 'dgw-tools-test.tar.gz'
            archive.parent.mkdir()
            manifest = json.dumps({'schemaVersion': 1, 'id': 'dgw-tools-test',
                                   'platform': 'linux-aarch64', 'files': [
                                       {'path': 'bin/tool', 'bytes': 1, 'sha256': '0' * 64}]}).encode()
            with archive.open('wb') as raw:
                with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
                    with tarfile.open(fileobj=compressed, mode='w|') as packed:
                        info = tarfile.TarInfo('dgw-tools-test/manifest.json')
                        info.size = len(manifest)
                        packed.addfile(info, io.BytesIO(manifest))
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            archive.with_suffix('.gz.sha256').write_text(f'{checksum}  {archive.name}\n')
            output = root / 'release-index.json'
            subprocess.run([sys.executable, SCRIPT, root, '--output', output,
                            '--base-url', 'https://example.org/releases'], check=True)
            item = json.loads(output.read_text())['artifacts'][0]
            self.assertEqual(item['sha256'], checksum)
            self.assertEqual(item['url'], 'https://example.org/releases/tools/dgw-tools-test.tar.gz')
            self.assertTrue(output.with_suffix('.json.sha256').is_file())


if __name__ == '__main__':
    unittest.main()
