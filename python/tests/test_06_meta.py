from utils import assert_roundtrip

import arkadia as ak
from arkadia.data import Node, Schema, SchemaKind

# ==================================================================================
# 2. SCHEMA DEFINITION & TYPING
# ==================================================================================


def test_comments_handling():
    """Validates that comments /*...*/ are handled correctly."""
    text = '@User<id:int /*primary key*/, name:string> @User(5, "Bob")'
    expected = '@User</*primary key*/ id:number,name:string>(5,"Bob")'
    res = ak.data.decode(text)
    assert not res.errors
    assert res.node.fields["id"].value == 5
    assert_roundtrip(text, expected, False)


def test_meta_header():
    akd_text = """
    $a0=5
    <
    /* c1 */
    // $a1  /* c0 */ //
    /* c2 */ $a2=2 /* c3 */ $a3=3 a:number
    >
    ($a6 /*a*/ 3)
    """
    expected = "<///*c0*/ $a0=5 $a1=true// /*c1*/ /*c2*/ /*c3*/ $a2=2 $a3=3 a:number>(/*a*/ $a6=true 3)"
    assert_roundtrip(akd_text, expected)


def test_meta():
    akd_text = """
    $attr=5
    <
    /* comm2 */
    // $schema1 //
    /* comm1 */
    [a:int]
    >
    $attr=3
    [
    // /*meta for list*/ $attr=4 //
    /*item1*/ $attr5 (3 $attr6),
    /*item2*/ {a:5},
    ]
    """
    expected = "<[///*comm2*/ /*comm1*/ $attr=5 $schema1=true// a:number]>[///*meta for list*/ $attr=4// (///*item1*/ $attr5=true// $attr6=true 3),(///*item2*/// 5)]"
    assert_roundtrip(akd_text, expected)


# ==============================================================================
# 1. SCHEMA DEFINITION META (Types defined in < ... >)
# ==============================================================================


