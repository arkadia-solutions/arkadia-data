#!/bin/bash
# Builds the Rust package of arkadia-data: rust/dist/arkadia-data-<version>.crate
# (the same file `cargo publish` would upload; a .tar.gz of the crate sources).
#
#   rust/scripts/package.sh            build (and verify) the .crate
#   rust/scripts/package.sh --print    only print the path of the .crate
set -euo pipefail
cd "$(dirname "$0")/.."

version=$(sed -n 's/^version = "\([^"]*\)"/\1/p' Cargo.toml | head -1)
crate="dist/arkadia-data-$version.crate"
if [[ ${1:-} == --print ]]; then
  echo "$(pwd)/$crate"
  exit 0
fi

# --allow-dirty: works on uncommitted changes too; the package is verified by
# building the unpacked crate (library and ak-data) in target/package.
${CARGO:-cargo} package --locked --allow-dirty --quiet
mkdir -p dist
cp "target/package/arkadia-data-$version.crate" "$crate"
echo "Packaged $(pwd)/$crate ($(du -h "$crate" | cut -f1 | tr -d ' '))"
