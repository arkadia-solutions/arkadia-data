#!/bin/bash
# Adds the arkadia-data Rust library to arkadia-cli as a local (vendored)
# dependency of the daemon crate, so the daemon can `use arkadia_data`.
#
#   rust/scripts/add-to-cli.sh [CLI_DIR]          default CLI_DIR: ../arkadia-cli
#   CRATE=service ORDER=1 rust/scripts/add-to-cli.sh ../arkadia-cli
#
# Steps: build rust/dist/arkadia-data-<version>.crate, unpack it into
# CLI_DIR/vendor/arkadia-data (replacing an older copy), keep vendor/ out of
# the Cargo workspace and run `cargo add` for the crate in CLI_DIR/$CRATE.
#
# ORDER=1 keeps the `preserve_order` feature (JSON key order in AK-DATA
# headers, identical to Python). It is off by default because Cargo enables
# features for the whole build: serde_json would keep insertion order in all
# of arkadia-cli, not only here. Output is lossless either way.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cli="$(cd "${1:-$here/../../arkadia-cli}" && pwd)"
member=${CRATE:-service}
cargo=${CARGO:-cargo}

[[ -f $cli/Cargo.toml ]] || { echo "No Cargo.toml in $cli" >&2; exit 1; }
[[ -f $cli/$member/Cargo.toml ]] || { echo "No crate $member in $cli (set CRATE=…)" >&2; exit 1; }

bash "$here/scripts/package.sh"
crate=$(bash "$here/scripts/package.sh" --print)
version=$(basename "$crate" .crate | sed 's/^arkadia-data-//')

# Unpack into vendor/arkadia-data (the .crate contains arkadia-data-<version>/).
mkdir -p "$cli/vendor"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
tar -xzf "$crate" -C "$stage"
rm -rf "$cli/vendor/arkadia-data"
mv "$stage/arkadia-data-$version" "$cli/vendor/arkadia-data"
# The vendored copy is a dependency, not a project: no tests/benchmarks of it run.
rm -rf "$cli/vendor/arkadia-data/tests" "$cli/vendor/arkadia-data/target"
echo "Vendored arkadia-data $version → $cli/vendor/arkadia-data"

# Path dependencies inside the workspace folder become members; exclude vendor/.
root="$cli/Cargo.toml"
if grep -q '^\[workspace\]' "$root" && ! grep -q '^exclude *=.*vendor' "$root"; then
  if grep -q '^exclude *=' "$root"; then
    echo "Note: add \"vendor\" to [workspace] exclude in $root" >&2
  else
    awk '{print} /^\[workspace\]/{print "exclude = [\"vendor\"]"}' "$root" > "$root.tmp" && mv "$root.tmp" "$root"
    echo "Added exclude = [\"vendor\"] to [workspace] in Cargo.toml"
  fi
fi

features=(--no-default-features)
[[ ${ORDER:-0} == 1 ]] && features=(--features preserve_order)
(cd "$cli" && "$cargo" add arkadia-data --path vendor/arkadia-data --package "$(sed -n 's/^name = "\([^"]*\)"/\1/p' "$member/Cargo.toml" | head -1)" "${features[@]}")

cat <<EOF

arkadia-data $version is a dependency of $member. In the daemon:

    use arkadia_data as akd;
    let text = akd::encode(&value);              // compact AK-DATA for prompts
    let back = akd::decode(&text)?;              // the original JSON
    let tokens = akd::estimate_tokens(&text);

Update later: run this script again (or: make add-to-cli CLI=$cli in arkadia-data).
EOF
