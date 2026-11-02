# Contributing

Use a current Rust toolchain, Node.js 22/24 and Python 3.10 or newer with uv. Install with `make prepare`. The three implementation directories are one monorepository; do not use the old split-repository URLs.

Checks: `make test`, `python3 scripts/check_release.py --history`, and the package smoke checks in `.github/workflows/ci.yml`. `make e2e` additionally formats code, builds and installs into a temporary prefix and compares Rust/Python outputs; review its source before running. It never publishes packages. Benchmarking is offline unless `NETWORK=1` is explicitly supplied. Use only synthetic data in tests/issues.

`python/tests/fixtures/conformance.json` is the shared semantic round-trip corpus; identical copies live in `typescript/tests/fixtures/` and `rust/tests/fixtures/` so each package stays independently testable. Update all copies together and add a regression case before changing parser/encoder behavior. Tests must include special property names, nested/mixed data and malformed input; do not silently discard fields. Package version and format version are distinct.

Python: `uv run --locked --all-extras pytest`, `uv run ruff check .`, `uv run ruff format --check .` in python/. TypeScript: `npm ci`, `npm test`, `npm run build` in typescript/. Rust: `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings` in rust/. Run Python commands through uv rather than a stale pre-existing venv. Preview APIs may change; describe compatibility implications in CHANGELOG.md.
