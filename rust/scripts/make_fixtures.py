"""
Writes rust/tests/fixtures.json: inputs with the exact AK-DATA (compact and
readable) and TOON text the Python package writes, for `cargo test`.

    cd python && uv run --all-extras python ../rust/scripts/make_fixtures.py
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compat  # noqa: E402
import toon_format  # noqa: E402

import arkadia.data as akd  # noqa: E402

cases = []
for name, data in compat.corpus(120):
    if compat.huge_int(data) or name.startswith(("dataset:", "fixture:")):
        continue
    cases.append(
        {
            "name": name,
            "data": data,
            "compact": akd.dumps(data),
            "pretty": akd.dumps(data, indent=2),
            "toon": toon_format.encode(data, indent_size=2, delimiter=","),
        }
    )
out = HERE.parent / "tests" / "fixtures.json"
out.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{len(cases)} cases → {out}")
