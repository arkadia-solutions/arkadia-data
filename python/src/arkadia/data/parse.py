# parse.py
"""
JSON → Node converter.
"""

from typing import Any, Dict, List, Optional

from .Node import Node
from .Schema import Schema, SchemaKind


class EncodingError(Exception):
    pass


# --------------------------------------------------------------
# Helper: Type Wrapper
# --------------------------------------------------------------
class PrimitiveType:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name


TYPE_STRING = PrimitiveType("string")
TYPE_NUMBER = PrimitiveType("number")
TYPE_BOOL = PrimitiveType("bool")
TYPE_NULL = PrimitiveType("null")
TYPE_ANY = PrimitiveType("any")

# --------------------------------------------------------------
# Primitive → Node(primitive)
# --------------------------------------------------------------


def parse_primitive(v: Any) -> Node:
    if isinstance(v, str):
        schema = Schema(kind=SchemaKind.PRIMITIVE, type_name=str(TYPE_STRING))
    elif isinstance(v, bool):
        schema = Schema(kind=SchemaKind.PRIMITIVE, type_name=str(TYPE_BOOL))
    elif isinstance(v, (int, float)):
        schema = Schema(kind=SchemaKind.PRIMITIVE, type_name=str(TYPE_NUMBER))
    elif v is None:
        schema = Schema(kind=SchemaKind.PRIMITIVE, type_name=str(TYPE_NULL))
    else:
        raise EncodingError(f"Unsupported primitive: {v}")

    return Node(schema=schema, value=v)


# --------------------------------------------------------------
# List → Node(list)
# --------------------------------------------------------------


def parse_list(arr: List[Any]) -> Node:
    # 1. EMPTY LIST
    # If the list is empty, we default to a List of Any.
    if len(arr) == 0:
        element_schema = Schema(kind=SchemaKind.PRIMITIVE, type_name="any")
        list_schema = Schema(kind=SchemaKind.LIST, element=element_schema)
        return Node(schema=list_schema, elements=[])

    # 2. PARSE ALL ITEMS
    parsed_items = [parse(v) for v in arr]

    unified_element_schema = _element_schema(parsed_items)

    # 4. FINALIZE
    list_schema = Schema(
        kind=SchemaKind.LIST, type_name="list", element=unified_element_schema
    )

    return Node(schema=list_schema, elements=parsed_items)


