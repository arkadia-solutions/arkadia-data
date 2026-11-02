# arkadia-data — AK-DATA (Arkadia Data Format) for Python

**Lossless, schema-first data for LLMs and agents.** AK-DATA writes JSON
data with a header that names each field once and records that follow it by
position — about **55% fewer tokens than JSON** and **14% fewer than TOON**
on typical agent payloads, decoding back to the exact original.

```bash
pip install arkadia-data            # library, no dependencies
pip install "arkadia-data[bench]"   # + tiktoken, toon-format, PyYAML (exact counts, TOON/YAML comparison)
```

This package is a library. The `ak-data` command line tool is the Rust
crate of the same name (`make install` in the repository, or
`cargo install arkadia-data`) and writes exactly the same text.

## Library

```python
import arkadia.data as akd

data = {"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]}

text = akd.encode(data, {"compact": True})   # '<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])'
result = akd.decode(text)
result.node.dict() == data                    # True
result.errors                                 # [] — decode errors, if any

akd.encode(data)                              # readable multi-line form
akd.encode(data, {"prompt_output": True})     # structural template for model output
```

Shortcuts and prompt helpers:

```python
akd.dumps(data)              # compact (same as encode(..., compact=True, escape_new_lines=True))
akd.loads(text)              # data; raises akd.AKDataError on invalid input (strict=False: best effort)
akd.loads_any(reply)         # model reply in JSON or AK-DATA, with or without ``` fences
akd.to_prompt(data)          # one-line hint + <data>…</data>
akd.FORMAT_DEFINITION        # ~120-token definition to paste into a chat model
akd.answer_instruction("<result:<[name:string,total:number]>>")
akd.count_tokens(text)       # exact with tiktoken, approximate otherwise
```

## Prompts

```python
from arkadia.bench.prompts import build_prompt, get_example

ex = get_example("3")                         # one of the ten bundled examples
ex.prompt("ak-data-compact")                  # definition + data + question + answer format
build_prompt(data, "Who joined first?", "toon", answer=("result", [("name", "string")]))
```

Formats: `json`, `toon` (extra `bench`), `ak-data`, `ak-data-compact`. The
same prompts on the command line: `ak-data prompt --example 3 -f toon`.

## Benchmarks (repository only)

The benchmarks are not an `ak-data` command. From the repository root:

```bash
make benchmark                      # tokens → AI → reports/report.html
make benchmark ONLY_SHOW=1          # print every AI-benchmark prompt, run nothing
make benchmark DIR=~/my-json MODEL=gpt-4o-mini
# or directly: uv run --all-extras python -m arkadia.bench --help
```

Without `--dir` eight bundled datasets are used. Token counts are exact with
tiktoken (extra `bench`) and fall back to a calibrated estimate offline. The
AI step asks a model questions with known answers about each dataset in
every format and scores the replies — OpenAI or any OpenAI-compatible server
(`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `PROVIDER=ollama|openrouter`) and
Anthropic (`ANTHROPIC_API_KEY`); without a key it is a dry run. Code:
`arkadia.bench` (`bench`, `ai_bench`, `report`, `cli`).

## Development

```bash
make install && make test         # from the repository root (uv + npm); make e2e before a commit
# or: uv sync --all-extras && uv run pytest && uv run ruff check src tests
python scripts/make_datasets.py   # regenerate the bundled datasets
python scripts/make_examples.py   # regenerate the copy-paste examples
```

TypeScript / JavaScript: `npm install @arkadia/data`.

MIT © Arkadia Solutions · https://arkadia.solutions/akdata


## Preview 0.2.0 and network boundary

0.2.0 is a source preview until the release checklist passes and registry installs are verified. Registry packages may still be 0.1.x. For this preview, clone https://github.com/arkadia-solutions/arkadia-data and install from the relevant subdirectory: `pip install ./python`, `npm install ./typescript` after building it, or `cargo install --path rust --locked`. Do not assume `cargo install arkadia-data` is available before the crate is published.

`make benchmark` is offline by default, even if API keys exist in the environment or `.env`. Explicitly use `make benchmark NETWORK=1 MODEL=...` (CLI: `--allow-network`) to send the selected datasets to a provider. Local/remote Ollama also requires this opt-in. The provider host, model and data source are printed before requests. Reports may contain data, prompts, answers and local paths; they are private by default. `--offline` and `--allow-network` are mutually exclusive. Ordinary encode/decode operations do not call models.
