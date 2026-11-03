# AK-DATA — Arkadia Data Format

[![CI](https://github.com/arkadia-solutions/arkadia-data/actions/workflows/ci.yml/badge.svg)](https://github.com/arkadia-solutions/arkadia-data/actions/workflows/ci.yml)
[![version 0.3.0](https://img.shields.io/badge/version-0.3.0-2ea44f)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f)](LICENCE)
<!-- After publishing to the registries:
[![npm](https://img.shields.io/npm/v/@arkadia/data.svg)](https://www.npmjs.com/package/@arkadia/data)
[![PyPI](https://img.shields.io/pypi/v/arkadia-data.svg)](https://pypi.org/project/arkadia-data/)
[![crates.io](https://img.shields.io/crates/v/arkadia-data.svg)](https://crates.io/crates/arkadia-data)
-->

```text
                                   ; i  :J                                      
                               U, .j..fraaM.  nl                                
                            b h.obWMkkWWMMWMCdkvz,k                             
                         ! .mQWM:o hiMoMW v.uaXMdohbi                           
                        hI,MMmaIao.Wo .IMkoh FCMwqoXa                           
                      ,.c.aWdM. d,aToW  .    Mb!. MopfQ.L                       
                       jhj.xoM :k    aCu F: w MpmqMvMMI,I                       
                      bzMhz:W    .Mw . o lYh ai M iMa pM.j                      
                     hzqWWM;    M;o.WMWWMkMX f.a aa bModpo.                     
                     ;tMbbv   xp oJMMWWWWMMMM iv  dLMXakM:T                     
                       mdh        MMWWWWWWWbQLCzurjktvMor                       
                      ,QFw ;M,b .MWWWWWWWMWMWd  xz   M,kd X                     
                      qjMIo IMTW.WWWWWMWWWM.o.I   rpULaMdi.                     
                       .mMM  uoWWWMWWWWWWp qM,,M l M;mMbrI                      
                        f nm  MMW MWWjMuMj  I  o   LbMac                        
                              WWdMWWWW Mv a.b..aauMhMwQf                        
                              MoWWW,WWtjonJMWtoMdoaoMI                          
                              MMMM Mi    xd:Mm tMwo Cr,                         
                             xMMc .otqokWMMMao:oio.                             
                             MW    .   C..MkTIo                                 
                            WW                                                  
                           QWM                                                  
                           WW                                                   
                          uMW                                                   
                          WW                                                    
                          MW
```

**AK-DATA** is a compact, lossless text form of JSON data for language models.
A header names every field once — with its type — and the records follow by
position, also nested records and lists.

Think of it as a translation layer: programs keep JSON, the model reads
AK-DATA, and the conversion goes both ways without losing anything. On the
bundled agent datasets compact AK-DATA uses **55.9% fewer tokens than JSON**
and **14.1% fewer than TOON**.

> [!TIP]
> Try it in the browser, no install needed: [arkadia.solutions/akdata](https://arkadia.solutions/akdata) —
> paste your JSON and compare the sizes.

## Table of Contents

- [Why AK-DATA?](#why-ak-data)
- [Key Features](#key-features)
- [When Not to Use AK-DATA](#when-not-to-use-ak-data)
- [Benchmarks](#benchmarks)
- [Installation & Quick Start](#installation--quick-start)
- [CLI](#cli)
- [Changes and History](#changes-and-history)
- [Using AK-DATA with LLMs](#using-ak-data-with-llms)
- [Syntax in One Minute](#syntax-in-one-minute)
- [Documentation](#documentation)
- [What's New in 0.3.0](#whats-new-in-030)

## Why AK-DATA?

**Tokens cost money, and JSON spends many of them on repeating keys.** Three
orders with a nested customer and a list of items, in AK-DATA:

```text
<orders:<[
  id:string,
  customer:<name:string, city:string>,
  items:<[sku:string, qty:number]>,
  total:number,
  paid:bool
]>>
([
  ("ORD-1001", ("Ada", "Kraków"), [("PEN", 2), ("INK", 1)], 19.5, true),
  ("ORD-1002", ("Alan", "Gdańsk"), [("PAD", 3)], 12.0, false),
  ("ORD-1003", ("Grace", "Poznań"), [("PEN", 5), ("PAD", 1)], 31.25, true)
])
```

| format | tokens (o200k_base) |
|---|---:|
| JSON (indented) | 257 |
| JSON (minified) | 137 |
| TOON | 139 |
| **AK-DATA compact** (the same text on one line) | **105** |

- `<…>` is a **header**: field names and types, written once.
- `(…)` is a **record**: values in the order of the header.
- `[…]` is a **list**; `<[…]>` declares the header of every element — the
  nested `customer` and `items` too, so nested data stays positional.

A value that does not fit its header carries its own type or names
(`<string> "12"`, `<any> {…}`), so irregular data round-trips exactly.

## Key Features

- 📉 **Fewer tokens**: headers once per list, also for nested records and lists.
- 🔁 **Lossless**: JSON → AK-DATA → JSON returns the original — key order, empty keys, nested, mixed and irregular lists.
- 🧭 **Schema first**: the model sees the shape and the types before the values.
- 🏷️ **Metadata for the model**: `/* comments */`, `$attributes` and `#tags` that decoders skip.
- 🔢 **List sizes**: `//$size=N//` so models need not count.
- 🕘 **History in the document**: changes with author, date and title, stored as metadata (`ak-data diff | merge | history`).
- 🌐 **Three implementations, one output**: Python, TypeScript / JavaScript and Rust write the same text, checked against shared fixtures.

## When Not to Use AK-DATA

- **Programs** (APIs, `structuredContent`, files other tools read): keep JSON — AK-DATA is for the model.
- **A single small or irregular object**: minified JSON is often as small, and the format definition costs tokens.
- **Text-heavy records**: savings shrink; TOON's unquoted strings can be a little smaller.
- **Arithmetic over many rows** (sums, filters, counts): no format makes a model good at it — compute these with code.

## Benchmarks

### Tokens

Eight bundled datasets shaped like agent payloads, `o200k_base` tokens:

| dataset | JSON | JSON min | YAML | TOON | AK-DATA | AK-DATA compact |
|---|---:|---:|---:|---:|---:|---:|
| analytics | 4,858 | 3,141 | 3,858 | 2,071 | 2,352 | **1,991** |
| config | 279 | **152** | 193 | 182 | 197 | 168 |
| employees | 7,535 | 4,831 | 5,751 | 3,228 | 3,858 | **3,155** |
| logs | 9,215 | 5,911 | 7,091 | 4,122 | 4,732 | **3,980** |
| orders | 7,242 | 4,167 | 5,230 | 3,930 | 3,204 | **2,619** |
| rag-chunks | 2,351 | 1,913 | 2,264 | **1,656** | 1,788 | 1,689 |
| repositories | 3,568 | 2,083 | 2,605 | 2,507 | 1,618 | **1,358** |
| tool-results | 2,599 | 1,956 | 2,283 | **1,636** | 1,771 | 1,647 |
| **total** | 37,647 | 24,154 | 29,275 | 19,332 | 19,520 | **16,607** |
| vs JSON | – | −35.8% | −22.2% | −48.6% | −48.1% | **−55.9%** |

### Do models still understand it?

`gpt-5.4-mini`, two identical runs of 474 questions with known answers
(lookups, positions, nested paths, counts, maxima, filters, sums, list
lengths) over the bundled and 24 generated datasets:

| format | accuracy | 95% interval | prompt tokens | correct / 10k tokens |
|---|---:|---:|---:|---:|
| JSON (indented) | 74.9% | 72.0–77.6% | 134,982 | 26.3 |
| YAML | 73.8% | 70.9–76.5% | 105,545 | 33.2 |
| TOON | 73.1% | 70.2–75.8% | 76,107 | 45.5 |
| AK-DATA compact | 74.3% | 71.4–76.9% | 65,684 | 53.6 |
| **AK-DATA compact + list sizes** | **76.8%** | 74.0–79.4% | 66,566 | **54.7** |
| AK-DATA readable + list sizes | 73.8% | 70.9–76.5% | 81,168 | 43.1 |

> [!NOTE]
> AK-DATA compact is as accurate as JSON (no significant difference, paired
> McNemar test) with half the prompt tokens; list sizes help (p = 0.024 against
> plain compact). One model, two runs — differences of 2–3 points are within the
> run-to-run noise. Every prompt, reply and the code that computes each right
> answer: [arkadia.solutions/akdata/runs](https://arkadia.solutions/akdata/runs) ·
> the analysis: [the article](https://arkadia.solutions/articles/ak-data).

## Installation & Quick Start

| | Python | TypeScript / JavaScript | Rust |
|---|---|---|---|
| install | `pip install arkadia-data` | `npm install @arkadia/data` | `cargo add arkadia-data` |
| import | `import arkadia.data as akd` | `import { encode, decode } from '@arkadia/data'` | `use arkadia_data as akd;` |

Python and npm have no runtime dependencies; Rust needs only `serde_json`.

```python
import arkadia.data as akd

data = {"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]}
text = akd.dumps(data)        # <users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])
akd.loads(text) == data       # True
akd.loads_any(model_reply)    # a model reply in JSON or AK-DATA
akd.to_prompt(data)           # the format definition + <data>…</data>
```

```ts
import { dumps, loads, loadsAny } from '@arkadia/data';

const text = dumps({ users: [{ id: 1, name: 'Ada' }] }); // <users:<[id:number,name:string]>>([(1,"Ada")])
loads(text); // { users: [{ id: 1, name: 'Ada' }] }
```

```rust
use arkadia_data as akd;

let text = akd::encode(&data);   // compact; akd::encode_pretty for the readable form
let back = akd::decode(&text)?;  // serde_json::Value, equal to data
```

## CLI

`ak-data` is one program for macOS, Linux and Windows:

```bash
brew install arkadia-solutions/tap/ak-data     # macOS / Linux
cargo install arkadia-data                     # any system with Rust
```

…or download it from [GitHub Releases](https://github.com/arkadia-solutions/arkadia-data/releases)
(macOS: signed and notarized; checksums in `SHA256SUMS`).

Without a command it reads a file, text or stdin and shows it as readable,
coloured AK-DATA:

```bash
ak-data data.json                                   # readable AK-DATA
echo '{"users":[{"id":1,"name":"Ada"}]}' | ak-data -c
# <users:<[id:number,name:string]>>([(1,"Ada")])
ak-data data.akd -t json                            # back to JSON (-t json-min, toon)
ak-data data.json -c --sizes=4 -o data.akd          # the prompt form, to a file
```

| command | |
|---|---|
| `ak-data [file]` | read: AK-DATA, laid out (`-c`: one line); `-t` output type, `-i` input type, `-o` file |
| `ak-data diff OLD NEW` | the changes as a patch (`--info`: in place, like `git diff`) |
| `ak-data merge OLD NEW` | join a newer document and record the change |
| `ak-data apply DATA PATCH` | apply a patch or history entries (`-R`: undo) |
| `ak-data history FILE` | who changed what and when, like `git log` |
| `ak-data prompt [file]` | a copy-paste prompt for ChatGPT / Gemini / Claude |
| `ak-data example` | the 66 bundled examples (`--prompt`: with a prompt for AI) |
| `ak-data info` | the complete format definition, every example decoded |

Every command has `--help` with small examples and their output.

## Changes and History

```bash
echo '{"a":1,"b":2} {"a":1,"b":3}' | ak-data diff --info
ak-data merge data.akd update.json -m "Prices 2027" -o data.akd
ak-data history data.akd --oneline
```

`merge` and `apply` keep the data as it is and write the history after it as
the attribute `$changes` — metadata, so every decoder still returns exactly the
data. Each change is `(op, path, old, new)` with paths like `users[id=2].name`.
The same in the libraries:

```python
from arkadia.data import diff

changes = diff.diff(old, new)        # [Change(op='change', path='users[id=2].name', …)]
diff.apply(old, changes) == new      # ConflictError when a change does not fit
text = diff.commit(text, new, title="Rename Alan", author="Ada")
diff.history(text)                   # [ChangeSet(id, date, author, title, …)]
```

`diff.diff`, `diff.apply`, `diff.reverse`, `diff.commit` and `diff.history`
exist in `@arkadia/data` and in `arkadia_data::diff` as well.

## Using AK-DATA with LLMs

- Put the format definition once in the system prompt (`akd.FORMAT_DEFINITION`, about 150 tokens) and the data in compact form with list sizes.
- To get AK-DATA back, give the header to fill: *Answer in AK-DATA only, with exactly this header: `<result:<[name:string,total:number]>>`*.
- Read the reply with `loads_any` / `loadsAny` — JSON or AK-DATA, code fences allowed.
- Agent skills: [`ak-data-format`](skills/ak-data-format/SKILL.md) teaches an agent to read and write AK-DATA; [`ak-data-install`](skills/ak-data-install/SKILL.md) sets up the tools. Copy a folder into the agent's skills directory (e.g. `~/.claude/skills/`).
- 66 ready prompts in JSON, TOON and AK-DATA, with the expected answers: [`examples/prompts/`](examples/prompts/) or `ak-data example --prompt`.

## Syntax in One Minute

| You write | Means |
|---|---|
| `<id:number,name:string>(1,"Ada")` | record; values follow the header order |
| `<[id:number,tags:[string]]>[(1,["a"]),(2,[])]` | list of records sharing one header |
| `{id:1,name:"Ada"}` | record with names (no header needed) |
| `<any> {…}` | a value whose shape differs from the header |
| `<string> "12"` | a value whose type differs from the header |
| `` `x y` `` | a name with spaces or symbols |
| `/* note */`, `$attr=1`, `#tag` | comments and metadata for the reader, not data |
| `@User<id:number>` | a named type, reusable as `@User(1)` |

## Documentation

- `ak-data info` — the complete definition with the grammar; every example decoded live.
- [arkadia.solutions/akdata](https://arkadia.solutions/akdata) — playground, syntax, examples, benchmarks.
- Files use the extension `.akd` (or `.ak-data`); in Markdown, fence AK-DATA as `` ```akd ``.

## What's New in 0.3.0

- `ak-data` reads without a command — a file, text or stdin; `-t`, `-i`, `-o`.
- Changes and history: `diff`, `merge`, `apply`, `history` in the CLI and in all three libraries.
- Structured attribute values (`$changes=[…]`), records with optional fields under one header, list sizes.
- Ready-made `ak-data` for macOS (signed and notarized), Linux and Windows; Homebrew.
- `enc`, `dec`, `fmt`, `hint` and `stats` are now `ak-data` itself; the Python and npm packages are libraries only.

All changes: [CHANGELOG.md](CHANGELOG.md).

## Contributing, Security, License

Development and benchmarks: [CONTRIBUTING.md](CONTRIBUTING.md) · security
reports: [SECURITY.md](SECURITY.md) · [MIT](LICENCE) © Arkadia Solutions
