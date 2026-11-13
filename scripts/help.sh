#!/bin/bash
# `make help`: the colored guide. Honors NO_COLOR; COLOR=always forces color.
set -euo pipefail
cd "$(dirname "$0")/.."
accent='' bold='' dim='' cyan='' reset=''
if [[ -z ${NO_COLOR+x} && ( -t 1 || ${COLOR:-auto} == always ) ]]; then
  accent=$'\033[38;5;34m'; bold=$'\033[1;97m'; dim=$'\033[90m'; cyan=$'\033[36m'; reset=$'\033[0m'
fi
IFS= read -r version < VERSION || true
version=${version//[[:space:]]/}  # also drops \r (Windows checkouts)
IFS=. read -r v_major v_minor _ <<< "$version"
next="$v_major.$((v_minor + 1)).0"
printf '\n%s' "$accent"
cat assets/logo.txt
printf '%s\n  %sAK-DATA · ARKADIA DATA FORMAT%s  %sv%s%s\n' "$reset" "$bold" "$reset" "$dim" "$version" "$reset"
printf '  Lossless, token-efficient JSON for LLMs and agents.\n'
printf '  %sLibraries: Python arkadia-data · npm @arkadia/data · Rust arkadia-data · CLI: ak-data (Rust)%s\n\n' "$dim" "$reset"
row() { printf '  %s%-40s%s %s\n' "$cyan" "$1" "$reset" "$2"; }
section() { printf '\n  %s%s%s\n' "$accent" "$1" "$reset"; }
section 'SETUP'
row 'make prepare' 'Install all dependencies: uv sync, npm install, cargo fetch.'
row 'make prepare-py | -ts | -rs' 'Only Python, TypeScript or Rust.'
section 'VERSION'
row 'make update' "Next minor version ($version → $next) in ./VERSION and all three packages."
row 'make version' 'Show the version; check that npm, Python and Rust use it.'
section 'RELEASE'
row 'make release' 'ak-data archive for this computer → dist/release (macOS: signed + notarized).'
row 'make release UNSIGNED=1' 'The same without signing; TARGET=<triple> for another target.'
row "git push origin v$version" 'GitHub Actions: all platforms → GitHub Release, Homebrew tap, crates.io.'
section 'BUILD'
row 'make build' 'Python wheel + sdist, npm package, Rust release binary.'
row 'make build-py | -ts | -rs' 'python/dist, typescript/dist, rust/target/release/ak-data.'
section 'INSTALL'
row 'make install' 'Build and install ak-data with Homebrew (local tap arkadia/local).'
row 'make install METHOD=prefix' 'Install into ~/.local/bin instead (no Homebrew needed).'
row 'make install PREFIX=/path' 'Choose another prefix for METHOD=prefix; add its bin/ to PATH.'
row 'make uninstall' 'Remove the installed ak-data.'
section 'RUST PACKAGE'
row 'make package-rs' 'rust/dist/arkadia-data-<version>.crate (cargo package).'
row 'make add-to-cli' 'Vendor it into ../arkadia-cli and add it to the daemon (service).'
row 'make add-to-cli CLI=… ORDER=1' 'Another arkadia-cli folder; keep JSON key order (preserve_order).'
section 'TEST'
row 'make test' 'Unit tests: pytest, vitest, cargo test.'
row 'make test-py | -ts | -rs' 'One language only.'
row 'make e2e' 'Format, lint, test and build all, install, then compare Rust with Python.'
section 'BENCHMARK'
row 'make benchmark' 'Tokens, AI (bundled + RANDOM=24 generated datasets), HTML report → benchmarks/.'
row 'make benchmark ONLY_SHOW=1' 'Only print the prompt of every test (--only-show).'
row 'make benchmark DIR=~/my-json' 'Benchmark your own JSON files.'
row 'make benchmark NETWORK=1 MODEL=gpt-5.4-mini' 'With a model (offline without NETWORK=1): OPENAI_API_KEY / ANTHROPIC_API_KEY.'
row 'make benchmark RANDOM=48 TRIALS=3' 'More generated datasets / repeats; SEED=…, REASONING=low (GPT-5).'
row 'make benchmark-runs' 'Every test of the runs in reports/ → benchmarks/runs (website /akdata/runs).'
row 'make analyze' 'What to improve: paired test vs JSON, weak question types, AK-DATA misses.'
row 'make benchmark PROVIDER=ollama …' 'A local model (MODEL=qwen3:8b); ARGS="--write" passes more flags.'
section 'CHECK (METADATA TRAPS)'
row 'make check' '5 metadata-trap cases × 4 forms (JSON, JSON+_meta, AK-Data, AK-Data+/*…*/) on OpenAI, Anthropic, Google.'
row 'make check PROVIDERS="openai google"' 'Choose providers; OPENAI_MODEL=… ANTHROPIC_MODEL=… GOOGLE_MODEL=… (keys from .env).'
row 'make check CASES=1,4 FORMS=BD TRIALS=3' 'Subset of cases (1..5) or forms (A/B/C/D), repeated TRIALS times; REASONING=low.'
row 'make check SHOW=4 | COPY=4D' 'Print the 4 prompts of case 4 (SHOW=all: every case) or copy prompt 4D to clipboard.'
row 'make check PROMPTS=0 | DEMO=1 | DRY=1' 'Answers only (PROMPTS=0), invented answers without calls (DEMO=1), or validate + tokens (DRY=1).'
section 'MAINTAIN'
row 'make help' 'Show this guide. Honors NO_COLOR; COLOR=always forces color.'
row 'make examples' 'Regenerate the 66 examples (51 real-size + 15 features) for ak-data, the website and examples/prompts.'
row 'make skill' 'Regenerate the skill reference (skills/ak-data-format/reference).'
row 'make clean' 'Remove build outputs, caches and reports/.'
section 'QUICK START'
printf '  %smake prepare\n  make install\n  ak-data data.json -c\n  ak-data prompt --example 3 --format toon%s\n' "$bold" "$reset"
printf '\n  %sWithout an API key the AI benchmark is a dry run (prompt sizes only). See README.md.%s\n\n' "$dim" "$reset"
