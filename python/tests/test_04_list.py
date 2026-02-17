import arkadia.ai as ai
from arkadia.ai.data import SchemaKind
import pytest
from arkadia.ai.data.decode import decode
from arkadia.ai.data.encode import encode
from arkadia.ai.data import Node
from utils import assert_roundtrip

def test_decode_list_of_primitives():
    """Validates simple lists."""
    text = "[1, 2, 3]"
    excepted = "<[number]>[1,2,3]"
    res = decode(text)
    assert not res.errors

    node = res.node
    # Check elements (Node logic might store simple lists in primitive_elements)
    values = [el.value for el in node.elements]
    assert values == [1, 2, 3]
    assert_roundtrip(node, excepted, True)


def test_infer_mixed_list_type_from_first_element():
    """
    Tests if the list type is inferred based on the first element ("a" -> string).
    As a result, the number 3 (int) should be treated as a mismatch and marked with the <number> tag.
    """
    # 1. Input data: List starts with strings but has an int at the end
    data = {"tests": ["a", "b", "c", 3]}

    # 2. Encoding (inference happens here in _infer_primitive_type or parse_list)
    # Assuming default configuration is used
    node = ai.data.parse(data)

    assert node.schema is not None
    assert node.schema.is_record
    assert "tests" in node.fields
    tests_node = node.fields["tests"]
    assert tests_node.is_list
    assert tests_node.schema is not None
    assert tests_node.schema.element is not None

    assert tests_node.schema.element.kind == SchemaKind.PRIMITIVE
    assert (
        tests_node.schema.element.type_name == "string"
    )  # Inferred from first element

    assert tests_node.elements and len(tests_node.elements) == 4

    output = ai.data.encode(data, {"compact": True, "colorize": False})

    # We expect the list NOT to be [any], but [string] (implied or explicit),
    # so strings will be "clean", and the number will get a tag.

    # Check if 'a' is treated normally (as a string in a string list)
    assert '"a"' in output

    # KEY: Check if 3 got a tag because it doesn't match the inferred String type
    # (depends on whether your Encoder outputs <number> or <int>, adjust string below)
    assert "<number> 3" in output or "<int> 3" in output

    # Ensure there is NO tag next to strings (because they match the list type)
    assert '<string> "a"' not in output

    excepted = '<tests:[string]>(["a","b","c",<number> 3])'
    assert_roundtrip(node, excepted, True)


def test_explicit_any_list_generates_tags_due_to_primitive_mismatch():
    """
    Tests the scenario where a list is defined as [any].

    Current Behavior:
    1. 'any' is parsed as a PRIMITIVE type named "any".
    2. The actual values have types "string" and "number".
    3. Because "string" != "any", the Encoder sees a mismatch and adds explicit tags.
    """

    # 1. Input in AID format
    aid_text = """
    <tests: [any]>
    (
        ["a", "b", "c", 3]
    )
    """

    # 2. Decode
    result = ai.data.decode(aid_text, debug=True)
    node = result.node
    errors = result.errors
    assert len(errors) == 0

    # 3. Verify Internal State (Based on your logs)
    tests_node = node.fields["tests"]

    # Verify the list definition
    # It expects elements of type PRIMITIVE "any"
    element_schema = tests_node.schema.element
    assert element_schema.kind == SchemaKind.PRIMITIVE
    assert element_schema.type_name == "string"

    # Verify the actual elements
    # They are parsed as Strings and Numbers
    assert tests_node.elements[0].schema.type_name == "string"
    assert tests_node.elements[3].schema.type_name == "number"

    # 4. Encode
    # We use compact=True to make string assertion easier
    excepted = '<tests:[string]>(["a","b","c",<number> 3])'
    assert_roundtrip(node, excepted, True)

def test_inference_happy_path():
    """
    Theory: If a list has no type (or [any]), the first element ("a")
    should refine the list schema to [string].
    """
    data_str = '["a", "b"]'  # No header = SchemaKind.ANY

    result = ai.data.decode(data_str)
    node = result.node
    errors = result.errors

    assert len(errors) == 0
    assert node.is_list
    assert node.schema.element.type_name == "string"  # Inferred!

    excepted = '<[string]>["a","b"]'
    assert_roundtrip(node, excepted, True)

def test_inference_mismatch():
    """
    Theory: First element "a" sets list to [string].
    The number 3 is mismatch and gets tagged.
    """
    data_str = '["a", 3]'

    result = ai.data.decode(data_str)
    node = result.node
    errors = result.errors

    assert len(errors) == 0  # Mismatch is valid in AID, just logged

    # The list should have become [string] due to "a"
    assert node.schema.element.type_name == "string"

    excepted = '<[string]>["a",<number> 3]'
    assert_roundtrip(node, excepted, True)


def test_inference_mismatch():
    """
    Theory: First element "a" sets list to [string].
    The number 3 is mismatch and gets tagged.
    """
    data_str = '[3, "a"]'

    result = ai.data.decode(data_str)
    node = result.node
    errors = result.errors

    assert len(errors) == 0  # Mismatch is valid in AID, just logged
    # The list should have become [string] due to "a"
    assert node.schema.element.type_name == "number"

    excepted = '<[number]>[3,<string> "a"]'
    assert_roundtrip(node, excepted, True)

def test_schema_crash_fix_override_logic():
    """
    Theory: We expect a String, but we get a List.
    This triggers 'needs_override' in parse_value.

    If you pass the OLD schema to parse_list, this crashes or errors.
    If you pass the NEW node_schema, this works and tags the output.
    """
    # Header says 'test' is a string, but body has a list
    aid_text = """
<test: string>
(
    ["a", "b"]
)
    """

    result = ai.data.decode(aid_text)
    node = result.node
    errors = result.errors
    assert len(errors) == 0

    excepted = '<test:string>(<[string]> ["a","b"])'
    assert_roundtrip(node, excepted, True)

def test_primitive_no_outupt():
    aid_text = """
 <ab>
{
    ab:  ["a", "b", "c", 3]
}
    """

    result = ai.data.decode(aid_text, debug=True)
    node = result.node
    errors = result.errors
    assert len(errors) == 0

    excepted = '<ab:[string]>(["a","b","c",<number> 3])'
    assert_roundtrip(node, excepted, True)


def test_simple_types():
    aid_text = """["a", "b", "c", 3]"""

    result = ai.data.decode(aid_text, debug=True)
    node = result.node
    errors = result.errors
    assert len(errors) == 0

    excepted = '<[string]>["a","b","c",<number> 3]'
    assert_roundtrip(node, excepted, True)


def test_inner_list_types():
    aid_text = """<[[int]]>[[2,3,4],[5,6,7]]"""

    result = ai.data.decode(aid_text, debug=True)
    node = result.node
    errors = result.errors
    assert len(errors) == 0

    excepted = '<[[number]]>[[2,3,4],[5,6,7]]'
    assert_roundtrip(node, excepted, True)


