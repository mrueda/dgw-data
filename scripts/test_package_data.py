import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'package_data.py'


class DataPackageTest(unittest.TestCase):
    def test_builds_and_verifies_without_persisting_host_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def write(name, data=b'data'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                return str(path)
            bundle = {
                'schemaVersion': 1, 'id': 'test', 'assembly': 'b37',
                'contigStyle': 'no_chr_prefix',
                'referencePath': write('source/ref.gz'),
                'referenceFaiPath': write('source/ref.gz.fai'),
                'referenceGziPath': write('source/ref.gz.gzi'),
                'clinvar': {'path': write('source/clinvar.gz'),
                            'indexPath': write('source/clinvar.gz.tbi'),
                            'release': 'test', 'sourceUrl': 'https://example.org/clinvar',
                            'licenseLabel': 'test terms'},
                'geneAnnotation': {'path': write('source/genes.gz'),
                                   'indexPath': '',
                                   'assembly': 'GRCh37', 'contigStyle': 'no_chr_prefix',
                                   'release': 'test', 'sourceUrl': 'https://example.org/genes',
                                   'licenseLabel': 'test terms'},
                'consequenceAnnotation': {'path': write('source/effects.gz'),
                                          'release': 'test', 'sourceUrl': 'https://example.org/effects',
                                          'licenseLabel': 'test terms'},
            }
            gene_data = Path(bundle['geneAnnotation']['path']).read_bytes()
            index_path = root / 'source/genes.sqlite'
            connection = sqlite3.connect(index_path)
            connection.execute('create table metadata (singleton integer primary key, payload text)')
            connection.execute('insert into metadata values (1, ?)', (json.dumps({
                'sourceSha256': hashlib.sha256(gene_data).hexdigest(),
                'sourceSize': len(gene_data), 'assembly': 'GRCh37',
                'contigStyle': 'no_chr_prefix'}),))
            connection.commit(); connection.close()
            bundle['geneAnnotation']['indexPath'] = str(index_path)
            descriptor = root / 'bundle.json'
            descriptor.write_text(json.dumps(bundle))
            roles = {
                'reference': bundle['referencePath'],
                'reference-index': bundle['referenceFaiPath'],
                'reference-bgzf-index': bundle['referenceGziPath'],
                'clinvar': bundle['clinvar']['path'],
                'clinvar-index': bundle['clinvar']['indexPath'],
                'genes': bundle['geneAnnotation']['path'],
                'gene-index': bundle['geneAnnotation']['indexPath'],
                'consequences': bundle['consequenceAnnotation']['path'],
            }
            files = {}
            for role, path in roles.items():
                data = Path(path).read_bytes()
                files[role] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                               'sourceUrl': 'https://example.org/source', 'release': 'test',
                               'licenseLabel': 'test terms'}
            specs = root / 'specs.json'
            specs.write_text(json.dumps({'schemaVersion': 1, 'packages': {
                'b37': {'revision': 'r1', 'contigStyle': 'no_chr_prefix', 'files': files}}}))
            output = root / 'dist'
            subprocess.run([sys.executable, SCRIPT, 'build', '--bundle', descriptor,
                            '--output', output, '--specs', specs],
                           check=True, capture_output=True, text=True)
            archive = output / 'dgw-data-b37-r1.tar.gz'
            subprocess.run([sys.executable, SCRIPT, 'verify', archive], check=True)
            self.assertTrue(archive.with_suffix('.gz.sha256').is_file())
            with gzip.open(archive, 'rb') as packed:
                self.assertNotIn(str(root).encode(), packed.read())
            specs_data = json.loads(specs.read_text())
            specs_data['packages']['b37']['files']['reference']['sha256'] = '0' * 64
            specs.write_text(json.dumps(specs_data))
            failed = subprocess.run([sys.executable, SCRIPT, 'build', '--bundle', descriptor,
                                     '--output', root / 'bad', '--specs', specs],
                                    capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('Pinned input mismatch for reference', failed.stderr)


if __name__ == '__main__':
    unittest.main()
