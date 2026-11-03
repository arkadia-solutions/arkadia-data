#!/bin/bash
# `make e2e`: format, lint, test and build Python, TypeScript and Rust, install
# each package in isolation and smoke-test it, then check that the Rust
# ak-data writes exactly what the Python package writes.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$(pwd)
UV=${UV:-uv} NPM=${NPM:-npm} CARGO=${CARGO:-cargo}

blue='' yellow='' green='' red='' nc=''
if [[ -z ${NO_COLOR+x} ]]; then
  blue=$'\033[0;34m'; yellow=$'\033[1;33m'; green=$'\033[0;32m'; red=$'\033[0;31m'; nc=$'\033[0m'
fi
log()  { echo -e "${blue}[E2E]${nc} $1"; }
fix()  { echo -e "${yellow}[FIX]${nc} $1"; }
ok()   { echo -e "${green}[OK]${nc} $1"; }
fail() { echo -e "${red}[ERROR]${nc} $1"; exit 1; }
expect() { if [[ "$2" == *"$3"* ]]; then log "  ✅ $1"; else fail "$1 returned: $2"; fi; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
data='{"users":[{"id":1,"name":"Ada"},{"id":2,"name":"Alan"}]}'
akd='<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])'

log "--- [1/5] Python: format, lint, tests (uv + ruff + pytest) ---"
cd "$root/python"
fix "Formatting (ruff format)…";        $UV run ruff format .
fix "Fixing lint errors and imports…";  $UV run ruff check --fix .
log "Running tests (pytest)…";          $UV run --all-extras pytest -q
log "Building the wheel and importing it in an isolated venv…"
rm -rf dist && $UV build -q
python3 -m venv "$tmp/venv" && "$tmp/venv/bin/pip" install -q dist/*.whl
expect "import arkadia.data as akd" \
  "$(DATA="$data" "$tmp/venv/bin/python" -c 'import json, os, arkadia.data as akd; d = json.loads(os.environ["DATA"]); t = akd.dumps(d); assert akd.loads(t) == d; print(t)')" "$akd"
ok "Python package works after installation."

log "--- [2/5] TypeScript: format, lint, tests, build (Biome + vitest + tsc) ---"
cd "$root/typescript"
[[ -d node_modules ]] || { fix "Installing dependencies…"; $NPM install; }
fix "Formatting and fixing lint errors (biome check --write)…"; npx biome check --write .
log "Running tests (vitest)…";              $NPM test --silent
log "Building and verifying the package…";  $NPM run verify --silent
pkg=$($NPM pack --silent --pack-destination "$tmp" | tail -n 1)
$NPM install --silent --no-save --prefix "$tmp/npm" "$tmp/$pkg"
expect "import { encode, decode } from '@arkadia/data'" \
  "$(cd "$tmp/npm" && DATA="$data" node -e 'const { encode, loads } = require("@arkadia/data"); const d = JSON.parse(process.env.DATA); const t = encode(d, { compact: true }); if (JSON.stringify(loads(t)) !== JSON.stringify(d)) process.exit(1); console.log(t)')" "$akd"
ok "npm package works after installation."

log "--- [3/5] Rust: format, lint, tests, release build (rustfmt + clippy + cargo test) ---"
cd "$root/rust"
fix "Formatting (cargo fmt)…";                  $CARGO fmt
log "Linting (clippy, warnings are errors)…";   $CARGO clippy --locked --all-targets -q -- -D warnings
log "Running tests (cargo test)…";              $CARGO test --locked -q
log "Building the release binary…";             $CARGO build --locked --release -q
ok "Rust crate is clean and formatted."

log "--- [4/5] ak-data: install the release binary and test it ---"
METHOD=prefix PREFIX="$tmp/prefix" bash scripts/install.sh > /dev/null
bin="$tmp/prefix/bin/ak-data"
expect "ak-data --version"     "$("$bin" --version)"                          "0."
expect "ak-data -t toon"       "$(echo "$akd" | "$bin" -t toon)"              "users[2]{id,name}:"
expect "ak-data (stdin)"       "$(echo "$data" | "$bin" -c)"                  "$akd"
expect "ak-data text -t json"  "$("$bin" "$akd" -t json-min)"                 "$data"
expect "ak-data diff (stdin)"  "$(echo '{"a":1} {"a":2}' | "$bin" diff --paths)" "~ a  1 → 2"
expect "ak-data prompt -e 3"   "$("$bin" prompt -e 3 -f ak-data-compact)"     "<data>"
expect "ak-data prompt --list" "$("$bin" prompt --list)"                      "66 bundled examples"
expect "ak-data prompt --meta" "$("$bin" prompt -e 11 --attributes --comments)" '$unit="grosze"'
expect "ak-data read -c"       "$(echo "$data" | "$bin" read -c)"             "$akd"
expect "ak-data read -t json"  "$(echo "$akd" | "$bin" read -t json-min)"     "$data"
expect "ak-data FILE"          "$(echo "$data" > "$tmp/d.json"; "$bin" "$tmp/d.json" -c)" "$akd"
echo '{"users":[{"id":1,"name":"Ada"}],"v":1}' > "$tmp/old.json"
echo '{"users":[{"id":1,"name":"Ada L."},{"id":2,"name":"Alan"}],"v":1}' > "$tmp/new.json"
expect "ak-data diff"          "$("$bin" diff "$tmp/old.json" "$tmp/new.json" -t akd -c)"   '("change","users[id=1].name","Ada","Ada L.")'
expect "ak-data merge"         "$("$bin" merge "$tmp/old.json" "$tmp/new.json" -f json -c --quiet)" '"name":"Alan"'
"$bin" "$tmp/old.json" -c -o "$tmp/data.akd" 2>/dev/null
"$bin" diff "$tmp/old.json" "$tmp/new.json" -m "Add Alan" -o "$tmp/patch.akd" > /dev/null 2>&1
"$bin" apply "$tmp/data.akd" "$tmp/patch.akd" --quiet
expect "ak-data apply"         "$("$bin" "$tmp/data.akd" -t json-min)"      '"name":"Ada L."},{"id":2,"name":"Alan"}'
expect "ak-data history"       "$("$bin" history "$tmp/data.akd" --oneline)"   "Add Alan"
expect "ak-data example"       "$("$bin" example 2 --raw | "$bin" -t json-min)" '"orders"'
expect "ak-data example -p"    "$("$bin" example --seed 1 --prompt --raw)"     "Question:"
expect "ak-data info"          "$("$bin" info grammar)"                        "document   ="
ok "ak-data works after installation."

log "--- [5/5] Cross-language: Rust writes exactly what Python writes ---"
cd "$root/python"
$UV run --all-extras python ../rust/scripts/compat.py "$root/rust/target/release/ak-data" --random 500
$UV run --all-extras python ../rust/scripts/compat_prompts.py "$root/rust/target/release/ak-data"
ok "Rust and Python produce identical AK-DATA and TOON."

echo
echo -e "${green}=============================================${nc}"
echo -e "${green}   ALL CHECKS PASSED 🚀  READY TO COMMIT.     ${nc}"
echo -e "${green}=============================================${nc}"
