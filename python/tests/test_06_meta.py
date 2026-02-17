import arkadia.ai as ai
from arkadia.ai.data import SchemaKind, Schema, Node
from utils import assert_roundtrip


# ==================================================================================
# 2. SCHEMA DEFINITION & TYPING
# ==================================================================================

def test_comments_handling():
    """Validates that comments /.../ are ignored or handled."""
    text    = '@User<id:int /*primary key*/, name:string> @User(5, "Bob")'
    expected = '@User</*primary key*/ id:number,name:string>(5,"Bob")'
    res = ai.data.decode(text)
    assert not res.errors
    # If the parser attaches schema comments to fields correctly, good.
    # Here we just ensure data parsing works despite comments.
    assert res.node.fields["id"].value == 5


    print(res.node.schema.fields)
    assert_roundtrip(text, expected, False)

def test_meta_header():
    aid_text = """
    $a0=5
    <
    /* c1 */
    / $a1  /* c0 *//
    /* c2 */ $a2=2 /* c3 */ $a3=3 a:number
    >
    ($a6 /*a*/ 3)
    """
    print(aid_text)
    expected = "<//*c0*/ $a0=5 $a1=true/ /*c1*/ /*c2*/ /*c3*/ $a2=2 $a3=3 a:number>(/*a*/ $a6=true 3)"
    assert_roundtrip(aid_text, expected)

def test_meta():
    aid_text = """
    $attr=5
    <
    /* comm2 */
    / $schema1 /
    /* comm1 */
    [a:int]
    >
    $attr=3
    [
    / /*meta for list*/ $attr=4 /
    /*item1*/ $attr5 (3 $attr6),
    /*item2*/ {a:5},
    ]
    """
    print(aid_text)
    expected = "<[//*comm2*/ /*comm1*/ $attr=5 $schema1=true/ a:number]>[//*meta for list*/ $attr=4/ (//*item1*/ $attr5=true/ $attr6=true 3),(//*item2*// 5)]"
    assert_roundtrip(aid_text, expected)


# ==============================================================================
# 1. SCHEMA DEFINITION META (Types defined in < ... >)
# ==============================================================================

def test_list_schema():
    """
    Verifies that an empty schema definition < ... > correctly parses:
    1. Comments (including nested ones).
    2. Attributes ($key=val).
    3. Tags (#tag).
    """
    aid_text = """
    /* 0 */
    < 
      /* commentm0 */ /* com1 /*com1.2*/ */
      / $listAttr="GlobalList" $b=4  #tag /
      /* comment4 */
      id:number
    >
    /* a */
    #tag1 $val=3
    [
      1,
      2,
      3
    ]
    /* b */
    """
    
    result = ai.data.decode(aid_text, debug=True)
    node = result.node
    errors = result.errors
    
    # 1. Assert no syntax errors
    assert len(errors) == 0, f"Errors found: {errors}"

    # print(node.sch)
    
    # 2. Check Schema Basics
    schema = node.schema
    print(node.encode({ "compact": True}))
    assert schema is not None
    assert schema.kind == SchemaKind.LIST # Default kind for <...>
    
    # 3. Verify Attributes ($key=val)
    # Parser should cast '4' to int if logic allows, or keep as value
    assert schema.attr.get("listAttr") == "GlobalList"
    assert schema.attr.get("b") == 4
    
    # 4. Verify Tags (#tag)
    assert "tag" in schema.tags
    assert len(schema.tags) == 1
    
    # 5. Verify Comments
    # We expect multiple comments to be collected
    print(schema.comments)

    assert len(schema.comments) == 1 # /* 0 */'
    assert "0" in schema.comments[0]
    

    expected = '<[//*0*/ $listAttr="GlobalList" $b=4 #tag/ number]>[//*a*/ /*b*/ $val=3 #tag1/ 1,2,3]'
    assert_roundtrip(aid_text, expected)


def test_empty_schema_encode():
    """
    Verifies that a Schema with meta/comments is encoded correctly{}.
    Expected format based on your output:
    < /* comment */ / $attr=val #tag / any >
    """
    
    # 1. Prepare Schema manually
    schema = Schema(SchemaKind.RECORD, fields=[])
    schema.comments = ["comment1", "comment2"]
    schema.attr = {"key": "value", "count": 10}
    schema.tags = ["myTag"]
    
    # Create a node using this schema
    node = Node(schema, value=None)
    expected = '<//*comment1*/ /*comment2*/ $key="value" $count=10 #myTag/ any>(null)'
    assert_roundtrip(node, expected)


