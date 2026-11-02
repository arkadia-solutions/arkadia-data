"""
The formats AK-Data compares itself with. Optional ones (TOON, YAML) are
only listed when their library is installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import arkadia.data as _akd
from arkadia.data.layout import pretty as _pretty

# Lists with at least this many elements get $size=N in the "+ sizes" variants.
SIZES_MIN = 4


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    encode: Callable[[Any], str]
    decode: Optional[Callable[[str], Any]]
    note: str = ""


def _akd_decode(text: str) -> Any:
    result = _akd.decode(text)
    if result.errors:
        raise ValueError(f"{len(result.errors)} decode error(s): {result.errors[0]}")
    return result.node.dict()


def _base_formats() -> List[Format]:
    return [
        Format(
            "json",
            "JSON (indent 2)",
            lambda d: json.dumps(d, ensure_ascii=False, indent=2),
            json.loads,
            "what most tools and agents send by default",
        ),
        Format(
            "json-min",
            "JSON (minified)",
            lambda d: json.dumps(d, ensure_ascii=False, separators=(",", ":")),
            json.loads,
            "no whitespace",
        ),
        Format(
            "akd",
            "AK-Data",
            lambda d: _pretty(_akd.dumps(d), 80),
            _akd_decode,
            "readable form: one record per line (ak-data)",
        ),
        Format(
            "akcd",
            "AK-Data compact",
            lambda d: _akd.encode(d, {"compact": True, "escape_new_lines": True}),
            _akd_decode,
            "single line, for prompts and tool results",
        ),
    ]


def _variants() -> List[Format]:
    """AK-Data with list sizes — compared in the AI benchmark."""
    return [
        Format(
            "akcd-n",
            "AK-Data compact + sizes",
            lambda d: _akd.dumps(d, sizes=SIZES_MIN),
            _akd_decode,
            f"single line, $size=N on lists of {SIZES_MIN}+ items",
        ),
        Format(
            "akd-n",
            "AK-Data + sizes",
            lambda d: _pretty(_akd.dumps(d, sizes=SIZES_MIN), 80),
            _akd_decode,
            f"one record per line, $size=N on lists of {SIZES_MIN}+ items",
        ),
    ]


def available_formats(variants: bool = False) -> Dict[str, Format]:
    """
    The formats of the token benchmark; variants=True adds AK-Data with list
    sizes (akcd-n, akd-n), compared in the AI benchmark.
    """
    formats = {f.key: f for f in _base_formats()}
    if variants:
        formats.update({f.key: f for f in _variants()})
    try:
        import toon_format

        formats["toon"] = Format(
            "toon",
            "TOON",
            lambda d: toon_format.encode(d, indent_size=2, delimiter=","),
            lambda t: toon_format.decode(t),
            "Token-Oriented Object Notation",
        )
    except ImportError:
        pass
    try:
        import yaml

        formats["yaml"] = Format(
            "yaml",
            "YAML",
            lambda d: yaml.safe_dump(d, allow_unicode=True, sort_keys=False),
            yaml.safe_load,
            "block style",
        )
    except ImportError:
        pass
    order = ["json", "json-min", "yaml", "toon", "akd", "akcd", "akd-n", "akcd-n"]
    return {k: formats[k] for k in order if k in formats}


def missing_formats() -> List[str]:
    out = []
    for key, module, extra in (
        ("toon", "toon_format", "bench"),
        ("yaml", "yaml", "bench"),
    ):
        try:
            __import__(module)
        except ImportError:
            out.append(f"{key} (pip install 'arkadia-data[{extra}]')")
    return out
