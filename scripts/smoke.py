"""Exercise the DGW command subset against synthetic data, without a genome bundle."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def smoke(bin_dir):
    suffix = '.exe' if os.name == 'nt' else ''
    tools = {name: str((Path(bin_dir) / (name + suffix)).resolve())
             for name in ('bcftools', 'bgzip', 'tabix')}
    def run(name, *args, **kwargs):
        return subprocess.run([tools[name], *map(str, args)], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout
    versions = {name: run(name, '--version').decode().splitlines()[0] for name in tools}
    if any('1.24' not in version for version in versions.values()):
        raise AssertionError(versions)
    with tempfile.TemporaryDirectory(prefix='dgw test space ') as temporary:
        root = Path(temporary)
        sequence = 'ATG' + 'GAA' * 8 + 'TAA'
        fasta = root / 'référence.fa'
        fasta.write_text('>1\n' + sequence + '\n', encoding='utf8')
        Path(str(fasta) + '.fai').write_text(f'1\t30\t3\t30\t31\n')
        vcf = root / 'input.vcf'
        vcf.write_text('##fileformat=VCFv4.2\n##contig=<ID=1,length=30>\n'
                      '##FILTER=<ID=q10,Description="Low quality">\n'
                      '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
                      '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n'
                      '1\t4\t.\tG\tA,T\t.\tPASS\t.\tGT\t1/2\n'
                      '1\t5\t.\tAA\tA\t.\tPASS\t.\tGT\t0/1\n'
                      '1\t7\t.\tG\tA\t.\tq10\t.\tGT\t0/1\n')
        passed = root / 'pass.vcf'
        run('bcftools', 'view', '-f', 'PASS', '-Ov', '-o', passed, vcf)
        norm = root / 'norm.vcf.gz'
        run('bcftools', 'norm', '-c', 'e', '-m', '-both', '-f', fasta, '-Oz', '-o', norm, passed)
        run('tabix', '-p', 'vcf', norm)
        rows = run('bcftools', 'query', '-f', '%POS\t%REF\t%ALT\n', norm).decode().splitlines()
        assert rows == ['4\tG\tA', '4\tG\tT', '4\tGA\tG'], rows
        assert len(run('tabix', norm, '1:4-4').decode().splitlines()) == 3
        run('bgzip', '-t', norm)
        assert run('bgzip', '-d', '-c', norm).startswith(b'##fileformat=VCFv4.2')
        annotation = root / 'genes.gff3'
        annotation.write_text('##gff-version 3\n'
            '1\tDGW\tgene\t1\t30\t.\t+\t.\tID=gene:DGW1;Name=DGW1;biotype=protein_coding\n'
            '1\tDGW\ttranscript\t1\t30\t.\t+\t.\tID=transcript:DGWT1;Parent=gene:DGW1;biotype=protein_coding\n'
            '1\tDGW\texon\t1\t30\t.\t+\t.\tParent=transcript:DGWT1\n'
            '1\tDGW\tCDS\t1\t30\t.\t+\t0\tParent=transcript:DGWT1\n')
        csq = root / 'effects.vcf'
        run('bcftools', 'csq', '--local-csq', '-f', fasta, '-g', annotation, '-Ov', '-o', csq, norm)
        effects = run('bcftools', 'query', '-f', '%ALT\t%BCSQ\n', csq).decode().splitlines()
        assert effects[0].startswith('A\tmissense|'), effects
        assert effects[1].startswith('T\tstop_gained|'), effects
        assert 'frameshift' in effects[2], effects
        # REF mismatch must fail, never silently "repair" the allele.
        wrong = root / 'wrong.vcf'
        wrong.write_text(passed.read_text().replace('1\t4\t.\tG\t', '1\t4\t.\tC\t'))
        try:
            run('bcftools', 'norm', '-c', 'e', '-f', fasta, wrong)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('REF mismatch was accepted')
        return {'versions': versions, 'normalizedAlleles': rows, 'consequences': effects,
                'checks': ['PASS filtering', 'multiallelic splitting', 'left alignment',
                           'tabix query', 'BGZF integrity', 'local csq', 'REF mismatch rejection',
                           'spaces and Unicode paths']}


if __name__ == '__main__':
    print(json.dumps(smoke(sys.argv[1]), indent=2))
