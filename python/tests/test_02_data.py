from utils import assert_roundtrip

from arkadia.data.decode import decode
from arkadia.data.encode import encode

# ==================================================================================
# 3. ENCODING TESTS (Python Object -> String)
# ==================================================================================


def test_encode_simple_dict():
    """Validates encoding a Python dict to AK-DATA format."""
    data = {"x": 10, "y": 20}
    result = encode(data, config={"compact": True})
    expected = "<x:number,y:number>(10,20)"
    assert result == expected
    assert_roundtrip(result, "<x:number,y:number>(10,20)", True)


def test_encode_list_of_objects():
    """Validates encoding a list of dictionaries."""
    data = [{"name": "A", "val": 1}, {"name": "B", "val": 2}]
    result = encode(data, config={"compact": True, "colorize": False})
    expected = '<[name:string,val:number]>[("A",1),("B",2)]'
    assert result == expected

    assert_roundtrip(result, expected, True)


def test_round_trip_consistency():
    """
    Golden Test: Encode -> Decode -> Compare.
    """
    original_data = [
        {"id": 1, "active": True, "tags": ["a", "b"]},
        {"id": 2, "active": False, "tags": ["c"]},
    ]
    expected = (
        '<[id:number,active:bool,tags:[string]]>[(1,true,["a","b"]),(2,false,["c"])]'
    )

    # 1. Encode
    encoded_text = encode(
        original_data,
        config={"compact": True, "include_schema": True, "colorize": False},
    )
    assert encoded_text == expected
    assert_roundtrip(encoded_text, expected, True)

    # 2. Decode
    res = decode(encoded_text, debug=True)
    node = res.node
    print(node.schema.element.fields)

    assert not res.errors, f"Errors during decode: {res.errors}"

    # 3. Convert back to dict
    decoded_data = res.node.dict()

    # 4. Compare
    assert len(decoded_data) == 2
    assert decoded_data[0]["id"] == 1
    assert decoded_data[0]["active"] is True
    assert decoded_data[0]["tags"] == ["a", "b"]
    assert decoded_data[1]["active"] is False
