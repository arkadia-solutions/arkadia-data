import arkadia.ai as ai
from arkadia.ai.data import SchemaKind
from utils import assert_roundtrip

# ==============================================================================
# 1. SCHEMA DEFINITION META (Types defined in < ... >)
# ==============================================================================

def test_different_type_in_record():
    aid_text = """
    < 
      id: number
    >
    ( ["text"] )
    """

    
    result = ai.data.decode(aid_text)
    node = result.node
    errors = result.errors
    assert len(errors) == 0
    
    # 1. Check Record Meta (Outer)
    assert node.is_record

    excepted = '<id:number>(<[string]> ["text"])'
    assert_roundtrip(node, excepted, True)


def test_simple_types():
    aid_text = '{ a:"a", b:"b", c:"c", d: 3 }'
    excepted = '<a:string,b:string,c:string,d:number>("a","b","c",3)'
    assert_roundtrip(aid_text, excepted, True)   
    

def test_record_named_type_mismatch():
    """
    Tests a scenario where a positional record field has a defined type (e.g., string),
    but the actual value inside is of a different type (e.g., int).

    This ensures that the _record method in Encoder uses _apply_type_tag correctly.

    Schema: <test: string>
    Data: (3)
    Expected Output: (<number> 3)
    """

    # 1. Input in AID format
    aid_text = """
<tests: string>
{
 tests: 3
}
    """

    excepted = '<tests:string>(<number> 3)'
    assert_roundtrip(aid_text, excepted, True)   


def test_record_positional_type_mismatch():
    """
    Tests a scenario where a positional record field has a defined type (e.g., string),
    but the actual value inside is of a different type (e.g., int).

    This ensures that the _record method in Encoder uses _apply_type_tag correctly.

    Schema: <test: string>
    Data: (3)
    Expected Output: (<number> 3)
    """

    # 1. Input in AID format
    aid_text = """
<tests: string>
(3)
    """

    excepted = '<tests:string>(<number> 3)'
    assert_roundtrip(aid_text, excepted, True)   
