# arkadia-data (Rust) — AK-DATA, Arkadia Data Format

Lossless, token-efficient text for JSON in LLM prompts, tool results and
agent memory: one header with the field names, then positional records.
Decoding always returns the original JSON. The Rust crate writes exactly the
same text as the Python (`arkadia-data`) and npm (`@arkadia/data`) packages.

This crate is also the home of the **`ak-data` command line tool**.

## Library

```toml
[dependencies]
arkadia-data = "0.3"
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
| `examples::all()`, `examples::get("3")` | the 66 bundled examples |
| `diff::{diff, merge, apply, reverse, commit, history}` | changes between documents and their history (`$changes`) |
| `estimate_tokens` | token estimate without a tokenizer |

Only dependency: `serde_json`. The default feature `preserve_order` keeps the
JSON key order (headers follow the source); with `default-features = false`
keys are sorted, which is still lossless.

## `ak-data` command

```bash
cargo install arkadia-data               # or: brew install arkadia-solutions/tap/ak-data
```

Ready-made binaries for macOS (signed and notarized), Linux and Windows are
on [GitHub Releases](https://github.com/arkadia-solutions/arkadia-data/releases).

```text
ak-data data.json [-c]                   any file or text → AK-DATA, laid out or one line
echo '{"a":1}' | ak-data                 stdin works too
ak-data data.akd -t json                 → JSON (-t json-min, toon, akd-compact; -i json|akd; -o file)
ak-data diff old.json new.json           the changes as a patch (--info: in place, like git diff)
ak-data merge data.akd new.json          join and record the change in the history
ak-data apply data.akd patch.akd         apply a patch (-R: undo)
ak-data history data.akd                 like git log
ak-data prompt data.json -q "…"          a copy-paste prompt for a chat model
ak-data example [--prompt]               the bundled examples
ak-data info [section]                   the complete format definition
```

Every command has `--help` with small examples. Colours only in a terminal;
`--no-color` / `NO_COLOR=1` turn them off, `--color` forces them.

In the library, `arkadia_data::layout::{pretty, compact, highlight}` lay out,
compact and colour any AK-DATA text.

MIT © Arkadia Solutions · https://arkadia.solutions/akdata · [changelog](https://github.com/arkadia-solutions/arkadia-data/blob/main/CHANGELOG.md)
