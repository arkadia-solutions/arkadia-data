#!/usr/bin/env bash
# One version for all three packages, kept in ./VERSION.
#   scripts/version.sh            print it
#   scripts/version.sh sync       write it into Cargo.toml / Cargo.lock,
#                                 pyproject.toml / __init__.py / uv.lock,
#                                 package.json / package-lock.json
#   scripts/version.sh bump [minor|major|patch]   raise it (default minor), then sync
set -euo pipefail
cd "$(dirname "$0")/.."
current=$(tr -d ' \n' < VERSION)
[[ $current =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "VERSION is not x.y.z: '$current'" >&2; exit 1; }

sync() {
  local v=$1
  # Rust: [package] version and the crate's entry in Cargo.lock.
  perl -0pi -e 's/(\[package\]\nname = "arkadia-data"\nversion = ")[^"]+"/${1}'"$v"'"/' rust/Cargo.toml
  perl -0pi -e 's/(name = "arkadia-data"\nversion = ")[^"]+"/${1}'"$v"'"/' rust/Cargo.lock
  # Python: [project] version, __version__, the package's entry in uv.lock.
  perl -0pi -e 's/(\[project\]\nname = "arkadia-data"\nversion = ")[^"]+"/${1}'"$v"'"/' python/pyproject.toml
  perl -pi -e 's/^__version__ = "[^"]+"/__version__ = "'"$v"'"/' python/src/arkadia/data/__init__.py
  [[ -f python/uv.lock ]] && perl -0pi -e 's/(name = "arkadia-data"\nversion = ")[^"]+"/${1}'"$v"'"/' python/uv.lock
  # npm: package.json and the root entries of package-lock.json.
  perl -0pi -e 's/("name": "\@arkadia\/data",\n  "version": ")[^"]+"/${1}'"$v"'"/' typescript/package.json
  [[ -f typescript/package-lock.json ]] && perl -0pi -e 's/("name": "\@arkadia\/data",\n  "version": ")[^"]+"/${1}'"$v"'"/; s/(""\: \{\n      "name": "\@arkadia\/data",\n      "version": ")[^"]+"/${1}'"$v"'"/' typescript/package-lock.json
  check "$v"
}

check() {
  local v=$1 bad=0
  grep -q "^version = \"$v\"" rust/Cargo.toml || { echo "rust/Cargo.toml is not $v" >&2; bad=1; }
  grep -q "^version = \"$v\"" python/pyproject.toml || { echo "python/pyproject.toml is not $v" >&2; bad=1; }
  grep -q "^__version__ = \"$v\"" python/src/arkadia/data/__init__.py || { echo "python __version__ is not $v" >&2; bad=1; }
  grep -q "\"version\": \"$v\"" typescript/package.json || { echo "typescript/package.json is not $v" >&2; bad=1; }
  return $bad
}

case "${1:-}" in
  "") echo "$current" ;;
  sync) sync "$current" ;;
  check) check "$current" && echo "All packages are $current." ;;
  bump)
    IFS=. read -r major minor patch <<< "$current"
    case "${2:-minor}" in
      major) next="$((major + 1)).0.0" ;;
      minor) next="$major.$((minor + 1)).0" ;;
      patch) next="$major.$minor.$((patch + 1))" ;;
      *) echo "bump: major, minor or patch" >&2; exit 2 ;;
    esac
    echo "$next" > VERSION
    sync "$next"
    echo "Version $current → $next (VERSION, Cargo.toml, pyproject.toml, package.json)."
    ;;
  *) echo "usage: scripts/version.sh [sync|check|bump [minor|major|patch]]" >&2; exit 2 ;;
esac
