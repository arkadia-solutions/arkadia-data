"""
json-like helpers for AK-Data (Arkadia Data Format).

    import arkadia.data as akd

    text = akd.dumps({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]})
    # <users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])
    akd.loads(text)           # -> the same dict
    akd.dumps(obj, indent=2)  # readable multi-line form
    akd.to_prompt(obj)        # block with a one-line format hint for models
    akd.count_tokens(text)    # o200k_base when tiktoken is available

`encode` / `decode` remain the full API (configuration, node tree, metadata).
"""

from __future__ import annotations

import json
from typing import IO, Any, Optional

from .decode import decode
from .encode import encode


class AKDataError(ValueError):
    """Raised by loads() when the text is not valid AK-Data."""

    def __init__(self, errors: list, text: str):
        self.errors = errors
        self.text = text
        first = errors[0] if errors else "unknown error"
        super().__init__(f"Invalid AK-Data ({len(errors)} error(s)): {first}")


def dumps(
    obj: Any,
    *,
    indent: Optional[int] = None,
    types: bool = True,
    comments: bool = True,
    colorize: bool = False,
    sizes: Optional[int] = None,
) -> str:
    """
    Serialize `obj` (dicts, lists, str, int, float, bool, None) to AK-Data.

    indent=None gives the compact single-line form (best for prompts);
    indent=2 gives the readable form. types=False drops primitive types from
    headers (slightly fewer tokens, still lossless). sizes=N writes the number
    of elements of every list with at least N elements as metadata
    ([//$size=90// …]), so a model does not have to count them.
    """
    compact = indent is None
    config = {
        "compact": compact,
        "escape_new_lines": compact,
        "indent": indent or 2,
        "include_type": types,
        "include_comments": comments,
        "colorize": colorize,
        "include_array_size": sizes is not None,
        "array_size_min": sizes or 1,
    }
    return encode(obj, config)


def loads(text: str, *, strict: bool = True) -> Any:
    """
    Parse AK-Data text into Python values. With strict=True (default) any
    decode error raises AKDataError; with strict=False the best-effort value
    is returned.
    """
    result = decode(text, remove_ansi_colors=True)
    if result.errors and strict:
        raise AKDataError(result.errors, text)
    return result.node.dict()


def loads_any(text: str) -> Any:
    """Parse text that may be JSON or AK-Data (for model output)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(stripped)
    except ValueError:
        return loads(stripped)


def dump(obj: Any, fp: IO[str], **kwargs: Any) -> None:
    fp.write(dumps(obj, **kwargs))


def load(fp: IO[str], **kwargs: Any) -> Any:
    return loads(fp.read(), **kwargs)
