# DGW data and tools

Build and release definitions for
[Digital Genome Workstation](https://github.com/mrueda/digital-genome-workstation).

DGW uses two kinds of external package:

- an assembly package with the reference FASTA, ClinVar, Ensembl genes and the
  transcript model used for consequence prediction;
- a platform package with `bcftools`, `bgzip` and `tabix`.

Users import their own VCF into DGW. They do not have to find or configure these
supporting resources individually.

## Current scope

- Genome assemblies: b37 and hg38
- Platforms: Linux ARM64/x86-64, macOS Apple Silicon/Intel, Windows x86-64
- Tools: bcftools/HTSlib 1.24, package revision 2
- Public databases: ClinVar and Ensembl
- User-supplied database: COSMIC
- Deliberately excluded: dbNSFP

Large genomes and databases are not stored in Git or Git LFS. This repository
contains their pinned identities, packaging code, native build workflows and tests.
The resulting archives are published as release assets only after review.

## Repository map

- `sources.json`: pinned source-code releases and checksums
- `data-packages.json`: pinned genome-resource inputs and provenance
- `scripts/build.sh`: native tool build entry point
- `scripts/package_data.py`: assembly package builder and verifier
- `scripts/release_index.py`: verified application-catalog generator
- `.github/workflows/`: manually triggered native builds and tests
- [`BUILDING.md`](BUILDING.md): local and CI build details
- [`VALIDATION.md`](VALIDATION.md): what has been tested
- [`RELEASING.md`](RELEASING.md): owner-run publication procedure
- [`LICENSES.md`](LICENSES.md): repository and packaged-resource license boundary

No workflow publishes on push. Automatic installation in DGW remains disabled
until reviewed public release URLs are added to its catalog. Users can already
install verified archives downloaded separately through Settings → Resources.

Author: Manuel Rueda

Repository code is licensed under Apache-2.0. Packaged tools and datasets
retain their own licenses; every archive includes a manifest and applicable notices.
