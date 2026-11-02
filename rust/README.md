# arkadia-data (Rust) — AK-DATA, Arkadia Data Format

Lossless, token-efficient text for JSON in LLM prompts, tool results and
agent memory: one header with the field names, then positional records.
Decoding always returns the original JSON. The Rust crate writes exactly the
same text as the Python (`arkadia-data`) and npm (`@arkadia/data`) packages.

This crate is also the home of the **`ak-data` command line tool**.

## Library

```toml
[dependencies]
arkadia-data = "0.2"            # or: arkadia-data = { path = "../arkadia-data/rust" }
```

```rust
use arkadia_data as akd;
use serde_json::json;

let data = json!({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]});

let text = akd::encode(&data);            // <users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])
let back = akd::decode(&text)?;           // == data
let pretty = akd::encode_pretty(&data);   // readable form

// Text in, text out (e.g. a daemon that formats both ways):
let akd_text = akd::json_to_akd(r#"{"a":[1,2]}"#, true)?;   // <a:[number]>([1,2])
let json_text = akd::akd_to_json(&akd_text, false)?;       // {"a":[1,2]}
let toon = akd::convert(&akd_text, akd::Format::Toon)?;    // JSON or AK-DATA in, any format out

// Model output that may be JSON or AK-DATA, with code fences:
let value = akd::loads_any("```\n<n:number>(1)\n```")?;

// Prompts
let p = akd::build_prompt(&data, "Who joined first?", akd::Format::AkDataCompact, None, true);
let tokens = akd::estimate_tokens(&p);
```

| API | |
|---|---|
| `encode`, `encode_pretty`, `encode_with(&EncodeOptions)` | JSON value → AK-DATA |
| `decode` (strict), `decode_lenient` (value + errors) | AK-DATA → JSON value |
| `json_to_akd`, `akd_to_json`, `convert`, `loads_any`, `is_json` | text-level conversions |
| `Format` (`json`, `json-min`, `toon`, `ak-data`, `ak-data-compact`), `encode_as` | every prompt format |
| `toon::encode` | TOON (same output as the reference `toon-format`) |
| `build_prompt`, `Answer`, `FORMAT_DEFINITION`, `HINT`, `TOON_DEFINITION`, `to_prompt` | copy-paste prompts |
| `examples::all()`, `examples::get("3")` | the ten bundled examples |
| `estimate_tokens` | token estimate without a tokenizer |

Only dependency: `serde_json`. The default feature `preserve_order` keeps the
JSON key order (headers follow the source); with `default-features = false`
keys are sorted, which is still lossless.

## `ak-data` command

```bash
make install                 # from the repository root: build + install (Homebrew local tap, or ~/.local/bin)
cargo install --path rust    # or with Cargo directly
```

```text
ak-data data.json [-c]                   anything → AK-DATA, laid out or one line (= ak-data read)
echo '{"a":1}' | ak-data                 stdin, or text: ak-data '{"a":1}', ak-data '```…```'
ak-data data.akd -t json|json-min|toon|akd-compact [-i json|akd] [-o file]
ak-data diff old.json new.json           the changes as a patch (-o fix.akd; --info: in context like git diff)
ak-data merge data.akd new.json          join + record the change in $changes [--latest] [-m title]
ak-data apply data.akd patch.akd         apply a patch / history entries [--change id] [-R] [--no-history]
ak-data history data.akd                 like git log [--oneline] [-p] [--path users]
ak-data prompt data.json -q "…" -f ak-data-compact -a "name:string,total:number"
ak-data prompt --list | --example 3 --format toon [--attributes] [--comments] [--all-formats] [--expected]
ak-data data.akd [--width 80] [--no-comments] [--no-attributes]   keeps comments and history
ak-data example [id|slug] [--prompt] [--json] [--raw] [--list] [--seed N]
ak-data info [section] [--list]
```

`ak-data example` shows a random example from the 66 bundled ones (flat tables,
nesting, irregular records, type overrides, named types, metadata …): what it
shows, the readable and compact forms laid out and coloured, token counts and a
round-trip check; `--prompt` adds a copy-paste prompt for a chat model and the
expected answer (`--raw` prints only the prompt, e.g. for `| pbcopy`).
`ak-data info` prints the complete format definition — document structure,
values, headers, records, lists, overrides, named types, metadata, encoder
rules, JSON mapping, grammar, writing rules — with every example decoded live.

In the library, `arkadia_data::layout::pretty(text, width)` lays out any
AK-DATA text (same algorithm as `pretty` in `@arkadia/data`),
`layout::compact` puts it on one line and `layout::highlight` colours it.

`ak-data` without a command reads its input (a file, text or stdin) and
shows it as AK-DATA; with nothing to read, or `--help`, it shows the logo and
the colored guide; `ak-data <command> --help` the options of one command. Colors only in
a terminal; `--no-color` / `NO_COLOR=1` turn them off, `--color` forces them.
In a terminal `ak-data` highlights what it writes (never in files or pipes).

## Package for arkadia-cli (daemon)

```bash
bash rust/scripts/package.sh                       # → rust/dist/arkadia-data-<version>.crate
make add-to-cli                       # vendor it into ../arkadia-cli, cargo add to service/
make add-to-cli CLI=~/src/arkadia-cli CRATE=service ORDER=1
```

`add-to-cli` unpacks the `.crate` into `arkadia-cli/vendor/arkadia-data`
(an older copy is replaced), adds `exclude = ["vendor"]` to its `[workspace]`
and runs `cargo add arkadia-data --path vendor/arkadia-data` for the daemon
crate. Then, in the daemon: `use arkadia_data as akd; akd::encode(&value)`.
Run it again after changing arkadia-data. `ORDER=1` keeps `preserve_order`;
it is off by default because Cargo would enable it for serde_json in the
whole of arkadia-cli (key order of every JSON the daemon writes).

## Tests

```bash
cargo test                                   # unit, fixtures from Python, 3000 random round-trips
cd ../python && uv run --all-extras python ../rust/scripts/compat.py ../rust/target/release/ak-data
```

`compat.py` compares the binary with the Python package on the bundled
datasets, the examples, the TOON spec fixtures and random values (AK-DATA
compact and readable, TOON, decoding). `make_fixtures.py` refreshes
`tests/fixtures.json`.

MIT © Arkadia Solutions · https://arkadia.solutions/akdata


0.2.0 is a source preview; install with `cargo install --path rust --locked` from the monorepo root. Registry installation is not available until the owner publishes and verifies the release.
