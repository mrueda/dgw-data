#!/usr/bin/env bash
set -euo pipefail
# Run from the repository root, in Bash (MSYS2 MINGW64 on Windows).
target=${1:?Supply a platform ID, e.g. linux-aarch64}
jobs=${DGW_BUILD_JOBS:-2}
python3 scripts/package.py prepare
root=$(pwd)
prefix="$root/work/deps"
flags=(-G "Unix Makefiles")
case "$target" in
  windows-x86_64)
    flags=(-G "MSYS Makefiles")
    export LDFLAGS="-static -static-libgcc"
    export LIBS="$(pkg-config --static --libs regex) -liconv"
    ;;
  linux-*) export LDFLAGS="-static-libgcc" ;;
  darwin-*) export MACOSX_DEPLOYMENT_TARGET=13.0 ;;
  *) echo "Unsupported platform: $target" >&2; exit 1 ;;
esac
cmake -S work/zlib-1.3.2 -B work/zlib-build "${flags[@]}" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DCMAKE_INSTALL_LIBDIR=lib -DZLIB_BUILD_SHARED=OFF -DZLIB_BUILD_STATIC=ON
cmake --build work/zlib-build --parallel "$jobs"
ctest --test-dir work/zlib-build --output-on-failure
cmake --install work/zlib-build
cmake -S work/libdeflate-1.26 -B work/libdeflate-build "${flags[@]}" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DCMAKE_INSTALL_LIBDIR=lib -DLIBDEFLATE_BUILD_SHARED_LIB=OFF \
  -DLIBDEFLATE_BUILD_STATIC_LIB=ON -DLIBDEFLATE_BUILD_TESTS=ON \
  -DLIBDEFLATE_USE_SHARED_LIB=OFF
cmake --build work/libdeflate-build --parallel "$jobs"
ctest --test-dir work/libdeflate-build --output-on-failure --no-tests=error
cmake --install work/libdeflate-build
export CPPFLAGS="-I$prefix/include"
export LDFLAGS="${LDFLAGS:-} -L$prefix/lib"
cd work/bcftools-1.24/htslib-1.24
./configure --disable-bz2 --disable-lzma --disable-libcurl --with-libdeflate --disable-plugins
make -j "$jobs" libhts.a bgzip tabix
cd ..
./configure --with-htslib=htslib-1.24 --disable-bcftools-plugins
make -j "$jobs" bcftools
cd "$root"
python3 scripts/package.py package "$target"
