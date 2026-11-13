# Contributing

Use a current Rust toolchain, Node.js 22/24 and Python 3.10 or newer with uv. Install with `make prepare`. The three implementation directories are one monorepository; do not use the old split-repository URLs.

Checks: `make test`, `python3 scripts/check_release.py --history`, and the package smoke checks in `.github/workflows/ci.yml`. `make e2e` additionally formats code, builds and installs into a temporary prefix and compares Rust/Python outputs; review its source before running. It never publishes packages. Benchmarking is offline unless `NETWORK=1` is explicitly supplied. Use only synthetic data in tests/issues.

`python/tests/fixtures/conformance.json` is the shared semantic round-trip corpus; identical copies live in `typescript/tests/fixtures/` and `rust/tests/fixtures/` so each package stays independently testable. Update all copies together and add a regression case before changing parser/encoder behavior. Tests must include special property names, nested/mixed data and malformed input; do not silently discard fields. Package version and format version are distinct.

Python: `uv run --locked --all-extras pytest`, `uv run ruff check .`, `uv run ruff format --check .` in python/. TypeScript: `npm ci`, `npm test`, `npm run build` in typescript/. Rust: `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings` in rust/. Run Python commands through uv rather than a stale pre-existing venv. Preview APIs may change; describe compatibility implications in CHANGELOG.md.

## Layout

```
python/       arkadia-data: arkadia.data (format), arkadia.bench (benchmarks & check), tests, datasets
typescript/   @arkadia/data
rust/         arkadia-data crate: library + the ak-data command
examples/     copy-paste prompts (examples/prompts/) and 5 metadata-trap cases (examples/meta-traps/cases.md)
skills/       ak-data-install and ak-data-format
benchmarks/   numbers and runs produced by `make benchmark`
```

## Development

Requires [uv](https://docs.astral.sh/uv/), Node.js and Rust. `make` shows the guide.

```bash
make prepare        # uv sync + npm ci + cargo fetch
make test           # pytest + vitest + cargo test
make e2e            # format + lint + tests + builds + installed packages + Rust output = Python output
make install        # build and install ak-data from this checkout (METHOD=prefix: ~/.local/bin)
make skill          # regenerate the skill reference from ak-data
make examples       # regenerate the 66 examples
make version        # check that all packages use ./VERSION
```

## Benchmarks

```bash
make benchmark                               # tokens and a dry AI run → reports/report.html
make benchmark DIR=~/my-json                 # on your own JSON files
make benchmark NETWORK=1 MODEL=gpt-5.4-mini  # with a model (OPENAI_API_KEY / ANTHROPIC_API_KEY)
make analyze                                 # paired tests, weak question types, misses
make check                                   # 5 metadata-trap cases × 4 forms across OpenAI, Anthropic, Google
make check DRY=1                             # validate cases and count tokens without API calls (DEMO=1: fake run)
```

The benchmark is offline unless `NETWORK=1` is given; with it, the selected
datasets are sent to the chosen provider. Reports can contain data, prompts
and answers and stay private (`reports/` is not committed).

## Releases

Maintainers release from `main`: `make update` (next minor version in
`./VERSION` and every package), the `## [x.y.z] - date` section in
`CHANGELOG.md`, then a tag `vx.y.z`. The tag runs
`.github/workflows/release.yml`, which builds `ak-data` for every platform and
publishes the release; its secrets are configured in the repository settings.