def test_schema_round_trip_encode_decode():
    """
    Verifies that a Schema with meta/comments can be encoded to text
    and then decoded back, preserving all metadata (Round-Trip).
    """
    
    # 1. Prepare Schema manually
    original_schema = Schema(SchemaKind.RECORD, fields=[])
    original_schema.comments = ["comment1", "comment2"]
    original_schema.attr = {"key": "value", "count": 10, "isActive": True}
    original_schema.tags = ["myTag", "urgent"]

    # Create a node using this schema
    original_node = Node(original_schema, value=None)

    # 2. Encode to String
    # Important: We must enable include_comments to verify them after decoding
    config = {
        "include_comments": True,
        "compact": True, # Test compact mode (one line)
        "colorize": False 
    }
    encoded_text = original_node.encode(config)
    
    print("-" * 20 + " ENCODED TEXT " + "-" * 20)
    print(encoded_text)
    print("-" * 54)

    # 3. Decode back to Node
    result = ai.data.decode(encoded_text, debug=True)
    decoded_node = result.node
    errors = result.errors

    # 4. Verify No Errors
    assert len(errors) == 0, f"Decode errors found: {errors}"
    assert decoded_node is not None
    
    # 5. Verify Schema Integrity
    decoded_schema = decoded_node.schema
    assert decoded_schema is not None
    assert decoded_schema.kind == SchemaKind.RECORD

    # 6. Verify Meta Data (Attributes)
    # Note: Depending on parser implementation, 'value' might be single or double quoted string
    assert decoded_schema.attr["key"] == "value"
    assert decoded_schema.attr["count"] == 10
    assert decoded_schema.attr["isActive"] is True
    
    # 7. Verify Tags
    assert "myTag" in decoded_schema.tags
    assert "urgent" in decoded_schema.tags
    assert len(decoded_schema.tags) == 2

    # 8. Verify Comments
    # The decoder might concatenate them or keep as list, depending on logic.
    # Assuming the parser collects them into the list:
    assert len(decoded_schema.comments) == 2
    assert "comment1" in decoded_schema.comments
    assert "comment2" in decoded_schema.comments


    decoded_text = decoded_node.encode({
        "compact": True,
        "include_meta": False
    })
    
    print(decoded_text)


    decoded_text_no_meta = decoded_node.encode({
        "compact": True,
        "include_type": False,
        "include_meta": True
    })

    print(decoded_text_no_meta)


    # A. Encode WITHOUT Meta (include_meta=False)
    # Oczekujemy, że tagi i atrybuty znikną z outputu.
    decoded_text_clean = decoded_node.encode({
        "compact": True,
        "include_meta": False,
        "include_comments": False
    })
    
    print(f"\n[No Meta]: {decoded_text_clean}")
    
    # Assertions for No Meta
    assert "$key" not in decoded_text_clean
    assert "#myTag" not in decoded_text_clean
    assert "/" not in decoded_text_clean # Brak bloku meta
    assert "<any>" in decoded_text_clean or "< any >" in decoded_text_clean # Pusty schemat bez meta

    # B. Encode WITH Meta (include_meta=True) but NO Type (include_type=False)
    decoded_text_with_meta = decoded_node.encode({
        "compact": True,
        "include_type": False,
        "include_meta": True,
        "include_comments": False
    })

    print(f"\n[With Meta]: {decoded_text_with_meta}")

    # Assertions for With Meta
    assert "$key=" in decoded_text_with_meta
    assert "#myTag" in decoded_text_with_meta
    assert "$count=10" in decoded_text_with_meta
    assert "/" in decoded_text_with_meta


    expected = '<//*comment1*/ /*comment2*/ $key="value" $count=10 $isActive=true #myTag #urgent/ any>(null)'
    assert_roundtrip(original_node, expected, True)


def test_meta_schema_list_vs_element():
    """
    Tests nested metadata within a type definition:
    Outer: / $listAttr="GlobalList" /  -> Applies to the entire List
    Inner: / $elemAttr="InnerRecord" / -> Applies to the Element (Record) inside
    """
    aid_text = """
    < 
      /* comm-header-0 */ /* comm-header-1 /* comm-header-1.1*/ */
      / $listAttr="GlobalList" $b=4 /*com-in*/ /
      /* comm-after-header-0 */
      [ 
        / $elemAttr="InnerRecord" #elem0 /* comm-inside-header-0 */ /
        /* comm-inside-field-0 */ #elem1 id: int    
      ]
    >
    [ /* comm-data-v1 */  (1) /* comm-data-v2 */ ]
    """
    
    results = ai.data.decode(aid_text, debug=True)
    node = results.node
    errors = results.errors

    assert len(errors) == 0

    # 1. Check List Meta (Outer)
    assert node.is_list
    # Access attributes via .attr (Mixin)
    assert node.schema.attr.get("listAttr") == "GlobalList"
    assert node.schema.attr.get("elemAttr") == "InnerRecord"
    assert node.schema.attr.get("b") == 4
    
    # 2. Check Element Meta (Inner Record)
    elem_schema = node.schema.element
    assert elem_schema.kind == SchemaKind.RECORD
    assert elem_schema.attr == {}
    assert node.elements[0].schema.attr == {}

    print(node.encode({
        "colorize": True,
        "compact": False
    }))

    expected = '<[//*com-in*/ /*comm-header-0*/ /*comm-header-1 /* comm-header-1.1*/*/ /*comm-after-header-0*/ /*comm-inside-header-0*/ $listAttr="GlobalList" $b=4 $elemAttr="InnerRecord" #elem0/ /*comm-inside-field-0*/ #elem1 id:number]>[(//*comm-data-v1*/ /*comm-data-v2*// 1)]'
    assert_roundtrip(aid_text, expected, True)


