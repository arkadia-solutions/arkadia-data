# AK-DATA (Arkadia Data Format) developer commands. Run `make` for the colored guide.
# Libraries: Python arkadia-data · npm @arkadia/data · Rust arkadia-data. CLI: ak-data (Rust).

.DEFAULT_GOAL := help
.PHONY: help prepare prepare-py prepare-ts prepare-rs update version version-sync release homebrew-formula build build-py build-ts build-rs \
        install uninstall test test-py test-ts test-rs e2e benchmark benchmark-runs analyze skill examples clean
UV        ?= uv
NPM       ?= npm
CARGO     ?= cargo
METHOD    ?= auto
PREFIX    ?= $(HOME)/.local
OUT       ?= reports
PROVIDER  ?= auto
NETWORK   ?= 0
DIR       ?=
MODEL     ?=
BASE_URL  ?=
ONLY_SHOW ?=
ARGS      ?=
# AI benchmark: generated datasets on top of the bundled ones (more questions),
# their seed, repeats of every prompt, reasoning_effort for GPT-5 / o-series.
RANDOM    ?= 24
SEED      ?= 7
TRIALS    ?= 1
REASONING ?=
BENCH_ARGS = $(if $(filter 1 yes true,$(NETWORK)),--allow-network,--offline) --out $(abspath $(OUT)) --provider $(PROVIDER) $(if $(DIR),--dir $(abspath $(DIR))) \
	$(if $(MODEL),--model $(MODEL)) $(if $(BASE_URL),--base-url $(BASE_URL)) \
	--random $(RANDOM) --seed $(SEED) --trials $(TRIALS) $(if $(REASONING),--reasoning $(REASONING)) \
	$(if $(filter 1 yes true,$(ONLY_SHOW)),--only-show) \
	$(if $(DIR),,--site $(abspath benchmarks/benchmark.json)) $(ARGS)

help:
	@bash scripts/help.sh

# Install dependencies of all three packages.
prepare: prepare-py prepare-ts prepare-rs
prepare-py:
	cd python && $(UV) sync --all-extras
prepare-ts:
	cd typescript && $(NPM) ci
prepare-rs:
	cd rust && $(CARGO) fetch --locked

# One version for npm, Python and Rust, kept in ./VERSION.
# make update: the next minor version (0.2.0 → 0.3.0) written into every package.
update:
	@bash scripts/version.sh bump minor
version:
	@bash scripts/version.sh check
version-sync:
	@bash scripts/version.sh sync > /dev/null

# Release archive of ak-data for this computer → dist/release/ (macOS: universal,
# signed and notarized with the Developer ID from the keychain or .env;
# UNSIGNED=1 skips that). On a tag, .github/workflows/release.yml does it for
# every platform and publishes. HOMEBREW: the tap formula from dist/release.
release:
	@bash scripts/release.sh $(if $(filter 1 yes true,$(UNSIGNED)),--no-sign) $(if $(TARGET),--target $(TARGET))
homebrew-formula:
	@bash scripts/homebrew-formula.sh dist/release

# Build the packages: python/dist, typescript/dist, rust/target/release/ak-data
# (each first takes the version from ./VERSION).
build: version-sync build-py build-ts build-rs
build-py:
	cd python && rm -rf dist && $(UV) build
build-ts:
	cd typescript && $(NPM) run build
build-rs:
	cd rust && $(CARGO) build --release --locked

# Install the ak-data program: Homebrew local tap, or METHOD=prefix into PREFIX/bin.
install: build-rs
	METHOD=$(METHOD) PREFIX=$(PREFIX) bash rust/scripts/install.sh
uninstall:
	METHOD=$(METHOD) PREFIX=$(PREFIX) bash rust/scripts/install.sh --uninstall

# Unit tests.
test: test-py test-ts test-rs
test-py:
	cd python && $(UV) run --all-extras pytest -q
test-ts:
	cd typescript && $(NPM) test
test-rs:
	cd rust && $(CARGO) test --locked

# Format, lint, test, build and install everything; Rust output must equal Python's.
e2e:
	@UV=$(UV) NPM=$(NPM) CARGO=$(CARGO) bash scripts/e2e.sh

# Tokens → AI comprehension → reports/report.html (ONLY_SHOW=1: print prompts only).
# Bundled datasets also update benchmarks/benchmark.json (the website copies it).
benchmark:
	cd python && $(UV) run --all-extras python -m arkadia.bench $(BENCH_ARGS)

# Every test of the AI runs in reports/ (prompt, reply, answers) → benchmarks/runs/
# for the website; make benchmark does this itself for the runs it makes.
benchmark-runs:
	cd python && $(UV) run --all-extras python -m arkadia.bench.runs $(filter-out %dry-run.json,$(wildcard $(abspath $(OUT))/ai-*.json)) -o $(abspath benchmarks/runs) --site $(abspath benchmarks/benchmark.json)

# What to improve: paired comparison with JSON, weak question types, the
# questions AK-DATA got wrong (REPORT=reports/ai-….json, default the newest;
# FORMAT=akcd-n to list another format's misses, VS=toon for another reference).
REPORT ?=
FORMAT ?= akcd
VS     ?= json
analyze:
	cd python && $(UV) run --all-extras python -m arkadia.bench.analyze $(if $(REPORT),$(abspath $(REPORT))) --format $(FORMAT) --vs $(VS)

# Regenerate skills/ak-data-format/reference/ from ak-data.
skill: build-rs
	bash scripts/skill-refs.sh

# Copy-paste prompts (examples/prompts: 51 examples, every format with/without metadata).
examples:
	cd python && $(UV) run --all-extras python scripts/make_examples.py

# Remove build outputs, caches and reports/.
clean:
	rm -rf python/dist python/.pytest_cache python/.ruff_cache typescript/dist rust/target rust/dist $(OUT)
	find python -name __pycache__ -type d -prune -exec rm -rf {} +
