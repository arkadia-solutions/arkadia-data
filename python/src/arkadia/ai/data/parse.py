# parse.py
"""
JSON → Node converter.
"""

from typing import Any, Dict, List
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
    
    # Use the first element as the baseline.
    first_schema = parsed_items[0].schema
    is_list_of_records = (first_schema.kind == SchemaKind.RECORD)

    unified_element_schema: Schema

    # 3. DETERMINE ELEMENT SCHEMA
    if is_list_of_records:
        # RECORDS: Create a unified schema containing ALL fields from ALL items.
        unified_element_schema = Schema(kind=SchemaKind.RECORD, type_name="record")
        seen_fields = set()
        
        for item in parsed_items:
            # Skip non-record items if mixed list (or handle as error depending on strictness)
            if item.schema.kind == SchemaKind.RECORD:
                for field in item.schema.fields:
                    if field.name not in seen_fields:
                        unified_element_schema.add_field(field)
                        seen_fields.add(field.name)
    else:
        # PRIMITIVES: Simply take the schema of the first element.
        # We assume the list is homogeneous based on the first item.
        unified_element_schema = first_schema

    # 4. FINALIZE
    list_schema = Schema(kind=SchemaKind.LIST, type_name="list", element=unified_element_schema)

    return Node(schema=list_schema, elements=parsed_items)


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