def test_meta_schema_before():
    """
    Tests nested metadata within a type definition:
    Outer: / $listAttr="GlobalList" /  -> Applies to the entire List
    Inner: / $elemAttr="InnerRecord" / -> Applies to the Element (Record) inside
    """
    aid_text = """
    < 
      /* header-com-0 */
      / #tag_header /
      /* comm-data-v1 */ #tag1 v1: number /* comm-data-v2 */ #tag2,
      /* comm-data-v3 */ #tag3 v2: number /* comm-data-v3 */ #tag4
    >
    [ 
     / #tag_list /
     /* comm-data-v1 */ #tag1 1 /* comm-data-v2 */ #tag2
     /* comm-data-v3 */ #tag3 2 /* comm-data-v3 */ #tag4
    ]
    """
    
    results = ai.data.decode(aid_text, debug=True)
    node = results.node
    errors = results.errors
    assert len(errors) == 0
    print(node.encode({
        "colorize": True,
    }))

    expected = '<[/#tag_header/ number]>[/#tag_list/ /*comm-data-v1*/ #tag1 1,/*comm-data-v2*/ /*comm-data-v3*/ /*comm-data-v3*/ #tag2 #tag3 #tag4 2]'
    assert_roundtrip(aid_text, expected, True)


def test_meta_schema_with_wrong_values():
    """
    Tests handling of malformed meta blocks.
    In the input: / elemAttr="InnerRecord" / is missing '$' prefix for attribute.
    The parser should likely report an error or skip it, but let's see how resilient it is.
    Assuming strict parsing: 'elemAttr="InnerRecord"' is not valid inside meta block (expects $key=val, #tag, !flag).
    """
    aid_text = """
    < 
      / listAttr="GlobalList" /
      [ 
        /* Missing $ prefix */
        / $elemAttr="InnerRecord" /* fixed input */ /
        /* comments2 */ id: int
      ] 
    >
    [ (1) ]
    """
    
    results = ai.data.decode(aid_text, debug=True)
    node = results.node
    errors = results.errors
    warnings = results.warnings
    print(results.warnings)

   

    print(results)
    print(ai.data.encode(results.node, {
        "compact": True,
        "colorize": True
    }))


    # If the input was fixed above, errors should be 0.
    # Because we have: listAttr="GlobalList", 
    # it should be one error: 'ERROR: Parsed attribute (implicit), expected: '$', parsed as: $listAttr='GlobalList''
    assert len(warnings) == 1
    assert "Implicit attribute 'listAttr'. Use '$listAttr' instead" in warnings[0].message

    # 1. Check List Meta (Outer)
    assert node.is_list
    assert node.schema.attr.get("listAttr") == "GlobalList"
    
    # 2. Check Element Meta (Inner Record)
    elem_schema = node.schema.element
    assert elem_schema.kind == SchemaKind.RECORD
    assert node.schema.attr.get("elemAttr") == "InnerRecord"


    expected = '<[//*fixed input*/ $listAttr="GlobalList" $elemAttr="InnerRecord"/ /*Missing $ prefix*/ /*comments2*/ id:number]>[(1)]'
    assert_roundtrip(aid_text, expected, True)


