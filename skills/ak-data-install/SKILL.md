---
name: ak-data-install
description: Install and use the AK-DATA tools (Arkadia Data Format) — the `ak-data` command (Rust) and the libraries PyPI `arkadia-data`, npm `@arkadia/data`, crates.io `arkadia-data` — to convert JSON to AK-DATA, count tokens and build prompts. Use when asked to set up AK-DATA, reduce tokens of JSON tool results/files, or run `ak-data`.
---

## Release boundary — 0.2 source preview

The current website demos unreleased 0.2 code. Stable registry packages may still be 0.1.11 and the Rust crate may not exist. For preview features use a reviewed checkout of https://github.com/arkadia-solutions/arkadia-data, verify its manifests say 0.2.0, then `pip install ./python`, build TypeScript with `npm --prefix typescript ci && npm --prefix typescript run build`, or `cargo install --path rust --locked`. Do not run the registry installation examples below for preview features; they describe the eventual stable release. Never publish or upload private data. Benchmark networking requires explicit `NETWORK=1` / `--allow-network`; encode/decode stays local.


# AK-DATA tools: install and use

AK-DATA (Arkadia Data Format) writes JSON data with a header that names each
field once and records that follow it by position. It is lossless and
typically ~50% smaller than pretty JSON for model context. This skill
installs the tools and uses them; for writing and reading the format itself
see the `ak-data-format` skill.

## 1. Install

The command **`ak-data`** is a single Rust binary:

```bash
cargo install arkadia-data               # from crates.io (needs Rust: https://rustup.rs)
# or from the repository: make install   # Homebrew local tap on macOS, else ~/.local/bin
```

Check: `ak-data --version`.

Libraries (same text in all three languages; no `ak-data` command in them):

```bash
pip install arkadia-data                 # Python ≥3.10 — import arkadia.data as akd
pip install "arkadia-data[bench]"        # + exact token counts (tiktoken) and TOON
npm install @arkadia/data                # Node / browsers — import { encode, decode } from '@arkadia/data'
cargo add arkadia-data                   # Rust — use arkadia_data as akd;
```

## 2. Use

| Task | Command |
|---|---|
| JSON → AK-DATA (compact, for prompts) | `ak-data read data.json -c -o data.akd` |
| Any file as readable AK-DATA | `ak-data read data.json` (or `ak-data data.json`) |
| AK-DATA → JSON | `ak-data read data.akd -t json` |
| Token count | `akd.count_tokens(text)` (Python, exact with `arkadia-data[bench]`) · `ak-data example` shows counts |
| AK-DATA → TOON | `ak-data read data.akd -t toon` |
| What changed / history | `ak-data diff old.json new.json` · `ak-data merge data.akd new.json -m "…" -o data.akd` · `ak-data history data.akd` |
| Prompt for a chat model | `ak-data prompt data.json -q "question" -f ak-data-compact -a "name:string,total:number"` |
| Same prompt in every format | `ak-data prompt data.json -q "question" --all-formats` |
| Ready examples (66) | `ak-data prompt --list` · `ak-data prompt --example 3 -f toon` |
| Format definition text | `akd.FORMAT_DEFINITION` / `HINT` (libraries) · `ak-data prompt` includes it |
| Full definition, coloured, every rule with an example | `ak-data info` · one section: `ak-data info grammar` |
| Random formatted example (+ prompt for AI) | `ak-data example` · `ak-data example --prompt` · `ak-data example 3 --prompt --raw` |

`read -t` accepts `akd`, `akd-compact`, `json`, `json-min`, `toon`.
Stdin works everywhere: `ak-data read - -c < result.json`.

In code:

```python
import arkadia.data as akd
text = akd.encode(data, {"compact": True})      # or akd.dumps(data)
data = akd.decode(text).node.dict()             # or akd.loads(text)
block = akd.to_prompt(data)                     # format hint + <data>…</data>
```

```ts
import { encode, decode } from '@arkadia/data';
const text = encode(data, { compact: true });
const back = decode(text).node.dict();
```

```rust
use arkadia_data as akd;
let text = akd::encode(&value);          // serde_json::Value → compact AK-DATA
let back = akd::decode(&text)?;          // → serde_json::Value
let json = akd::akd_to_json(&text, true)?;
```

Helper without the CLI: `python scripts/to_akd.py file.json` prints the
compact AK-DATA and the token change.

## 3. When to convert

- Convert JSON that a **model** will read and that has repeated structure
  (lists of records, logs, search results, rows) and is larger than ~300 tokens.
- Keep JSON for anything a **program** parses (APIs, MCP `structuredContent`).
- Put the format definition (`akd.FORMAT_DEFINITION`) once in the system prompt, not
  with every data block.
- Verify before relying on it: `ak-data read file.akd --strict` exits non-zero
  on invalid input; JSON → AK-DATA → JSON returns the original.
