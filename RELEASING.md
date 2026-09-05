# Publishing DGW resources

Resource archives are release assets, not Git files. Do not add them to the
repository or Git LFS. The repository owner uploads large files explicitly after
reviewing their provenance and redistribution terms.

## Before publishing

The current staging directory is outside the repository:

```text
/media/mrueda/2TBS/Databases/dgw/releases/
```

Verify the complete release index:

```sh
cd /media/mrueda/2TBS/Databases/dgw/releases
sha256sum -c release-index.json.sha256
find data tools -name '*.sha256' -print0 | xargs -0 -n1 sh -c 'cd "$(dirname "$1")" && sha256sum -c "$(basename "$1")"' sh
```

Inspect `release-index.json`, the manifests inside the archives, `README.md`, and
the upstream license notices before uploading anything.

## Upload the data packages

The b37 and hg38 archives are larger than 500 MB. Run these commands yourself from
the staging directory. Creating the release and uploading the assets are kept as
separate commands so an interrupted upload can be retried without recreating the
release.

```sh
gh release create resources-r1 \
  --repo mrueda/dgw-data \
  --title 'DGW resources r1' \
  --notes 'Pinned b37/hg38 resources and tested platform tools for DGW. See each archive manifest for provenance and licensing.'

gh release upload resources-r1 \
  data/r1/dgw-data-b37-r1.tar.gz \
  data/r1/dgw-data-b37-r1.tar.gz.sha256 \
  --repo mrueda/dgw-data

gh release upload resources-r1 \
  data/r1/dgw-data-hg38-r1.tar.gz \
  data/r1/dgw-data-hg38-r1.tar.gz.sha256 \
  --repo mrueda/dgw-data
```

If an upload is interrupted, repeat its `gh release upload` command. Add
`--clobber` only when deliberately replacing an asset after confirming its local
SHA-256. Published immutable releases should normally receive a new revision
instead of replacing an archive.

## Upload the platform tools

The tool archives are much smaller, but they follow the same release-asset model:

```sh
gh release upload resources-r1 \
  tools/1.24-2/*.tar.gz \
  tools/1.24-2/*.sha256 \
  --repo mrueda/dgw-data
```

## Enable automatic installation

Direct application downloads require anonymously accessible HTTPS assets. A private
GitHub repository does not provide that to ordinary DGW installations. Keep the
catalog URL-free while the project is private. When the resource repository and
release assets are intentionally made public:

1. Generate the release index with the public release-download base URL.
2. Verify the generated archive checksums have not changed.
3. Copy the index into DGW as `config/resource-artifacts.json`.
4. Build DGW and test one fresh installation per supported operating system.

For example:

```sh
python3 scripts/release_index.py \
  /media/mrueda/2TBS/Databases/dgw/releases \
  --output /media/mrueda/2TBS/Databases/dgw/releases/release-index.public.json \
  --flat-base-url https://github.com/mrueda/dgw-data/releases/download/resources-r1
```

The flat URL option is important because GitHub release assets do not retain the
local `data/` and `tools/` subdirectories. Do not insert guessed URLs by hand.
