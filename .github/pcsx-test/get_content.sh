#!/bin/bash
# Test-only: collect free PS1 homebrew to benchmark with.
# ps1-tests prebuilt programs, plus PSn00bSDK demos built from source.
set -x
OUT="$PWD/content"
mkdir -p "$OUT" work
cd work

# ps1-tests (prebuilt release)
mkdir -p ps1tests && (
  cd ps1tests
  gh release download -R JaCzekanski/ps1-tests -p '*' || exit 0
  ls -la
  for z in *.zip; do unzip -q -o "$z"; done
  find . -iname '*.exe' | sort
  for t in gpu/benchmark gpu/animated-triangle gte/gte-fuzz; do
    f=$(find . -ipath "*${t}*" -iname '*.exe' | head -1)
    [ -n "$f" ] && cp "$f" "$OUT/t_$(basename "$t").exe"
  done
)

# PSn00bSDK demos (release SDK + toolchain, examples built from the tag)
mkdir -p psn && (
  cd psn
  tag=$(gh release view -R Lameguy64/PSn00bSDK --json tagName -q .tagName) || exit 0
  gh release view -R Lameguy64/PSn00bSDK "$tag" --json assets -q '.assets[].name'
  gh release download -R Lameguy64/PSn00bSDK "$tag" -p '*inux*' -p '*.zip' --skip-existing || true
  ls -la
  mkdir -p sdk
  for z in *.zip; do case "$z" in *indows*|*src*|*ource*) continue;; esac; unzip -q -o "$z" -d sdk; done
  for t in *.tar.*; do [ -f "$t" ] && tar -xf "$t" -C sdk; done
  gcc_bin=$(find "$PWD/sdk" -name 'mipsel-*-elf-gcc' -type f | head -1)
  sdkcm=$(find "$PWD/sdk" -path '*libpsn00b/cmake/sdk.cmake' | head -1)
  echo "gcc=$gcc_bin sdk=$sdkcm"
  [ -n "$gcc_bin" ] && [ -n "$sdkcm" ] || exit 0
  target=$(basename "$gcc_bin" | sed 's/-gcc$//')
  export PATH="$(dirname "$gcc_bin"):$PATH"
  export PSN00BSDK_LIBS="$(dirname "$(dirname "$sdkcm")")"
  git clone -q --depth 1 --branch "$tag" https://github.com/Lameguy64/PSn00bSDK.git src || \
    git clone -q --depth 1 https://github.com/Lameguy64/PSn00bSDK.git src
  for ex in demos/n00bdemo graphics/fpscam graphics/balls graphics/billboard; do
    n=$(basename $ex)
    cmake -S "src/examples/$ex" -B "b_$n" -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE="$sdkcm" -DCMAKE_BUILD_TYPE=Release \
      -DPSN00BSDK_TC="$(dirname "$(dirname "$gcc_bin")")" -DPSN00BSDK_TARGET="$target" &&
    cmake --build "b_$n" &&
    cp "b_$n/$n.exe" "$OUT/p_$n.exe"
  done
)
ls -la "$OUT"
