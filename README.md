# AK-DATA — Arkadia Data Format

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

> **0.2.0 source preview.** Stable npm/PyPI packages are currently 0.1.11; the Rust crate is not yet published. Check the source revision and package manifests.

> **Lossless, schema-first data for LLMs and agents.** AK-DATA writes JSON
> data with a header that names each field once and records that follow it
> by position. On the bundled agent datasets it uses **55.9% fewer tokens
> than JSON and 14.1% fewer than TOON**, and decodes back to the exact
> original — including irregular, nested and mixed data.

| | Python | TypeScript / JavaScript | Rust |
|---|---|---|---|
| package | [`arkadia-data`](https://pypi.org/project/arkadia-data/) | [`@arkadia/data`](https://www.npmjs.com/package/@arkadia/data) | [`arkadia-data`](https://crates.io/crates/arkadia-data) |
| install | `pip install ./python` | build `typescript/` then install its local path | `cargo add arkadia-data --path /path/to/checkout/rust` |
| import | `import arkadia.data as akd` | `import { encode, decode } from '@arkadia/data'` | `use arkadia_data as akd;` |

The command line tool **`ak-data`** is the Rust program (`make install`, or
`cargo install arkadia-data`); the Python and npm packages are libraries.

Open source (MIT) · Python and npm without runtime dependencies · Rust: `serde_json` only.

```text
JSON (97 tokens)                          AK-DATA compact (55 tokens)
{                                         <tool:string,results:<[rank:number,title:string,
  "tool": "web_search",                     url:string,score:number]>>("web_search",
  "results": [                              [(1,"Agent memory in production",
    {"rank": 1, "title": "Agent memory      "https://example.org/a",0.97),
      in production", "url": ..., ...},     (2,"Token budgets","https://example.org/b",0.94)])
    ...
```

## Library

```python
import arkadia.data as akd

data = {"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]}

text = akd.encode(data, {"compact": True})   # <users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])
result = akd.decode(text)                     # node tree + errors + metadata
result.node.dict() == data                    # True — lossless

akd.dumps(data) / akd.loads(text)             # json-like shortcuts (loads raises AKDataError)
akd.to_prompt(data)                           # format hint + <data>…</data> for a prompt
akd.loads_any(model_reply)                    # model reply in JSON or AK-DATA, fences allowed
akd.FORMAT_DEFINITION                         # the definition to paste into any chat model
```

```ts
import { encode, decode } from '@arkadia/data';

const text = encode(data, { compact: true });
const { node, errors } = decode(text);
node.dict(); // same object back

// also: dumps, loads, loadsAny, toPrompt, buildPrompt, estimateTokens, FORMAT_DEFINITION
```

```rust
use arkadia_data as akd;

let text = akd::encode(&data);                  // compact; akd::encode_pretty for the readable form
let back = akd::decode(&text)?;                 // serde_json::Value, == data
let akd_text = akd::json_to_akd(json, true)?;   // text in, text out (e.g. in a daemon)
let json_text = akd::akd_to_json(&akd_text, false)?;
let toon = akd::convert(&akd_text, akd::Format::Toon)?;
```

All three write the same text and read each other's output. `make e2e`
compares the Rust binary with the Python package on every bundled dataset,
the examples, the TOON spec fixtures and 500 random documents (AK-DATA
compact and readable, TOON, decoding); the test suites add seeded random
round-trips. The one difference is JavaScript itself: it writes `199.0` as
`199` and puts integer-like keys (`"0"`) first.

## `ak-data` command (Rust)

```bash
make install                  # build + install: Homebrew (local tap arkadia/local) or ~/.local/bin
cargo install --path rust --locked  # from the preview checkout
```

| command | |
|---|---|
| *(none)* = `read` | a file, text (`'{…}'`, `'```…```'`) or stdin as readable, coloured AK-DATA. `-i json\|akd` how to read the input, `-t akd\|akd-compact\|json\|json-min\|toon` the output type (default AK-DATA), `-o file`, `-c` one line |
| `read` | any file (JSON or AK-DATA) as AK-DATA: laid out, or one line with `-c`; `-t json\|json-min\|toon\|akd-compact` converts. AK-DATA input keeps its comments, attributes and history; `--sizes[=n]`, `--no-types`, `--no-schema`, `--prompt-output`, `--no-comments`, `--no-attributes`, `--width`, `--strict`, `-o`. `ak-data FILE` = `ak-data read FILE` |
| `prompt` | copy-paste prompt for ChatGPT / Gemini / Claude (`-q`, `-f`, `-a`, `--answer-name`, `--example`, `--list`, `--all-formats`, `--no-definition`, `--expected`, `--attributes`, `--comments`, `--meta`, `-o`) |
| `diff` | `ak-data diff OLD NEW`: the changes as a patch — a change set (id, date, author, title, changes), coloured AK-DATA; `-o fix.akd` saves it for `apply` (`-t json`, `-m`, `--author`, `--description`, `--exit-code`). `--info`: the paths and the changes in place with context like `git diff` (`-U n`, `--full`, `--paths`). OLD / NEW: files, text, or two documents on stdin |
| `merge` | `ak-data merge OLD NEW`: NEW joined into OLD, the change recorded in the history `$changes` (`--latest`: NEW as it is; `-m`, `--author`, `--description`, `--no-history`) |
| `apply` | `ak-data apply FILE PATCH`: apply a patch or entries of another history, FILE updated in place (`--change id`, `-R` undo, `--no-history`, `--force`, `--dry-run`, `-o`, `--stdout`) |
| `history` | `ak-data history FILE`: who changed what and when, like `git log` (`--oneline`, `-p`, `--path`, `--author`, `--change`, `-n`) |
| `example` | a random example, laid out and coloured (`--prompt`: with a copy-paste prompt for AI and the expected answer; `--raw`, `--list`, `--json`) |
| `info` | the complete format definition, coloured, every example decoded live (`ak-data info grammar`: one section) |

`enc`, `dec`, `fmt`, `hint` and `stats` from earlier versions were removed:
`ak-data` (= `read`) does what `enc`, `dec` and `fmt` did; the definition is
`FORMAT_DEFINITION` in the libraries, token counts are in `ak-data example`
and `make benchmark`. `ak-data` is the only command line tool — the Python
and npm packages are libraries.

In the shell, text goes in single quotes:

```bash
echo '{"users":[{"id":1,"name":"Ada"}]}' | ak-data -c     # <users:<[id:number,name:string]>>([(1,"Ada")])
ak-data '<a:number>(1)' -t json                           # text works like a file
echo '{"a":1,"b":2} {"a":1,"b":3}' | ak-data diff         # two documents, one after the other
ak-data diff '<n:number>(1)' '<n:number>(2)'              # or two texts
```

```bash
ak-data data.json                                 # readable AK-DATA (= ak-data read data.json)
ak-data data.json -c -o data.akd                  # one line, for prompts
ak-data data.akd -t json                          # back to JSON (-t toon, json-min)
ak-data diff old.json new.json                    # the changes as a patch (--info: in context)
ak-data merge data.akd new.json -m "Prices 2027" -o data.akd   # join, record the change
ak-data merge data.akd export.json --latest -o data.akd        # newest as it is + the change
ak-data diff old.json new.json -m "Fix" -o fix.akd && ak-data apply data.akd fix.akd
ak-data apply data.akd data.akd --change 3f2a1c -R             # undo one change
ak-data history data.akd                          # like git log (--oneline, -p, --path users)
ak-data prompt data.json -q "Which service has the most errors?" -f ak-data-compact -a "service:string,errors:number"
ak-data prompt --example 3 --format toon          # 66 bundled examples: ak-data prompt --list
ak-data prompt --example 11 --meta                # … with its attributes and comments
ak-data example --prompt                          # random example + prompt for AI
ak-data info                                      # the whole definition
```

**History without a new structure.** `merge` and `apply` keep the data as it
is and write the history after it as the attribute `$changes` — metadata, so
`ak-data -t json`, `loads` and every decoder still give exactly the data:

```text
<n:number,users:<[id:number,name:string]>>(2,[(1,"Ada"),(2,"Alan T.")])
// $changes=<[id:string,date:string,author:string,title:string,description:string,changes:<[op:string,path:string,old:string,new:string]>]>[("a1b2c3d4e5","2026-11-01T09:00:00Z","Ada","Rename Alan",null,[("change","users[id=2].name","Alan","Alan T.")])] //
```

Each change is `(op, path, old, new)`: `add`, `remove`, `change`, or `order`
(a list of records got a new order). Lists of records are matched by `id` /
`key` / `name` / `slug` / `sku` / `code` / `uuid` (or the first field), so
paths read `users[id=2].name`. Ids are short hashes chained like commits.

The same in the libraries (identical results, checked against shared
fixtures in all three test suites):

```python
from arkadia.data import diff
changes = diff.diff(old, new)                 # [Change(op, path, old, new), …]
diff.apply(old, changes) == new               # ConflictError if a change does not fit
diff.apply(new, diff.reverse(changes)) == old
text = diff.commit(text, new, title="Rename Alan", author="Ada")   # data + $changes
diff.history(text)                            # [ChangeSet(id, date, author, title, …)]
```

```ts
import { diff } from '@arkadia/data';
const changes = diff.diff(oldData, newData);
diff.apply(oldData, changes);                 // throws ConflictError if a change does not fit
const text2 = diff.commit(text, newData, { title: 'Rename Alan', author: 'Ada' });
diff.history(text2);                          // [{ id, date, author, title, description, changes }]
```

```rust
use arkadia_data::diff::{self, ChangeSet, Info};
let changes = diff::diff(&old, &new);
let back = diff::apply(&old, &changes)?;      // Err(conflicts) if a change does not fit
let set = ChangeSet::new(changes, &Info { title: Some("Rename Alan".into()), ..Info::default() }, None);
let text = diff::with_history(&new, &[set]);  // data + // $changes=… //
diff::history(&text);
```

`read -t` accepts `akd`, `akd-compact`, `json`, `json-min`, `toon`; TOON is
built in. Benchmarks are not part of `ak-data`; they run from the
repository with `make benchmark` (see below).

## Copy-paste examples

[`examples/prompts/`](examples/prompts/) has 66 prompts: 51 real-size ones — HR, invoices, logs,
flights, servers, a search tool result, recipes, CI runs, email extraction and
more — and 15 feature examples, each showing one part of the format (named
types, overrides, irregular records, metadata …). The website, `ak-data
example` and `ak-data prompt --example N` use this same set. Each prompt is in
JSON, TOON, AK-DATA and AK-DATA COMPACT, with the format
definition included and the expected answer computed from the data. Paste one
into ChatGPT, Gemini or Claude and compare. In 45 of 51 the AK-DATA COMPACT
prompt is smaller than JSON (median −28%, up to −57%); the exceptions are
small or mostly free-text prompts where the format definition dominates.
On these small datasets TOON is often a little smaller than AK-DATA, partly
because its definition is shorter.

45 examples carry **metadata** — units, status codes, test records — written
both as `$attributes`/`#tags` and as `/* comments */` (JSON and TOON get the same
facts as notes above the data). Every prompt can be built with either, both or
none: `ak-data prompt --example 11 --format toon --attributes --comments`. In 25
of them (*needs metadata*) the question cannot be answered correctly without
it. Metadata costs a median of +9% prompt tokens. The `/akdata` page shows the
same examples with a format switch and Attributes / Comments toggles.

## Benchmark

Without `--dir` the benchmark runs on eight bundled datasets that model what
agents move around. Each format is encoded, decoded and compared with the
original, so the table also shows whether a format is lossless.

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

Tokens counted with `o200k_base`; `cl100k_base` gives the same picture
(−55.9% vs JSON, −13.7% vs TOON). Full reports: [`benchmarks/`](benchmarks).
Where AK-DATA does *not* win: a single irregular object (minified JSON is
smaller) and text-heavy records (TOON's unquoted strings are up to 2%
smaller). On TOON's own spec fixtures AK-DATA compact is 43.6% below JSON
and 24% below TOON.

The AI benchmark (`make benchmark`) generates questions with known
answers from the bundled datasets and from 24 randomly generated ones (flat,
wide, nested, irregular, multi-table, configuration and list-of-numbers
shapes; `RANDOM=…`, `SEED=…`) — about 470 questions per format: lookups,
positions, nested paths, counts with one or two conditions, maxima and
minima, filters, sums, optional fields, list lengths. It asks a model with
the data in each format, scores exactly and reports accuracy with its 95%
confidence interval, prompt tokens and correct answers per 10k tokens;
`TRIALS=3` repeats every prompt, `--write` also checks that the model can
produce each format. AK-DATA is compared compact, compact with list sizes
(`$size`) and readable with list sizes.

## Syntax in one minute

| You write | Means |
|---|---|
| `<id:number,name:string>(1,"Ada")` | record; values follow the header order |
| `<[id:number,tags:[string]]>[(1,["a"]),(2,[])]` | list of records sharing one header |
| `{id:1,name:"Ada"}` | record with names (no header needed) |
| `<any> {…}` | a value whose shape differs from the header |
| `<string> "12"` | a value whose type differs from the header |
| `` `x y` `` | identifier with spaces or symbols |
| `/* note */`, `$attr=1`, `#tag` | comments and metadata for the reader, not data |
| `@User<id:number>` | named type, reusable as `@User(1)` |

The definition for prompts (`akd.FORMAT_DEFINITION`, ~150 tokens):

```text
AK-DATA (Arkadia Data Format): <a:type,b:type> is a header; (v1,v2) is a record whose values follow the header order.
<[a:type,...]>[(...),(...)] is a list of records sharing that header; headers nest, e.g. items:<[sku:string,qty:number]>.
{key:value} is a record with names; <type> or <any> before a value overrides the header type.
Strings are quoted; numbers, true, false, null as in JSON; /*...*/, $attr, #tag are metadata, not data.
A record with fewer values than its header has only the first fields; //$size=N// before list items is their count.
```

## Skills for agents

- [`skills/ak-data-install`](skills/ak-data-install/SKILL.md) — installs the
  `ak-data` command (Rust) and the libraries (`arkadia-data` / `@arkadia/data`)
  and uses them to convert, count tokens and build prompts.
- [`skills/ak-data-format`](skills/ak-data-format/SKILL.md) — the format
  itself: step-by-step procedures to read AK-DATA and to write answers in it,
  the full syntax, a checklist of common mistakes, and a reference generated
  from `ak-data info` and `ak-data example` (`reference/`). Needs no
  installation. `make skill` regenerates the reference.

Both work in agents that read `SKILL.md` (Claude Code, Codex CLI, GitHub
Copilot, Gemini CLI, Cursor and others): copy the folder into the agent's
skills directory, e.g. `~/.claude/skills/`.

## Layout

```
python/       arkadia-data: arkadia.data (format), arkadia.bench (benchmarks), tests, datasets
typescript/   @arkadia/data: library
rust/         arkadia-data crate: library + the ak-data command, compat check against Python
examples/     copy-paste prompts in JSON, TOON, AK-DATA, AK-DATA COMPACT
skills/       ak-data-install and ak-data-format
benchmarks/   reports produced by `make benchmark`
```

## Development, benchmarks and the HTML report (Makefile)

Requires [uv](https://docs.astral.sh/uv/), Node.js and Rust (cargo). `make` shows the colored
guide. Linters and formatters: ruff (Python), Biome (TypeScript), rustfmt + clippy (Rust).

```bash
make prepare                         # uv sync + npm ci + cargo fetch            (prepare-py / -ts / -rs)
make update                          # next minor version (./VERSION → Cargo.toml, pyproject.toml, package.json)
make version                         # check that all three packages use ./VERSION
make build                           # python/dist, typescript/dist, rust release (build-py / -ts / -rs)
make install                         # build + install the ak-data program (brew, else ~/.local/bin; METHOD=prefix PREFIX=…)
make uninstall
make test                            # pytest + vitest + cargo test             (test-py / -ts / -rs)
make e2e                             # format + lint + tests + builds + installed packages + Rust = Python
make skill                           # skill reference from ak-data (skills/ak-data-format/reference)
make examples                        # 66 examples (51 real-size + 15 features) → ak-data, website, examples/prompts
make clean                           # build outputs, caches, reports/

make benchmark                       # tokens → AI → reports/report.html (one run, all steps)
                                     #   + benchmarks/benchmark.json (numbers for the website)
make benchmark ONLY_SHOW=1           # only print the prompt of every test (--only-show)
make benchmark DIR=~/my-json         # … on your own JSON files
make benchmark NETWORK=1 MODEL=gpt-5.4-mini    # OPENAI_API_KEY / ANTHROPIC_API_KEY (or python/.env)
make benchmark NETWORK=1 MODEL=gpt-5.4-mini REASONING=low RANDOM=48 TRIALS=3
make benchmark PROVIDER=ollama MODEL=qwen3:8b
make benchmark NETWORK=1 MODEL=gpt-5.4-mini,claude-haiku-5-5 ARGS="--write --lang pl"
```

`make benchmark` runs `python -m arkadia.bench` from `python/` (the
benchmarks live in the repository, not in the `ak-data` command): the token /
speed / fidelity benchmark for o200k_base and cl100k_base, then the AI
benchmark (a dry run with prompt sizes when no model is configured), then one
self-contained HTML page (charts, per-dataset tables, timing, fidelity,
accuracy per format and question type, wrong answers) with a summary written
by the model, or computed from the numbers — the report states which. All
flags: `cd python && uv run python -m arkadia.bench --help`.

The run also includes the **metadata benchmark**: four annotated datasets in
six variants (JSON, JSON + notes, AK-DATA without metadata, with
`/* comments */`, with `$attributes`/`#tags`, with both) and questions of which
some can only be answered with the metadata — what a status code means, a
unit, which records are tests. It reports accuracy on both kinds of questions
and the token price of each variant (`reports/meta-<model>.json`; `--no-meta`
skips it). The same data are copy-paste examples 48–51 in [`examples/prompts/`](examples/prompts/).

**Every test, by hand.** Each AI report keeps the exact prompt, the
model's raw reply and the answer to every question. `reports/report.html`
lists them under "Every test", and `make benchmark` exports them to
`benchmarks/runs/` for the website's `/akdata/runs` page (filter by format,
question type and result; open a question for its prompt and the reply).
`make benchmark-runs` exports the runs already in `reports/`.

**What to improve next.** `make analyze` reads the newest
`reports/ai-*.json` and shows (1) accuracy with its 95% interval, (2) a
paired comparison with JSON — questions one format got right and the other
wrong, with an exact McNemar p-value (below 0.05 the difference is real,
above it is noise), (3) accuracy per question type and per dataset next to
JSON, and (4) every question JSON answered and AK-DATA did not, with the
expected and the given answer. Change the encoder or the format definition
for the weakest type, re-run `make benchmark NETWORK=1 MODEL=…` with the same
`SEED`, and keep the change only if the paired comparison improves.
`FORMAT=akcd-n` lists the misses of another variant, `VS=toon` compares
with TOON.

On the bundled datasets the run also writes the numbers for the website to
`benchmarks/benchmark.json` — totals, per-dataset tables for both
tokenizers, prompt sizes and, after a run with a model, accuracy per format.
Results of real models are kept across runs; `DIR=…` runs never touch the
file. The website copies it (and the examples and skills) itself.

License: MIT © Arkadia Solutions


## Preview 0.2.0 and network boundary

0.2.0 is a source preview until the release checklist passes and registry installs are verified. Registry packages may still be 0.1.x. For this preview, clone https://github.com/arkadia-solutions/arkadia-data and install from the relevant subdirectory: `pip install ./python`, `npm install ./typescript` after building it, or `cargo install --path rust --locked`. Do not assume `cargo install arkadia-data` is available before the crate is published.

`make benchmark` is offline by default, even if API keys exist in the environment or `.env`. Explicitly use `make benchmark NETWORK=1 MODEL=...` (CLI: `--allow-network`) to send the selected datasets to a provider. Local/remote Ollama also requires this opt-in. The provider host, model and data source are printed before requests. Reports may contain data, prompts, answers and local paths; they are private by default. `--offline` and `--allow-network` are mutually exclusive. Ordinary encode/decode operations do not call models.


Security reports: [SECURITY.md](SECURITY.md). Development: [CONTRIBUTING.md](CONTRIBUTING.md). Semantic round-trip is not byte-for-byte JSON preservation: whitespace, number spelling and key enumeration may differ; keep exact large integers as strings before entering JavaScript. Metadata is untrusted content, not authorization for an agent.
