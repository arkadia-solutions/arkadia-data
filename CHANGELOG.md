# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]

## [0.3.1] - 2026-11-03

### Added
* **npm and PyPI from the release tag**: after the GitHub Release the
  workflow publishes `@arkadia/data` (npm, with provenance) and
  `arkadia-data` (PyPI), next to crates.io and Homebrew. Secrets:
  `NPM_TOKEN`, `PYPI_API_TOKEN` (or PyPI trusted publishing with the
  repository variable `PYPI_TRUSTED_PUBLISHING=true`). A version already in
  a registry is skipped.

### Fixed
* Windows release build: `VERSION` was read with `\r` (`.gitattributes` was
  not committed); the scripts now read it without `tr`.
* GitHub Release upload timed out (504) with all files in one request; files
  are uploaded one by one with retries.
* The TypeScript formatter rewrote the shared test vectors; `tests/fixtures`
  is excluded and `check_release.py` also compares `diff.json`.

## [0.3.0] - 2026-11-03

### Fixed
* Reports of models with a dot in their name were written under a cut name
  (`gpt-5.4-mini` → `ai-bundled-gpt-5.json`).
* The readable layout puts a comment in front of a field or list item on its
  own line (Rust `layout::pretty`, npm `pretty`).
* Decoding text with an unclosed `// … //` meta block that contains a digit
  (e.g. typing `//` inside a header: `<a:number //>(1)`) never finished in
  Python and TypeScript. Found by fuzzing all three decoders.
* A named type used by two sibling fields (`<start:@Point,end:@Point>`) lost
  all but the last field when decoding — in Python, TypeScript and Rust. Each
  field now gets its own copy of the named header.

### Changed
* **Records with optional fields share one header.** A list whose records
  have different keys gets a header with every field (the most frequent
  first) when that lets more records be positional than the most common
  exact layout; a record with only the first k fields is written with k
  values (`<[id,name,email]>[(1,"Ada","a@x"),(2,"Alan")]`) instead of
  `<any> {…}`. Same output in Python, npm and Rust; decoders already read it.
* **The format definition** (`FORMAT_DEFINITION`, `HINT`, `ak-data hint`)
  says that a record with fewer values has only the first fields and that
  `//$size=N//` is the number of items of a list.
* **AI benchmark**: questions from the bundled datasets plus generated ones
  (`--random N`, `--seed`; `make benchmark` uses `RANDOM=24` → about 470
  questions per format instead of 81), new question types (position, count
  with two conditions, minimum, filter, sums, values in lists, nulls,
  optional fields, deeper nested paths), accuracy with its 95% confidence
  interval, `--trials N` (every prompt N times), the format definition for
  TOON too (`--hint all`, default), AK-DATA compared compact, compact with
  sizes and readable with sizes (`akcd-n`, `akd-n`). The readable `akd`
  format is now `ak-data fmt` (one record per line).
* Default OpenAI model of the benchmark: `gpt-5.4-mini`; GPT-5 / o-series
  models get `max_completion_tokens` and optional `reasoning_effort`
  (`--reasoning`, `REASONING=low`) instead of `temperature`.
* `make skill`, `make examples` and `make benchmark` no longer copy anything
  to `../arkadia-landing` (`LANDING` removed).
* **`ak-data` looks like the earlier Python `akd` again**: the logo, the
  "ARKADIA DATA TOOL" banner with version and metadata, colored USAGE /
  COMMANDS / OPTIONS sections, a help screen per command
  (`ak-data enc --help`, `ak-data help dec`), a colored `stats` table with the
  savings, red errors, highlighted `enc` output in a terminal. Colors only in a
  terminal; `--no-color` / `NO_COLOR` / `--color`. `akd` is installed as a
  short name for `ak-data`.

### Added
* **Releases from a tag**: `git push origin v0.3.0` runs
  `.github/workflows/release.yml` — `ak-data` for macOS (universal binary,
  signed with the Developer ID certificate and notarized; with an installer
  certificate also a stapled `.pkg`), Linux (x86_64, arm64, static) and
  Windows, a GitHub Release with the archives, `SHA256SUMS` and these notes,
  the Homebrew formula in `arkadia-solutions/homebrew-tap`
  (`brew install arkadia-solutions/tap/ak-data`) and the crate on crates.io.
  The same build locally: `make release` (`scripts/release.sh`; secrets from
  the keychain or `.env`, names in `.env.example`), `make homebrew-formula`.
