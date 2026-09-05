# Validation record

## Native tool packages

Tool package revision 2 passed all five native targets on 2026-09-05 in
[GitHub Actions run 33972192922](https://github.com/mrueda/dgw-data/actions/runs/33972192922):

- Linux ARM64 and x86-64
- macOS Apple Silicon and Intel
- Windows x86-64

Tests cover strict PASS filtering, multiallelic splitting, indel normalization,
REF mismatch rejection, BGZF, tabix queries, and independently evaluated missense,
stop-gained and frameshift consequences. Each test runs from a relocated directory
whose path contains spaces and non-ASCII characters. The test data is synthetic.
This is a targeted DGW smoke suite, not the full upstream bcftools suite.

The Linux ARM64 package was also tested against DGW's public exome fixture. Across
three repetitions it returned the same allele, genotype and consequence rows as the
development installation. Median consequence-prediction time was 5.43 seconds for
the package and 5.36 seconds for the development installation; normalization was
0.646 and 0.666 seconds, respectively. These are workload-specific measurements,
not cross-platform performance guarantees.

## Assembly packages

The b37 and hg38 archives have been:

- checked against their outer SHA-256 files;
- streamed and checked against their embedded manifests;
- extracted with DGW's path and file-type safety checks;
- checked file by file for size and SHA-256;
- combined with the Linux ARM64 tool package;
- accepted by DGW's complete resource-bundle validator.

The seven staged artifacts are indexed in `release-index.json`. They are not public
release assets yet.

## Still required before a general release

- Clean-machine application installation on each supported operating system
- macOS and Windows security/signing checks
- Final review of dataset redistribution notices
- A fresh-install test using the final public HTTPS URLs