def _common_type(schemas: List[Schema]) -> Optional[str]:
    """
    The most frequent non-null primitive type (first seen wins ties), or None
    when there is none. Nulls never need a type tag, so they do not vote.
    """
    counts: Dict[str, int] = {}
    for sc in schemas:
        if sc.kind == SchemaKind.PRIMITIVE and sc.type_name != "null":
            counts[sc.type_name] = counts.get(sc.type_name, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def header_safe(key: str) -> bool:
    """A header cannot spell a key with a backtick; such records are named."""
    return "`" not in key


def _headerable(node: Node) -> bool:
    return all(header_safe(k) for k in node.fields)


def _element_schema(items: List[Node]) -> Schema:
    """
    The header schema of a list.

    Lists of records get the field layout shared by most of them, so those
    records can be written positionally under one header; the others are
    written self-describing ({key: value}). When no layout is shared by at
    least two records (or the only one) and half of the list, the list gets
    no record header.
    """
    first = items[0].schema
    if first.kind == SchemaKind.PRIMITIVE:
        # The most common non-null type; other values get an inline <type> tag.
        common = _common_type([i.schema for i in items])
        if common and common != first.type_name:
            return Schema(kind=SchemaKind.PRIMITIVE, type_name=common)
        return first
    if first.kind != SchemaKind.RECORD:
        # Lists: the first element sets the type; others are tagged.
        return first

    counts: Dict[frozenset, int] = {}
    layout: Dict[frozenset, Schema] = {}
    for item in items:
        if item.schema.kind == SchemaKind.RECORD and _headerable(item):
            keys = frozenset(item.fields.keys())
            counts[keys] = counts.get(keys, 0) + 1
            layout.setdefault(keys, item.schema)
    if not counts:
        return Schema(kind=SchemaKind.PRIMITIVE, type_name="any")

    keys, count = max(counts.items(), key=lambda kv: kv[1])
    exact = (count >= 2 or len(items) == 1) and count * 2 >= len(items)
    union = _union_schema(items)
    if union is not None and union[1] > (count if exact else 0):
        return union[0]
    if exact:
        element = Schema(kind=SchemaKind.RECORD)
        fitting = [
            i
            for i in items
            if i.schema.kind == SchemaKind.RECORD
            and _headerable(i)
            and frozenset(i.fields) == keys
        ]
        for field in layout[keys].fields:
            if field.kind == SchemaKind.PRIMITIVE:
                common = _common_type(
                    [
                        i.fields[field.name].schema
                        for i in fitting
                        if field.name in i.fields
                    ]
                )
                if common and common != field.type_name:
                    field = Schema(
                        kind=SchemaKind.PRIMITIVE, type_name=common, name=field.name
                    )
            element.add_field(field)
        return element
    return Schema(kind=SchemaKind.PRIMITIVE, type_name="any")


def _prefix_fits(item: Node, names: List[str]) -> bool:
    """The record's keys are exactly the first k names of a header (k >= 1)."""
    k = len(item.fields)
    return 1 <= k <= len(names) and set(names[:k]) == set(item.fields)


def _union_schema(items: List[Node]):
    """
    A header with every field of the records — the most frequent first — under
    which a record whose keys are its first k fields is written positionally
    with k values (the decoder leaves the missing trailing fields out). Returns
    (schema, number of records that fit) or None when fewer than two records,
    or fewer than half of the list, fit.
    """
    # Records whose every key a header can spell (an empty key cannot be).
    records = [
        i
        for i in items
        if i.schema.kind == SchemaKind.RECORD
        and _headerable(i)
        and all(k != "" for k in i.fields)
    ]
    if len(records) < 2:
        return None
    freq: Dict[str, int] = {}
    first: Dict[str, int] = {}
    base: Dict[str, Schema] = {}
    for r in records:
        for name, child in r.fields.items():
            freq[name] = freq.get(name, 0) + 1
            if name not in first:
                first[name] = len(first)
                base[name] = child.schema
    names = sorted(freq, key=lambda n: (-freq[n], first[n]))
    fitting = [r for r in records if _prefix_fits(r, names)]
    if len(fitting) < 2 or len(fitting) * 2 < len(items):
        return None
    element = Schema(kind=SchemaKind.RECORD)
    for name in names:
        field = base[name]
        if field.kind == SchemaKind.PRIMITIVE:
            common = _common_type(
                [r.fields[name].schema for r in records if name in r.fields]
            )
            if common and common != field.type_name:
                field = Schema(kind=SchemaKind.PRIMITIVE, type_name=common, name=name)
        element.add_field(field)
    return element, len(fitting)


# --------------------------------------------------------------
# Dict → Node(record)
# --------------------------------------------------------------


def parse_dict(obj: Dict[str, Any]) -> Node:
    """
    JSON objects → named records.
    """
    fields_data = {}

    schema = Schema(kind=SchemaKind.RECORD)

    for key, raw_value in obj.items():
        child_node = parse(raw_value)

        child_node.schema.name = key

        fields_data[key] = child_node

        schema.add_field(child_node.schema)

    if not all(header_safe(k) for k in obj):
        # A key a header cannot spell: the record is written by name.
        schema.clear_fields()

    return Node(schema=schema, fields=fields_data)


# --------------------------------------------------------------
# Main entrypoint
# --------------------------------------------------------------


def parse(value: Any) -> Node:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return parse_primitive(value)

    if isinstance(value, list):
        return parse_list(value)

    if isinstance(value, dict):
        return parse_dict(value)

    raise EncodingError(f"Unsupported structure type: {type(value)}")