* **One version for all three packages**: `./VERSION`. `make update` raises
  the minor version (0.2.0 → 0.3.0) and writes it into `Cargo.toml` /
  `Cargo.lock`, `pyproject.toml` / `__version__` / `uv.lock` and
  `package.json` / `package-lock.json`; `make build` takes it from there,
  `make version` checks that all packages use it.
* **`ak-data` reads without a command**: `ak-data data.json`,
  `echo '{…}' | ak-data`, `ak-data '{…}'` or `ak-data '```…```'` show the
  input as readable, coloured AK-DATA. `-i json|akd` says how to read the
  input, `-t akd|akd-compact|json|json-min|toon` the output type (default
  AK-DATA), `-o` the file, `-c` one line. `read` is the same as a command.
  AK-DATA input keeps its comments, attributes and history; encoder options
  (`--sizes`, `--no-types`, `--no-schema`, `--prompt-output`) encode it
  again. Every command takes files, text or stdin;
  `diff`, `merge` and `apply` also two documents in one text or on stdin
  (`echo '{"a":1} {"a":2}' | ak-data diff`).
* `ak-data diff` writes the changes as a patch: a change set (id, date,
  author, title, changes) as coloured AK-DATA — what `-o` saves for
  `ak-data apply` (`-t json`, `-c`). `--info` shows them for people: the
  paths, the changes in place with context and the history entries.
* The help of every command starts with quick examples on small text input,
  with their real output (run when the help is shown).
* Removed `ak-data hint` and `ak-data stats` (the definition:
  `FORMAT_DEFINITION` in the libraries; token counts: `ak-data example`,
  `make benchmark`). Removed `enc`, `dec` and `fmt` too: `ak-data` does it all.
* `ak-data` is the only command line tool: the npm package no longer has a
  CLI (`src/cli`), and the `akd` short name is not installed any more.
* **diff / merge / apply / history** — in the `ak-data` command and as a
  library in Rust (`arkadia_data::diff`), Python (`arkadia.data.diff`) and
  npm (`diff` from `@arkadia/data`), with identical results (shared
  fixtures, random round-trip tests):
  * `ak-data diff OLD NEW`: the changed paths (`users[id=2].name`), then the
    changes in place with the lines around them like `git diff` (`-U n`,
    `--full`, the changed part of a line highlighted) and the history entries
    only one file has. `-o` saves a patch.
  * `ak-data merge OLD NEW` joins NEW into OLD (`--latest`: takes NEW as it
    is) and records the change in the document's history.
  * `ak-data apply FILE PATCH` applies a patch or entries of another
    document's history (`--change id`), in place; `-R` undoes, `--no-history`
    changes only the data, `--force`, `--dry-run`. A change that does not
    fit (different old value) stops the apply.
  * `ak-data history FILE`: like `git log` — id, author, date, title,
    description, changes (`--oneline`, `-p`, `--path`, `--author`, `-n`).
  * Title, author and description on every change (`-m/--title`,
    `--author` (default `$AK_DATA_AUTHOR`, then git `user.name`),
    `--description`, `--date`).
  * The history is the attribute `$changes` after the data, so the structure
    of the data does not change and decoding gives exactly the data. Changes
    are `add`, `remove`, `change` and `order`; `apply(a, diff(a, b)) == b` and
    `reverse` undoes exactly. Libraries: `diff`, `merge`, `apply`,
    `reverse`, `commit`, `history`, `with_history`.
