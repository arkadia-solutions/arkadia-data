"""
Helpers for putting AK-Data (Arkadia Data Format) in front of a model.

Models read AK-Data without instructions in most cases, but a one-line hint
removes the remaining ambiguity (positional records) for ~95 tokens.
"""

from __future__ import annotations

from typing import Any

from .encode import encode as _encode

HINT = (
    "Data is in AK-Data format: <field:type,...> is a header; (v1,v2) is a "
    "record whose values follow the header order; {key:value} is a named "
    "record; [..] is a list; <[...]> describes every record in the list; "
    "<type> before a value overrides its type; a record with fewer values has "
    "only the first fields; //$size=N// is the number of items in a list."
)

HINT_SHORT = "AK-Data: <header> lists field names; (a,b) records follow header order."

# The full definition: paste it with the data into any chat model.
FORMAT_DEFINITION = """\
AK-DATA (Arkadia Data Format): <a:type,b:type> is a header; (v1,v2) is a record whose values follow the header order.
<[a:type,...]>[(...),(...)] is a list of records sharing that header; headers nest, e.g. items:<[sku:string,qty:number]>.
{key:value} is a record with names; <type> or <any> before a value overrides the header type.
Strings are quoted; numbers, true, false, null as in JSON; /*...*/, $attr, #tag are metadata, not data.
A record with fewer values than its header has only the first fields; //$size=N// before list items is their count."""

TOON_DEFINITION = """\
TOON (Token-Oriented Object Notation) — how to read it:
- Indentation shows nesting; "key: value" is a field.
- key[N]{f1,f2,...}: is followed by N rows of comma-separated values in field order.
- key[N]: a,b,c is a list of N values; "- " starts an item of a list of objects."""


def answer_instruction(header: str) -> str:
    """Asks for the answer in AK-Data with a given header (fewer output tokens)."""
    return (
        "Answer in AK-DATA only (no prose, no code fences), using exactly this "
        f"header and one record per result:\n{header}"
    )


def to_prompt(
    data: Any, *, hint: bool = True, compact: bool = True, label: str = "data"
) -> str:
    """
    A ready-to-paste block for a system prompt or a tool result:

        Data is in AK-Data format: ...
        <data>
        <id:number,name:string>[(1,"Ada"),(2,"Alan")]
        </data>
    """
    body = _encode(data, {"compact": compact, "escape_new_lines": compact})
    parts = [HINT] if hint else []
    parts.append(f"<{label}>\n{body}\n</{label}>")
    return "\n".join(parts)


def output_instructions(example: Any) -> str:
    """
    Instructions asking a model to answer in AK-Data, with the expected
    shape rendered as a prompt template (types and field order).
    """
    template = _encode(example, {"prompt_output": True})
    return (
        "Answer only with AK-Data in this shape: replace each type with its "
        "value, keep the field names, quote strings, repeat list items as "
        "needed.\n" + template
    )
