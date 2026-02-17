from arkadia.ai.data import decode
from utils import assert_roundtrip

# ==================================================================================
# 1. DECODING TESTS (String -> Node)
# ==================================================================================


def test_decode_and_encode_primitives():
    """
    Validates that basic types are parsed correctly (Decode)
    and then encoded back to a string representation correctly (Encode).
    """
    cases = [
        # (Input Text, Expected Python Value, Expected Encoded Output)
        # Note: Encoded output usually matches input for simple primitives,
        # but strings might have specific quoting.
        ("123", 123, "<number>123"),
        ("-50", -50, "<number>-50"),
        ('"hello"', "hello", '<string>"hello"'),
        ('"hello world"', "hello world", '<string>"hello world"'),
        ("true", True, "<bool>true"),
        ("false", False, "<bool>false"),
        ("null", None, "<null>null"),
    ]

    for text, expected_val, expected_enc in cases:
        # 1. DECODE
        res = decode(text, "", debug=False)

        assert not res.errors, f"Parsing failed for input: {text}. Errors: {res.errors}"
        assert res.node.value == expected_val
        assert res.node.is_primitive, f"Node for '{text}' should be primitive"

        # 2. ENCODE
        encoded_str = res.node.encode(
            config={"colorize": False, "compact": True}
        ).strip()

        assert (
            encoded_str == expected_enc
        ), f"Encoding mismatch. Got '{encoded_str}', expected '{expected_enc}'"


def test_decode_floats():
    """Validates that floating point numbers are parsed correctly."""
    cases = [("12.34", 12.34), ("-0.005", -0.005), ("0.0", 0.0)]
    for text, expected in cases:
        res = decode(text)
        assert not res.errors
        assert res.node.value == expected
        assert isinstance(res.node.value, float)


def test_decode_named_record():
    """Validates named records {key:value}."""
    text = '{id: 1, name: "Test"}'
    res = decode(text, debug=True)
    assert not res.errors

    node = res.node

    print(node)
    assert node.is_record
    assert node.fields["id"].value == 1
    assert node.fields["name"].value == "Test"

    assert_roundtrip(node, '<id:number,name:string>(1,"Test")', True)


def test_decode_positional_record():
    """Validates positional records (val1, val2)."""
    text = '(10, "Alice")'
    expected =  '<_0:number,_1:string>(10,"Alice")'
    res = decode(text, debug=True)
    assert not res.errors

    node = res.node
    print(node)

    assert node.is_record
    # Positional records are stored as elements if no schema names are known yet
    # Or in fields if mapped. Assuming generic record -> elements or "0","1" fields logic.

    # Fallback if mapped to index keys
    assert node.fields["_0"].value == 10
    assert node.fields["_1"].value == "Alice"

    assert_roundtrip(node, expected, True)


def test_decode_raw_string():
    """Validates raw strings (unquoted) used in named records."""
    text = "{color: red, status: active}"
    res = decode(text, debug=True)
    assert not res.errors

    node = res.node
    assert node.fields["color"].value == "red"
    assert node.fields["status"].value == "active"

    assert_roundtrip(node, '<color:string,status:string>("red","active")', True)