def test_list_schema():
    akd_text = """
    /* 0 */
    < 
      /* commentm0 */ /* com1 /*com1.2*/ */
      // $listAttr="GlobalList" $b=4  #tag //
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

    result = ak.data.decode(akd_text, debug=True)
    node = result.node
    errors = result.errors

    assert len(errors) == 0
    schema = node.schema
    assert schema.kind == SchemaKind.LIST

    assert schema.attr.get("listAttr") == "GlobalList"
    assert schema.attr.get("b") == 4
    assert "tag" in schema.tags
    assert len(schema.comments) == 1
    assert "0" in schema.comments[0]

    expected = '<[///*0*/ $listAttr="GlobalList" $b=4 #tag// number]>[///*a*/ /*b*/ $val=3 #tag1// 1,2,3]'
    assert_roundtrip(akd_text, expected)


def test_empty_schema_encode():
    schema = Schema(SchemaKind.RECORD, fields=[])
    schema.comments = ["comment1", "comment2"]
    schema.attr = {"key": "value", "count": 10}
    schema.tags = ["myTag"]

    node = Node(schema, value=None)
    expected = '<///*comment1*/ /*comment2*/ $key="value" $count=10 #myTag// any>(null)'
    assert_roundtrip(node, expected)


def test_schema_round_trip_encode_decode():
    original_schema = Schema(SchemaKind.RECORD, fields=[])
    original_schema.comments = ["comment1", "comment2"]
    original_schema.attr = {"key": "value", "count": 10, "isActive": True}
    original_schema.tags = ["myTag", "urgent"]

    original_node = Node(original_schema, value=None)

    config = {
        "include_comments": True,
        "compact": True,
        "colorize": False,
    }
    encoded_text = original_node.encode(config)

    result = ak.data.decode(encoded_text, debug=True)
    decoded_node = result.node
    assert len(result.errors) == 0

    decoded_schema = decoded_node.schema
    assert decoded_schema.attr["key"] == "value"
    assert decoded_schema.attr["count"] == 10
    assert decoded_schema.attr["isActive"] is True
    assert "myTag" in decoded_schema.tags
    assert len(decoded_schema.comments) == 2

    # Verify no meta encoding
    decoded_text_clean = decoded_node.encode(
        {"compact": True, "include_meta": False, "include_comments": False}
    )
    assert "$" not in decoded_text_clean
    assert "#" not in decoded_text_clean
    assert "//" not in decoded_text_clean

    expected = '<///*comment1*/ /*comment2*/ $key="value" $count=10 $isActive=true #myTag #urgent// any>(null)'
    assert_roundtrip(original_node, expected, True)


def test_meta_schema_list_vs_element():
    akd_text = """
    < 
      /* comm-header-0 */ /* comm-header-1 /* comm-header-1.1*/ */
      // $listAttr="GlobalList" $b=4 /*com-in*/ //
      /* comm-after-header-0 */
      [ 
        // $elemAttr="InnerRecord" #elem0 /* comm-inside-header-0 */ //
        /* comm-inside-field-0 */ #elem1 id: int    
      ]
    >
    [ /* comm-data-v1 */  (1) /* comm-data-v2 */ ]
    """

    results = ak.data.decode(akd_text, debug=True)
    node = results.node
    assert len(results.errors) == 0

    assert node.schema.attr.get("listAttr") == "GlobalList"
    assert node.schema.attr.get("elemAttr") == "InnerRecord"

    expected = '<[///*com-in*/ /*comm-header-0*/ /*comm-header-1 /* comm-header-1.1*/*/ /*comm-after-header-0*/ /*comm-inside-header-0*/ $listAttr="GlobalList" $b=4 $elemAttr="InnerRecord" #elem0// /*comm-inside-field-0*/ #elem1 id:number]>[(///*comm-data-v1*/ /*comm-data-v2*/// 1)]'
    assert_roundtrip(akd_text, expected, True)


def test_meta_schema_before():
    akd_text = """
    < 
      /* header-com-0 */
      // #tag_header //
      /* comm-data-v1 */ #tag1 v1: number /* comm-data-v2 */ #tag2,
      /* comm-data-v3 */ #tag3 v2: number /* comm-data-v3 */ #tag4
    >
    [ 
     // #tag_list //
     /* comm-data-v1 */ #tag1 1 /* comm-data-v2 */ #tag2
     /* comm-data-v3 */ #tag3 2 /* comm-data-v3 */ #tag4
    ]
    """

    results = ak.data.decode(akd_text, debug=True)
    assert len(results.errors) == 0

    expected = "<[//#tag_header// number]>[//#tag_list// /*comm-data-v1*/ #tag1 1,/*comm-data-v2*/ /*comm-data-v3*/ /*comm-data-v3*/ #tag2 #tag3 #tag4 2]"
    assert_roundtrip(akd_text, expected, True)


def test_meta_schema_with_wrong_values():
    akd_text = """
    < 
      // listAttr="GlobalList" //
      [ 
        /* Missing $ prefix */
        // $elemAttr="InnerRecord" /* fixed input */ //
        /* comments2 */ id: int
      ] 
    >
    [ (1) ]
    """

    results = ak.data.decode(akd_text, debug=True)
    assert len(results.warnings) == 1
    assert "Implicit attribute" in results.warnings[0].message

    node = results.node
    assert node.schema.attr.get("listAttr") == "GlobalList"
    assert node.schema.attr.get("elemAttr") == "InnerRecord"

    expected = '<[///*fixed input*/ $listAttr="GlobalList" $elemAttr="InnerRecord"// /*Missing $ prefix*/ /*comments2*/ id:number]>[(1)]'
    assert_roundtrip(akd_text, expected, True)


def test_meta_schema_field_modifiers():
    akd_text = """
    <
        /* comm0 */
        // $id=0  /*comm2 /* comm2.5*/ */ //

        /* comm3 */
        
        /* Modifiers block before field name */
        !required $key=101  id:int,

        $desc="User Name"
        name: string
    >
    ( /* comment0 */ // $id=3 /*comment2*/ // /*comment3*/ 1, "Alice" $id=65 #alice /*comment4*/ )
    """

    results = ak.data.decode(akd_text, debug=True)
    node = results.node
    assert len(results.errors) == 0

    fields = node.schema.fields
    f_id = next(f for f in fields if f.name == "id")
    assert f_id.required is True
    assert f_id.attr.get("key") == 101

    assert node.attr.get("id") == 3

    expected = '<///*comm2 /* comm2.5*/*/ $id=0// /*comm0*/ /*comm3*/ /*Modifiers block before field name*/ !required $key=101 id:number,$desc="User Name" name:string>(///*comment2*/ $id=3// /*comment0*/ /*comment3*/ 1,/*comment4*/ $id=65 #alice "Alice")'
    assert_roundtrip(akd_text, expected, True)


# ==============================================================================
# 2. DATA BLOCK META (Metadata inside data blocks [ ... ])
# ==============================================================================


def test_meta_data_block_list_primitive():
    akd_text = '[ // $size=3 $author="me" // 1, 2, 3 ]'

    results = ak.data.decode(akd_text, debug=True)
    node = results.node
    assert len(results.errors) == 0

    assert node.attr.get("size") == 3
    assert node.attr.get("author") == "me"

    expected = '<[number]>[//$size=3 $author="me"// 1,2,3]'
    assert_roundtrip(akd_text, expected, True)


# ==============================================================================
# 3. NESTED META (Lists within lists)
# ==============================================================================


def test_meta_nested_lists():
    akd_text = """
    [ 
      // $level=0 //
      [ 
        // $level=1 // 
        1, 2 
      ],
      [
        // $level=2 //
        3, 4
      ]
    ]
    """

    results = ak.data.decode(akd_text, debug=True)
    node = results.node
    assert len(results.errors) == 0

    assert node.attr.get("level") == 0
    assert node.elements[0].attr.get("level") == 1
    assert node.elements[1].attr.get("level") == 2

    expected = "<[[number]]>[//$level=0// [//$level=1// 1,2],[//$level=2// 3,4]]"
    assert_roundtrip(akd_text, expected, True)


# ==============================================================================
# 4. EDGE CASES & OVERRIDES
# ==============================================================================


def test_meta_mixed_with_type_override():
    akd_text = '[ // $info="mixed" // 1, 2, <string> "3" ]'
    expected = '<[number]>[//$info="mixed"// 1,2,<string> "3"]'

    result = ak.data.decode(akd_text)
    assert len(result.errors) == 0
    assert result.node.attr.get("info") == "mixed"
    assert result.node.elements[2].value == "3"

    assert_roundtrip(result.node, expected, True)


def test_meta_and_explicit_type_in_data():
    akd_text = "[ // $tag=1 // 1, 2 ]"

    result = ak.data.decode(akd_text)
    assert len(result.errors) == 0
    assert result.node.attr.get("tag") == 1
    assert result.node.schema.element.type_name == "number"

    expected = "<[number]>[//$tag=1// 1,2]"
    assert_roundtrip(result.node, expected, True)