def test_meta_schema_field_modifiers():
    """
    Tests field modifiers inside a record definition: !required, $key=value.
    New Syntax: Field definition should look like:
    / !required $key=101 / id: int
    """
    aid_text = """
    <
        /* comm0 */
        / $id=0  /*comm2 /* comm2.5*/ */ /

        /* comm3 */
        
        /* Modifiers block before field name */
        !required $key=101  id:int,

        $desc="User Name"
        name: string
    >
    ( /* comment0 */ / $id=3 /*comment2*/ / /*comment3*/ 1, "Alice" $id=65 #alice /*comment4*/ )
    """
    
    results = ai.data.decode(aid_text, debug=True)
    node = results.node
    errors = results.errors

    print(node)

    assert len(errors) == 0
    assert node.is_record 
    
    # Retrieve field definitions from schema
    fields = node.schema.fields
    
    # Field 'id'
    f_id = next(f for f in fields if f.name == "id")
    assert f_id.required is True
    assert f_id.attr.get("key") == 101
    
    # Field 'name'
    f_name = next(f for f in fields if f.name == "name")
    assert f_name.required is False # Default
    assert f_name.attr.get("desc") == "User Name"

    # Check Instance Data Meta (the node itself, not the schema)
    # The record instance has / $id=3 /
    assert node.attr.get("id") == 3

    expected = '<//*comm2 /* comm2.5*/*/ $id=0/ /*comm0*/ /*comm3*/ /*Modifiers block before field name*/ !required $key=101 id:number,$desc="User Name" name:string>(//*comment2*/ $id=3/ /*comment0*/ /*comment3*/ 1,/*comment4*/ $id=65 #alice "Alice")'
    assert_roundtrip(aid_text, expected, True)




# ==============================================================================
# 2. DATA BLOCK META (Metadata inside data blocks [ ... ])
# ==============================================================================

def test_meta_data_block_list_primitive():
    """
    Tests metadata inside a data block for a simple list.
    Syntax: [ / @size=3 / 1, 2, 3 ]
    """
    aid_text = '[ / $size=3 $author="me" / 1, 2, 3 ]'
    
    results = ai.data.decode(aid_text, debug=True)
    node = results.node
    errors = results.errors
    assert len(errors) == 0
    
    assert node.is_list
    # Meta should go to this specific node's schema
    assert node.attr.get("size") == 3
    assert node.attr.get("author") == "me"
    
    # Check content
    assert len(node.elements) == 3
    assert node.elements[0].value == 1

    expected = '<[number]>[/$size=3 $author="me"/ 1,2,3]'
    assert_roundtrip(aid_text, expected, True)



# ==============================================================================
# 3. NESTED META (Lists within lists)
# ==============================================================================

def test_meta_nested_lists():
    """
    Tests metadata assignment in nested lists.
    Structure: [ /@level=0/  [ /@level=1/ 1, 2 ] ]
    """
    aid_text = """
    [ 
      / $level=0 /
      [ 
        / $level=1 / 
        1, 2 
      ],
      [
        / $level=2 /
        3, 4
      ]
    ]
    """
    
    results = ai.data.decode(aid_text, debug=True)
    node = results.node
    errors = results.errors
    assert len(errors) == 0
    
    # Root Node
    assert node.is_list
    assert node.attr.get("level") == 0
    
    # Inner Node 1
    inner1 = node.elements[0]
    assert inner1.is_list
    assert inner1.attr.get("level") == 1
    
    # Inner Node 2
    inner2 = node.elements[1]
    assert inner2.is_list
    assert inner2.attr.get("level") == 2


    expected = '<[[number]]>[/$level=0/ [/$level=1/ 1,2],[/$level=2/ 3,4]]'
    assert_roundtrip(aid_text, expected, True)


# ==============================================================================
# 4. EDGE CASES & OVERRIDES
# ==============================================================================

def test_meta_mixed_with_type_override():
    """
    Tests a scenario where we have metadata for the list AND a type override for an element.
    """
    aid_text = '[ / $info="mixed" / 1, 2, <string> "3" ]'
    expected = '<[number]>[/$info="mixed"/ 1,2,<string> "3"]'
    
    result = ai.data.decode(aid_text)
    node = result.node
    errors = result.errors
    assert len(errors) == 0
    
    # List Meta
    assert node.attr.get("info") == "mixed"
    
    # List Type Inference (Should be Number/Int based on first element '1')
    assert node.schema.element.type_name in ["number", "int"]
    
    # Element Override
    el_last = node.elements[2]
    assert el_last.schema.type_name == "string"
    assert el_last.value == "3"

    assert_roundtrip(node, expected, True)


def test_meta_and_explicit_type_in_data():
    """
    Tests a scenario where an explicit type is provided inside the / ... / block.
    [ / @tag=1 int / 1, 2 ]
    The parser must understand that 'int' is the list type, and @tag is metadata.
    """
    aid_text = '[ / $tag=1 / 1, 2 ]'
    
    result = ai.data.decode(aid_text)
    node = result.node
    errors = result.errors
    assert len(errors) == 0
    
    print(node)
    assert node.is_list
    assert node.schema.element.type_name == "number"

    assert len(getattr(node, "attr", {}).keys()) == 1

    expected = "<[number]>[/$tag=1/ 1,2]"
    assert_roundtrip(node, expected, True)