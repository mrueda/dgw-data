# Licenses and data terms

The root [`LICENSE`](LICENSE) applies to code authored for this repository,
including build scripts, tests, workflows and catalog tooling. That code is
Apache-2.0.

It does **not** relicense third-party software, genome assemblies, annotations or
database records placed in a DGW release archive. Each package contains an exact
manifest and notices for its contents. Source identities and checksums are also
pinned in `sources.json` and `data-packages.json`.

## Platform-tool archives

The packages contain bcftools/HTSlib, zlib and libdeflate. Their upstream license
files are copied into each archive and remain controlling for those components.
DGW's build configuration does not change those upstream licenses.

## Assembly-data archives

The current packages contain material from these sources:

- **1000 Genomes/IGSR hs37d5:** consult the
  [IGSR data disclaimer](https://www.internationalgenome.org/IGSR_disclaimer/)
  and cite the applicable project publications.
- **UCSC-hosted GRCh38 sequence:** consult the
  [UCSC Genome Browser Conditions of Use](https://genome.ucsc.edu/conditions.html)
  and the assembly/data-provider credits referenced there.
- **Ensembl GTF and GFF3:** consult the
  [Ensembl legal and data disclaimer](https://www.ensembl.org/info/about/legal/disclaimer.html).
- **ClinVar:** consult NCBI's
  [ClinVar disclaimer and data-use policy](https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/),
  including its requested attribution and medical-use disclaimer.

The SQLite gene index is derived from the packaged Ensembl GTF and is distributed
under the same applicable source-data terms. BGZF repacking and index generation do
not change the terms governing the underlying sequence or records.

COSMIC is not distributed. A user who configures it is responsible for complying
with their COSMIC license. dbNSFP is not used or packaged.

## Release rule

Before publishing a new archive, review its embedded manifest and notices against
the current upstream pages. A successful package build proves file identity and
integrity; it is not a legal determination that redistribution is permitted.
