import { describe, expect, it } from 'vitest';
import { decode, encode, Node, Schema, SchemaKind } from '../src/index';
import { assertRoundtrip } from './utils';

describe('AK Data Metadata (Meta)', () => {
  // ==================================================================================
  // 2. SCHEMA DEFINITION & TYPING
  // ==================================================================================

  it('should handle comments', () => {
    /** Validates that comments / * ... * / are handled correctly. */
    const text = '@User<id:int /*primary key*/, name:string> @User(5, "Bob")';
    // Note: int normalizes to number in TS
    const expected = '@User</*primary key*/ id:number,name:string>(5,"Bob")';

    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    expect(res.node.fields['id'].value).toBe(5);

    assertRoundtrip(text, expected, false);
  });

  it('should handle meta header', () => {
    const akdText = `
        $a0=5
        <
        /* c1 */
        // $a1  /* c0 *///
        /* c2 */ $a2=2 /* c3 */ $a3=3 a:number
        >
        ($a6 /*a*/ 3)
        `;

    const expected =
      '<///*c0*/ $a0=5 $a1// /*c1*/ /*c2*/ /*c3*/ $a2=2 $a3=3 a:number>(/*a*/ $a6 3)';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle mixed meta', () => {
    const akdText = `
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
        `;

    const expected =
      '<[///*comm2*/ /*comm1*/ $attr=5 $schema1// a:number]>[///*meta for list*/ $attr=4// (///*item1*/ $attr5// $attr6 3),(///*item2*/// 5)]';
    assertRoundtrip(akdText, expected, false);
  });

  // ==============================================================================
  // 1. SCHEMA DEFINITION META (Types defined in < ... >)
  // ==============================================================================

  it('should handle list schema with meta', () => {
    const akdText = `
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
        `;

    const result = decode(akdText, { debug: false });
    const node = result.node;

    expect(result.errors).toHaveLength(0);

    const schema = node.schema;
    expect(schema).not.toBeNull();
    expect(schema!.kind).toBe(SchemaKind.LIST);

    expect(schema!.attr['listAttr']).toBe('GlobalList');
    expect(schema!.attr['b']).toBe(4);
    expect(schema!.tags).toContain('tag');

    const expected =
      '<[///*0*/ $listAttr="GlobalList" $b=4 #tag// number]>[///*a*/ /*b*/ $val=3 #tag1// 1,2,3]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should encode manual schema with meta', () => {
    const schema = new Schema(SchemaKind.RECORD);
    schema.comments = ['comment1', 'comment2'];
    schema.attr = { key: 'value', count: 10 };
    schema.tags = ['myTag'];

    const node = new Node(schema, { value: null });
    const expected = '<///*comment1*/ /*comment2*/ $key="value" $count=10 #myTag// any>(null)';

    assertRoundtrip(node, expected, false);
  });

  it('should round trip schema encode decode', () => {
    const originalSchema = new Schema(SchemaKind.RECORD);
    originalSchema.comments = ['comment1', 'comment2'];
    originalSchema.attr = { key: 'value', count: 10, isActive: true };
    originalSchema.tags = ['myTag', 'urgent'];

    const originalNode = new Node(originalSchema, { value: null });

    const encodedText = encode(originalNode, {
      includeComments: true,
      compact: true,
      colorize: false,
    });

    const result = decode(encodedText, { debug: false });
    const decodedNode = result.node;

    expect(result.errors).toHaveLength(0);
    expect(decodedNode.schema!.attr['key']).toBe('value');
    expect(decodedNode.schema!.tags).toContain('urgent');

    // Test cleaning meta
    const decodedTextClean = encode(decodedNode, {
      compact: true,
      includeMeta: false,
      includeComments: false,
    });

    expect(decodedTextClean).not.toContain('$key');
    expect(decodedTextClean).not.toContain('//');

    const expected =
      '<///*comment1*/ /*comment2*/ $key="value" $count=10 $isActive #myTag #urgent// any>(null)';
    assertRoundtrip(originalNode, expected, false);
  });

  it('should handle meta schema list vs element', () => {
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;

    expect(results.errors).toHaveLength(0);
    expect(node.schema!.attr['listAttr']).toBe('GlobalList');
    expect(node.schema!.attr['elemAttr']).toBe('InnerRecord');

    const expected =
      '<[///*com-in*/ /*comm-header-0*/ /*comm-header-1 /* comm-header-1.1*/*/ /*comm-after-header-0*/ /*comm-inside-header-0*/ $listAttr="GlobalList" $b=4 $elemAttr="InnerRecord" #elem0// /*comm-inside-field-0*/ #elem1 id:number]>[(///*comm-data-v1*/ /*comm-data-v2*/// 1)]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta schema before fields', () => {
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    expect(results.errors).toHaveLength(0);

    const expected =
      '<[//#tag_header// number]>[//#tag_list// /*comm-data-v1*/ #tag1 1,/*comm-data-v2*/ /*comm-data-v3*/ /*comm-data-v3*/ #tag2 #tag3 #tag4 2]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should warn on meta schema with implicit values', () => {
    const akdText = `
        < 
          // listAttr="GlobalList" //
          [ 
            /* Missing $ prefix */
            // $elemAttr="InnerRecord" /* fixed input */ //
            /* comments2 */ id: int
          ] 
        >
        [ (1) ]
        `;

    const results = decode(akdText, { debug: false });
    expect(results.warnings.length).toBeGreaterThan(0);
    expect(results.warnings[0].message).toContain("Implicit attribute 'listAttr'");

    const expected =
      '<[///*fixed input*/ $listAttr="GlobalList" $elemAttr="InnerRecord"// /*Missing $ prefix*/ /*comments2*/ id:number]>[(1)]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta schema field modifiers', () => {
    const akdText = `
        <
            /* comm0 */
            // $id=0  /*comm2 /* comm2.5*/ */ //

            /* comm3 */
            
            /* Modifiers block before field name */
            $required $key=101  id:int,

            $desc="User Name"
            name: string
        >
        ( /* comment0 */ // $id=3 /*comment2*/ // /*comment3*/ 1, "Alice" $id=65 #alice /*comment4*/ )
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;
    expect(results.errors).toHaveLength(0);

    const fId = node.schema!.fields.find((f) => f.name === 'id')!;
    expect(fId.required).toBe(true);
    expect(fId.attr['key']).toBe(101);
    expect(node.attr['id']).toBe(3);

    const expected =
      '<///*comm2 /* comm2.5*/*/ $id=0// /*comm0*/ /*comm3*/ /*Modifiers block before field name*/ $required $key=101 id:number,$desc="User Name" name:string>(///*comment2*/ $id=3// /*comment0*/ /*comment3*/ 1,/*comment4*/ $id=65 #alice "Alice")';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta data block list primitive', () => {
    const akdText = '[ // $size=3 $author="me" // 1, 2, 3 ]';

    const results = decode(akdText, { debug: false });
    const node = results.node;
    expect(results.errors).toHaveLength(0);

    expect(node.attr['size']).toBe(3);
    expect(node.attr['author']).toBe('me');

    const expected = '<[number]>[//$size=3 $author="me"// 1,2,3]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta nested lists', () => {
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;
    expect(results.errors).toHaveLength(0);

    expect(node.attr['level']).toBe(0);
    expect(node.elements[0].attr['level']).toBe(1);
    expect(node.elements[1].attr['level']).toBe(2);

    const expected = '<[[number]]>[//$level=0// [//$level=1// 1,2],[//$level=2// 3,4]]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta mixed with type override', () => {
    const akdText = '[ // $info="mixed" // 1, 2, <string> "3" ]';
    const expected = '<[number]>[//$info="mixed"// 1,2,<string> "3"]';

    const result = decode(akdText, { debug: false });
    expect(result.errors).toHaveLength(0);
    expect(result.node.attr['info']).toBe('mixed');
    expect(result.node.schema!.element?.typeName).toBe('number');

    assertRoundtrip(result.node, expected, false);
  });

  it('should handle meta and explicit type in data', () => {
    const akdText = '[ // $tag=1 // 1, 2 ]';

    const result = decode(akdText, { debug: false });
    expect(result.errors).toHaveLength(0);
    expect(result.node.attr['tag']).toBe(1);

    const expected = '<[number]>[//$tag=1// 1,2]';
    assertRoundtrip(result.node, expected, false);
  });
});
