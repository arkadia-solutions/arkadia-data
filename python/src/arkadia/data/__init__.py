"""
arkadia.data — AK-Data, the Arkadia Data Format.

A lossless, schema-first text form of JSON data for LLMs and agents: a
header names each field once and records follow by position.

    import arkadia.data as akd

    text = akd.encode(data, {"compact": True})   # full API with configuration
    result = akd.decode(text)                     # node tree, errors, metadata
    data = result.node.dict()

    akd.dumps(data) / akd.loads(text)             # json-like shortcuts
    akd.to_prompt(data)                           # format hint + <data> block

    from arkadia.data import diff                 # diff / merge / apply / history
    diff.diff(old, new); diff.apply(old, changes); diff.commit(text, new, title="…")
"""

from . import diff
from .api import AKDataError, dump, dumps, load, loads, loads_any
from .colorize import colorize
from .decode import decode
from .encode import encode
from .Node import Node
from .parse import parse
from .prompt import (
    FORMAT_DEFINITION,
    HINT,
    TOON_DEFINITION,
    answer_instruction,
    output_instructions,
    to_prompt,
)
from .Schema import Schema, SchemaKind
from .tokens import count_tokens, get_tokenizer

__all__ = [
    "encode",
    "decode",
    "parse",
    "Node",
    "Schema",
    "SchemaKind",
    "colorize",
    "dumps",
    "loads",
    "dump",
    "load",
    "loads_any",
    "AKDataError",
    "to_prompt",
    "output_instructions",
    "HINT",
    "FORMAT_DEFINITION",
    "TOON_DEFINITION",
    "answer_instruction",
    "count_tokens",
    "get_tokenizer",
    "diff",
]
__version__ = "0.3.0"
