#!/bin/bash
# Installs the ak-data command from rust/target/release (run `make build-rs` first).
#
#   rust/scripts/install.sh            Homebrew (local tap arkadia/local) when brew exists,
#                                      otherwise $PREFIX/bin (default ~/.local/bin)
#   METHOD=prefix PREFIX=/usr/local rust/scripts/install.sh
#   rust/scripts/install.sh --uninstall
set -euo pipefail
cd "$(dirname "$0")/.."

bin=target/release/ak-data
version=$(sed -n 's/^version = "\([^"]*\)"/\1/p' Cargo.toml | head -1)
method=${METHOD:-auto}
prefix=${PREFIX:-$HOME/.local}
if [[ $method == auto ]]; then
  if command -v brew >/dev/null 2>&1; then method=brew; else method=prefix; fi
fi

if [[ ${1:-} == --uninstall ]]; then
  if [[ $method == brew ]]; then
    brew uninstall --formula arkadia/local/ak-data 2>/dev/null || brew uninstall ak-data || true
  else
    rm -f "$prefix/bin/ak-data"
    [[ -L $prefix/bin/akd ]] && rm -f "$prefix/bin/akd"
  fi
  echo "ak-data removed ($method)."
  exit 0
fi

[[ -x $bin ]] || { echo "Missing $bin — run: make build-rs" >&2; exit 1; }

if [[ $method == prefix ]]; then
  install -d "$prefix/bin"
  install -m 755 "$bin" "$prefix/bin/ak-data"
  # The short name akd of earlier versions is not installed any more.
  [[ -L $prefix/bin/akd ]] && rm -f "$prefix/bin/akd"
  echo "Installed $prefix/bin/ak-data ($("$prefix/bin/ak-data" --version --no-color))"
  case ":$PATH:" in *":$prefix/bin:"*) ;; *) echo "Add $prefix/bin to PATH." ;; esac
  exit 0
fi

# Homebrew: a formula in the local tap arkadia/local (as arkadia-cli does),
# pointing at a tarball of the binary that was just built.
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
install -m 755 "$bin" "$stage/ak-data"
mkdir -p dist
archive="$(pwd)/dist/ak-data-$version-local.tar.gz"
tar -czf "$archive" -C "$stage" ak-data
sha=$(shasum -a 256 "$archive" | cut -d ' ' -f1)
brew tap-new --no-git arkadia/local >/dev/null 2>&1 || brew --repo arkadia/local >/dev/null
tap=$(brew --repo arkadia/local)
mkdir -p "$tap/Formula"
cat > "$tap/Formula/ak-data.rb" <<RUBY
class AkData < Formula
  desc "AK-DATA (Arkadia Data Format): lossless, token-efficient JSON for LLMs"
  homepage "https://arkadia.solutions/akdata"
  url "file://$archive"
  version "$version"
  sha256 "$sha"
  license "MIT"

  def install
    bin.install "ak-data"
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/ak-data --version")
  end
end
RUBY
if brew list --formula ak-data >/dev/null 2>&1; then
  brew reinstall arkadia/local/ak-data
else
  brew install arkadia/local/ak-data
fi
echo "Installed with Homebrew: $(command -v ak-data) ($(ak-data --version --no-color))"
found=$(command -v ak-data)
case "$found" in
  "$(brew --prefix)"/*) ;;
  *) echo "Note: $found comes first in PATH (an older ak-data, e.g. the Python one?) — remove it: uv tool uninstall arkadia-data / pip uninstall arkadia-data" >&2 ;;
esac
