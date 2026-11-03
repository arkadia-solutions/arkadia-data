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
crate of the same name (`brew install arkadia-solutions/tap/ak-data` or
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

ex = get_example("3")                         # one of the 66 bundled examples
ex.prompt("ak-data-compact")                  # definition + data + question + answer format
build_prompt(data, "Who joined first?", "toon", answer=("result", [("name", "string")]))
```

Formats: `json`, `toon` (extra `bench`), `ak-data`, `ak-data-compact`. The
same prompts on the command line: `ak-data prompt --example 3 -f toon`.

## Changes and history

```python
from arkadia.data import diff

changes = diff.diff(old, new)        # [Change(op='change', path='users[id=2].name', …)]
diff.apply(old, changes) == new      # ConflictError when a change does not fit
diff.apply(new, diff.reverse(changes)) == old
text = diff.commit(text, new, title="Rename Alan", author="Ada")   # data + its history ($changes)
diff.history(text)                   # [ChangeSet(id, date, author, title, …)]
```

The history is metadata: `akd.loads(text)` still returns exactly the data.

MIT © Arkadia Solutions · https://arkadia.solutions/akdata · [changelog](https://github.com/arkadia-solutions/arkadia-data/blob/main/CHANGELOG.md)