* Attribute values can be structured (`$changes=[…]`, `$range=[1,5]`): all
  three decoders skip them as metadata (Python and npm keep them in the
  node's `attr`); `ak-data` lays a long one out on several lines.
* `ak-data -t json` highlights JSON in a terminal, like AK-DATA; `--color`
  forces colours, `--no-color` turns them off.
* **Every test of a benchmark run, by hand**: AI reports now keep the exact
  prompt, the model's raw reply and the parsed answer of every question.
  `make benchmark` exports them to `benchmarks/runs/<run>/` (the website shows
  them on `/akdata/runs`: filter by dataset, question type, format and result,
  open a question for its prompt and the reply, copy the prompt), and
  `reports/report.html` has an "Every test" section with the same. Older
  reports: `make benchmark-runs` rebuilds their prompts exactly (checked by
  token count); their replies were not recorded.
* **One set of examples everywhere**: `ak-data example`, `ak-data prompt
  --example N`, the website and `examples/prompts/` use the same 66 examples —
  51 real-size ones and 15 feature examples (one part of the format each,
  tagged `feature`; `ak-data example --list --features`). The skill's
  `reference/examples.md` is generated from the feature examples.
* `make analyze`: paired comparison with JSON (McNemar), weak question types
  and the questions AK-DATA got wrong.
* **List sizes**: `//$size=N//` at the start of every list with at least n
  items — `ak-data enc --sizes[=n]`, `akd.dumps(data, sizes=n)`,
  `dumps(data, { sizes: n })`, `EncodeOptions::array_sizes` — so a model
  reading the data does not have to count. Decoders skip it (metadata).
* `arkadia.bench.generate`: random datasets of seven shapes (flat, wide,
  nested, irregular, multi-table, configuration, lists of numbers).
* **Metadata benchmark** (part of `make benchmark`, `--no-meta` skips it):
  four annotated datasets (`arkadia.bench.annotated`) in six variants — JSON,
  JSON + notes, AK-DATA without metadata, with `/* comments */`, with
  `$attributes`/`#tags`, with both. Of 27 questions, 15 can only be answered
  with the metadata (codes, units, test records); the report shows accuracy on
  both kinds of questions and the token price per variant
  (`reports/meta-<model>.json`), and the website shows it.
* **51 copy-paste examples, each with or without metadata** (`examples/prompts/`,
  was 10): 45 carry metadata, 25 need it to be answered. Every prompt exists
  in four formats × {none, comments, attributes, both}; `prompts.json` per
  example holds them all. `ak-data prompt --example N --attributes --comments`
  (`--meta` = both) builds the same prompts in Rust; `ak-data prompt --list`
  shows the tags. Prompts are byte-identical in Python and Rust
  (`rust/scripts/compat_prompts.py`, part of `make e2e`).
* **`ak-data fmt`**: lay out AK-DATA to a width (`--width`), one line
  (`--compact`), or without comments / attributes (`--no-comments`,
  `--no-attributes`).
* Python `arkadia.data.layout` (`pretty`, `compact`, `strip_meta`) — the same
  algorithm and output as Rust `layout` and npm `pretty` / `compact` /
  `stripMeta` (new).
* `ak-data example schema-metadata`: schema metadata ($required, $unit,
  $maxItems, comments) and instance metadata ($verified, #featured).
* **`ak-data example`**: a random example from a gallery of 14 (flat tables,
  nesting, lists, irregular records, type overrides, named types, metadata,
  special names …), laid out and coloured, with what it shows, token counts and
  a round-trip check. `--prompt` adds a copy-paste prompt for AI and the
  expected answer (computed from the data); `--raw` for pipes, `--list`,
  `--json`, `--seed`, `--width`. Nothing is drawn to the left of the code or
  the prompt, so both can be selected straight from the terminal.
* **`ak-data info`**: the complete format definition, coloured — document,
  values, headers and types, records, lists, overrides, named types, metadata,
  encoder rules, JSON mapping, EBNF grammar, writing rules and common
  mistakes. Every example is decoded live. `ak-data info <section>`.
* **Layout**: `arkadia_data::layout::{pretty, compact, highlight}` (Rust) and
  `pretty` / `compact` (`@arkadia/data`): re-flows any AK-DATA text to a line
  width (records fill lines, headers and lists of records one item per line);
  both languages give identical output.
* **`make benchmark` → website**: the bundled run writes
  `benchmarks/benchmark.json` (`--site FILE` in `python -m arkadia.bench`);
  model results are kept across runs. The website copies it with its own
  `make benchmark-copy`; this repository never writes outside itself.
* **Skill `ak-data-format` rewritten** for models: reading and writing
  procedures, full syntax, edge cases, checklist and common mistakes, and
  `reference/spec.md` + `reference/examples.md` generated from `ak-data`
  (`make skill`).
* `make package-rs`: the Rust package `rust/dist/arkadia-data-<version>.crate`.
* `make add-to-cli [CLI=../arkadia-cli]`: vendors the package into arkadia-cli
  and adds it as a dependency of the daemon crate (`service`).

## [0.2.0] - 2026-10-23

Libraries: `arkadia-data` (PyPI, `import arkadia.data as akd`),
`@arkadia/data` (npm, `import { encode, decode } from '@arkadia/data'`) and
`arkadia-data` (crates.io, `use arkadia_data as akd;`). The **`ak-data`**
command is the Rust program.

### Added
* **Rust crate `arkadia-data`** (`rust/`, `use arkadia_data as akd;`):
  `encode` / `encode_pretty` / `decode`, text-level `json_to_akd`,
  `akd_to_json`, `convert` (JSON or AK-DATA in, JSON / TOON / AK-DATA out),
  `loads_any`, a TOON encoder, prompts and the ten examples, token estimate.
  Only dependency `serde_json`. Writes exactly what the Python package writes
  (checked by `rust/scripts/compat.py` in `make e2e`).
* **The `ak-data` command is the Rust binary**: `enc`, `dec` (to JSON, TOON,
  AK-DATA), `stats`, `prompt`, `hint`; `make install` installs it with
  Homebrew (local tap `arkadia/local`) or into `~/.local/bin`.
* `ak-data prompt`: copy-paste prompts for ChatGPT, Gemini
  or Claude — format definition + data + question + answer format — in JSON,
  TOON, AK-DATA or AK-DATA COMPACT; ten bundled examples with expected
  answers (`examples/prompts/`). `ak-data hint` prints the definition.
* json-like helpers in `arkadia.data` and `@arkadia/data`: `dumps`, `loads`,
  `dump`, `load`, `loads_any` / `loadsAny`, `to_prompt` / `toPrompt`,
  `HINT`, `FORMAT_DEFINITION`, `AKDataError`, token counting
  (`count_tokens` / `estimateTokens`), `buildPrompt`.
* Benchmarks in the repository (not part of `ak-data`): `make benchmark`
  (`python -m arkadia.bench`) runs, in one go, the token / speed / fidelity
  benchmark (JSON, minified JSON, YAML, TOON, AK-DATA, AK-DATA compact; eight
  bundled datasets or `DIR=…`), the AI benchmark (questions with known
  answers per dataset and format; accuracy, tokens, correct answers per 10k
  tokens, per question type; `--write`; OpenAI-compatible endpoints, Ollama,
  OpenRouter, Anthropic; dry run without a key) and one self-contained HTML
  report with a summary written by a model or computed from the numbers.
  `make benchmark ONLY_SHOW=1` (`--only-show`) only prints every prompt.
* `Makefile`: `prepare`, `build`, `test` (each with `-py` / `-ts` / `-rs`),
  `install` / `uninstall` (the `ak-data` program), `benchmark`, `e2e`
  (format, lint, tests, builds, installed packages, Rust = Python; replaces
  `priv-check.sh`), `clean`.
* Agent skills: `skills/ak-data-install` (installs and uses the tools) and
  `skills/ak-data-format` (the format defined by its structure: read and
  write AK-DATA).
* Seeded random round-trip test suites (Python and TypeScript).

### Changed
* TypeScript: Biome replaces ESLint and Prettier (`npm run check`, `npm run fix`).
* `make` shows a colored guide with the logo (`scripts/help.sh`); `make e2e`
  lives in `scripts/e2e.sh`.
* The Python and npm packages are libraries only: no `ak-data` / `akd`
  commands (use the Rust `ak-data`).
* TypeScript writes readable headers like Python (`id:number`); Python writes
  an empty list like TypeScript.

### Fixed
* Keys containing a backtick were lost (decoded as `null`); such records are
  now written by name with a quoted key. An empty key next to a `"0"` key, and
  records whose field names repeat, also round-trip (Python, TypeScript).
* Python decoder crash on lists without an element schema.
* **Data loss on round-trip** for heterogeneous data: records whose keys
  differ from the list header, lists mixing records and lists, nested lists
  of records, `[any]` element types, empty objects and empty keys. JSON →
  AK-Data → JSON is now lossless on every tested document.
* The decoder no longer lets one list element's shape leak into the next
  ones (shared header schemas were modified in place).
* `[<[...]>]` (list of lists of records) headers and `[any]` element types
  now parse.
* Unclosed records report an error instead of decoding silently.
* The CLI crashed at start-up offline (tiktoken download at import time);
  token counting is now lazy with an approximate fallback.
* TOON comparison was silently skipped (wrong `toon-format` API call).

### Changed
* TypeScript: Biome replaces ESLint and Prettier (`npm run check`, `npm run fix`).
* `make` shows a colored guide with the logo (`scripts/help.sh`); `make e2e`
  lives in `scripts/e2e.sh`.
* Lists of records use the field layout shared by most records as header;
  others are written as named records. Saves tokens on semi-uniform data.
* Header types use the most common non-null type of each field, and `null`
  values need no type tag (fewer tokens for columns with missing values).
* Benchmarks moved to `arkadia.bench`; `arkadia.data` keeps the format API.
* Core library has no runtime dependencies; benchmark libraries moved to the
  `bench` / `ai` extras.
* Faster decoding of strings and whitespace; debug messages are only built
  when debugging.

## [0.1.11] - 2026-02-20

### Added
* **Prompt Output Mode**: Introduced `prompt_output` configuration. When enabled, the encoder generates a "Structural Blueprint" instead of raw data.
* Records expand into `{ key: type /* comment */ }` blocks.
* Lists render a single representative element followed by a continuation hint (`...`).
* Recursive expansion of nested anonymous schemas (no more `any` labels).
* **LLM Hinting**: Automatic injection of field comments into the prompt output to improve AI generation accuracy.
* **Escaped Identifiers**: Support for backticks (```) in identifiers. Names containing spaces or special characters (e.g., `@`User ID+`, ` `is - special?` ``) are now valid.
* **Smart Encoding**: The encoder now automatically wraps identifiers in backticks only when they do not match the standard `[a-zA-Z_][a-zA-Z0-9_]*` regex.
* **Boolean Flag Support**: Metadata attributes with `true` values are now rendered as clean flags (e.g., `$required` instead of `$required=true`).

### Changed
* TypeScript: Biome replaces ESLint and Prettier (`npm run check`, `npm run fix`).
* `make` shows a colored guide with the logo (`scripts/help.sh`); `make e2e`
  lives in `scripts/e2e.sh`.

* **List Formatting (Pretty Mode)**:
* Moved `$size` attribute into the standard metadata block (`// $size=N //`).
* Fixed missing commas between list elements in non-compact mode.
* Improved indentation logic for multiline lists.


* **Metadata Standardization**: Transitioned validation logic from `!required` suffix to `$required` metadata attribute to maintain the Passive Data Principle.

### Removed

* **`!required` Modifier**: Removed functional support for the `!` suffix in schema definitions. It remains as a syntax-highlighting-only token.

### Changed
* TypeScript: Biome replaces ESLint and Prettier (`npm run check`, `npm run fix`).
* `make` shows a colored guide with the logo (`scripts/help.sh`); `make e2e`
  lives in `scripts/e2e.sh`.
* The Python and npm packages are libraries only: no `ak-data` / `akd`
  commands (use the Rust `ak-data`).
* TypeScript writes readable headers like Python (`id:number`); Python writes
  an empty list like TypeScript.

### Fixed
* Keys containing a backtick were lost (decoded as `null`); such records are
  now written by name with a quoted key. An empty key next to a `"0"` key, and
  records whose field names repeat, also round-trip (Python, TypeScript).
* Python decoder crash on lists without an element schema.

* Fixed a bug in `Encoder.ts` and `Encoder.py` where metadata lines in lists were incorrectly suffixed with commas.
* Corrected identifier parsing logic to strictly terminate at the first closing backtick (no internal escaping).
