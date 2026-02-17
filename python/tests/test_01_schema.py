import pytest
from arkadia.ai.data.decode import decode
from arkadia.ai.data.encode import encode
from arkadia.ai.data import Node
from utils import assert_roundtrip



# ==================================================================================
# 2. SCHEMA DEFINITION & TYPING
# ==================================================================================


def test_schema_definition_and_usage():
    """
    Validates that a type defined with @Type<...> is correctly applied
    to the following value.
    """
    # Define schema first, then use it explicitly
    full_text = '@User<id:int, name:string> @User(1, "Admin")'
    res = decode(full_text, debug=True)

    assert not res.errors
    node = res.node
    assert node.schema.type_name == "User"

    # Since we have a schema, positional arguments should be mapped to fields
    # Check by key (Decoder maps positional to fields if schema exists)
    assert node.fields["id"].value == 1
    assert node.fields["name"].value == "Admin"

    assert_roundtrip(node, 
                     '@User<id:number,name:string>(1,"Admin")',
                     True)




def test_nested_schema_structure():
    """Validates nested structural types."""
    # We define Profile, then User uses it.
    text = """
    @Profile<level:int>
    @User<id:int, profile: @Profile>
    @User(1, {level: 99})
    """
    print(text)
    res = decode(text, debug=True)

    assert not res.errors
    node = res.node
    print(node)

    # id should be 1
    assert node.fields["id"].value == 1

    # profile should be a node
    profile_node = node.fields["profile"]
    assert profile_node.fields["level"].value == 99

    assert_roundtrip(node, 
                     "@User<id:number,profile:@Profile<level:number>>(1,(99))",
                     True)





