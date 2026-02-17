import { describe, expect, it } from 'vitest';
import { decode, encode, Node, Schema, SchemaKind } from '../src/index';
import { assertRoundtrip } from './utils';

describe('AK Data Metadata (Meta)', () => {
  // ==================================================================================
  // 2. SCHEMA DEFINITION & TYPING
  // ==================================================================================

  it('should handle comments', () => {
    /** Validates that comments /.../ are ignored or handled. */
    const text = '@User<id:int /*primary key*/, name:string> @User(5, "Bob")';
    // Note: int normalizes to number in TS
    const expected = '@User</*primary key*/ id:number,name:string>(5,"Bob")';

    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    // If the parser attaches schema comments to fields correctly, good.
    // Here we just ensure data parsing works despite comments.
    expect(res.node.fields['id'].value).toBe(5);

    assertRoundtrip(text, expected, false);
  });

  it('should handle meta header', () => {
    const akdText = `
        $a0=5
        <
        /* c1 */
        / $a1  /* c0 *//
        /* c2 */ $a2=2 /* c3 */ $a3=3 a:number
        >
        ($a6 /*a*/ 3)
        `;

    const expected =
      '<//*c0*/ $a0=5 $a1=true/ /*c1*/ /*c2*/ /*c3*/ $a2=2 $a3=3 a:number>(/*a*/ $a6=true 3)';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle mixed meta', () => {
    const akdText = `
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
        `;

    // Note: int -> number
    const expected =
      '<[//*comm2*/ /*comm1*/ $attr=5 $schema1=true/ a:number]>[//*meta for list*/ $attr=4/ (//*item1*/ $attr5=true/ $attr6=true 3),(//*item2*// 5)]';
    assertRoundtrip(akdText, expected, false);
  });

  // ==============================================================================
  // 1. SCHEMA DEFINITION META (Types defined in < ... >)
  // ==============================================================================

  it('should handle list schema with meta', () => {
    /**
     * Verifies that an empty schema definition < ... > correctly parses:
     * 1. Comments (including nested ones).
     * 2. Attributes ($key=val).
     * 3. Tags (#tag).
     */
    const akdText = `
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
        `;

    const result = decode(akdText, { debug: false });
    const node = result.node;
    const errors = result.errors;

    // 1. Assert no syntax errors
    expect(errors).toHaveLength(0);

    // 2. Check Schema Basics
    const schema = node.schema;
    expect(schema).not.toBeNull();
    expect(schema.kind).toBe(SchemaKind.LIST); // Default kind for <...>

    // 3. Verify Attributes ($key=val)
    // Parser casts to number if possible
    expect(schema.attr['listAttr']).toBe('GlobalList');
    expect(schema.attr['b']).toBe(4);

    // 4. Verify Tags (#tag)
    expect(schema.tags).toContain('tag');
    expect(schema.tags).toHaveLength(1);

    // 5. Verify Comments
    // We expect multiple comments to be collected
    expect(schema.comments.length).toBeGreaterThan(0);
    expect(schema.comments.some((c) => c.includes('0'))).toBe(true);

    const expected =
      '<[//*0*/ $listAttr="GlobalList" $b=4 #tag/ number]>[//*a*/ /*b*/ $val=3 #tag1/ 1,2,3]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should encode manual schema with meta', () => {
    /**
     * Verifies that a Schema with meta/comments is encoded correctly.
     * Expected format: < / $attr=val #tag / any >
     */

    // 1. Prepare Schema manually
    const schema = new Schema(SchemaKind.RECORD);
    schema.comments = ['comment1', 'comment2'];
    schema.attr = { key: 'value', count: 10 };
    schema.tags = ['myTag'];

    // Create a node using this schema
    const node = new Node(schema, { value: null });
    const expected = '<//*comment1*/ /*comment2*/ $key="value" $count=10 #myTag/ any>(null)';

    assertRoundtrip(node, expected, false);
  });

  it('should round trip schema encode decode', () => {
    /**
     * Verifies that a Schema with meta/comments can be encoded to text
     * and then decoded back, preserving all metadata (Round-Trip).
     */

    // 1. Prepare Schema manually
    const originalSchema = new Schema(SchemaKind.RECORD);
    originalSchema.comments = ['comment1', 'comment2'];
    originalSchema.attr = { key: 'value', count: 10, isActive: true };
    originalSchema.tags = ['myTag', 'urgent'];

    // Create a node using this schema
    const originalNode = new Node(originalSchema, { value: null });

    // 2. Encode to String
    // Important: We must enable include_comments to verify them after decoding
    const encodedText = encode(originalNode, {
      includeComments: true,
      compact: true, // Test compact mode (one line)
      colorize: false,
    });

    // 3. Decode back to Node
    const result = decode(encodedText, { debug: false });
    const decodedNode = result.node;
    const errors = result.errors;

    // 4. Verify No Errors
    expect(errors).toHaveLength(0);
    expect(decodedNode).not.toBeNull();

    // 5. Verify Schema Integrity
    const decodedSchema = decodedNode.schema;
    expect(decodedSchema).not.toBeNull();
    expect(decodedSchema.kind).toBe(SchemaKind.RECORD);

    // 6. Verify Meta Data (Attributes)
    expect(decodedSchema.attr['key']).toBe('value');
    expect(decodedSchema.attr['count']).toBe(10);
    expect(decodedSchema.attr['isActive']).toBe(true);

    // 7. Verify Tags
    expect(decodedSchema.tags).toContain('myTag');
    expect(decodedSchema.tags).toContain('urgent');
    expect(decodedSchema.tags).toHaveLength(2);

    // 8. Verify Comments
    expect(decodedSchema.comments).toHaveLength(2);
    expect(decodedSchema.comments).toContain('comment1');
    expect(decodedSchema.comments).toContain('comment2');

    // Additional checks for configuration flags
    const decodedTextClean = encode(decodedNode, {
      compact: true,
      includeMeta: false,
      includeComments: false,
    });

    // Assertions for No Meta
    expect(decodedTextClean).not.toContain('$key');
    expect(decodedTextClean).not.toContain('#myTag');
    expect(decodedTextClean).not.toContain('/'); // No meta block
    // Empty schema without meta encodes to <any> or similar
    expect(decodedTextClean).toContain('<any>');

    // B. Encode WITH Meta (includeMeta=true) but NO Type (includeType=false)
    const decodedTextWithMeta = encode(decodedNode, {
      compact: true,
      includeType: false,
      includeMeta: true,
      includeComments: false,
    });

    // Assertions for With Meta
    expect(decodedTextWithMeta).toContain('$key=');
    expect(decodedTextWithMeta).toContain('#myTag');
    expect(decodedTextWithMeta).toContain('$count=10');
    expect(decodedTextWithMeta).toContain('/');

    const expected =
      '<//*comment1*/ /*comment2*/ $key="value" $count=10 $isActive=true #myTag #urgent/ any>(null)';
    assertRoundtrip(originalNode, expected, false);
  });

  it('should handle meta schema list vs element', () => {
    /**
     * Tests nested metadata within a type definition:
     * Outer: / $listAttr="GlobalList" /  -> Applies to the entire List
     * Inner: / $elemAttr="InnerRecord" / -> Applies to the Element (Record) inside
     */
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;
    const errors = results.errors;

    expect(errors).toHaveLength(0);

    // 1. Check List Meta (Outer)
    expect(node.isList).toBe(true);
    // Access attributes via .attr (Mixin)
    expect(node.schema.attr['listAttr']).toBe('GlobalList');
    expect(node.schema.attr['elemAttr']).toBe('InnerRecord');

    expect(node.schema.attr['b']).toBe(4);

    // 2. Check Element Meta (Inner Record)
    const elemSchema = node.schema.element!;
    expect(elemSchema.kind).toBe(SchemaKind.RECORD);
    expect(elemSchema.attr).toStrictEqual({});

    // Check if element meta propagated to actual data elements (depends on implementation)
    // Usually schema meta is on schema, data meta is on data node.
    // Here we check the schema attached to the element node.
    expect(node.elements[0].schema.attr).toStrictEqual({});

    const expected =
      '<[//*com-in*/ /*comm-header-0*/ /*comm-header-1 /* comm-header-1.1*/*/ /*comm-after-header-0*/ /*comm-inside-header-0*/ $listAttr="GlobalList" $b=4 $elemAttr="InnerRecord" #elem0/ /*comm-inside-field-0*/ #elem1 id:number]>[(//*comm-data-v1*/ /*comm-data-v2*// 1)]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta schema before fields', () => {
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    expect(results.errors).toHaveLength(0);

    const expected =
      '<[/#tag_header/ number]>[/#tag_list/ /*comm-data-v1*/ #tag1 1,/*comm-data-v2*/ /*comm-data-v3*/ /*comm-data-v3*/ #tag2 #tag3 #tag4 2]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should warn on meta schema with implicit values', () => {
    /**
     * Tests handling of malformed meta blocks.
     * In the input: / listAttr="GlobalList" / is missing '$' prefix for attribute.
     */
    const akdText = `
        < 
          / listAttr="GlobalList" /
          [ 
            /* Missing $ prefix */
            / $elemAttr="InnerRecord" /* fixed input */ /
            /* comments2 */ id: int
          ] 
        >
        [ (1) ]
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;
    const warnings = results.warnings;

    // If the input was fixed above, errors should be 0.
    // Because we have: listAttr="GlobalList" (implicit), it should be a warning.
    expect(warnings.length).toBeGreaterThan(0);
    expect(warnings[0].message).toContain("Implicit attribute 'listAttr'");

    // 1. Check List Meta (Outer)
    expect(node.isList).toBe(true);
    expect(node.schema.attr['listAttr']).toBe('GlobalList');

    // 2. Check Element Meta (Inner Record)
    const elemSchema = node.schema.element!;
    expect(elemSchema.kind).toBe(SchemaKind.RECORD);
    expect(node.schema.attr['elemAttr']).toBe('InnerRecord');

    const expected =
      '<[//*fixed input*/ $listAttr="GlobalList" $elemAttr="InnerRecord"/ /*Missing $ prefix*/ /*comments2*/ id:number]>[(1)]';
    assertRoundtrip(akdText, expected, false);
  });

  it('should handle meta schema field modifiers', () => {
    /**
     * Tests field modifiers inside a record definition: !required, $key=value.
     */
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;
    expect(results.errors).toHaveLength(0);

    expect(node.isRecord).toBe(true);

    // Retrieve field definitions from schema
    const fields = node.schema.fields;

    // Field 'id'
    const fId = fields.find((f) => f.name === 'id')!;
    expect(fId).toBeDefined();
    expect(fId.required).toBe(true);
    expect(fId.attr['key']).toBe(101);

    // Field 'name'
    const fName = fields.find((f) => f.name === 'name')!;
    expect(fName).toBeDefined();
    expect(fName.required).toBe(false); // Default
    expect(fName.attr['desc']).toBe('User Name');

    // Check Instance Data Meta (the node itself, not the schema)
    // The record instance has / $id=3 /
    expect(node.attr['id']).toBe(3);

    const expected =
      '<//*comm2 /* comm2.5*/*/ $id=0/ /*comm0*/ /*comm3*/ /*Modifiers block before field name*/ !required $key=101 id:number,$desc="User Name" name:string>(//*comment2*/ $id=3/ /*comment0*/ /*comment3*/ 1,/*comment4*/ $id=65 #alice "Alice")';
    assertRoundtrip(akdText, expected, false);
  });

  // ==============================================================================
  // 2. DATA BLOCK META (Metadata inside data blocks [ ... ])
  // ==============================================================================

  it('should handle meta data block list primitive', () => {
    /**
     * Tests metadata inside a data block for a simple list.
     * Syntax: [ / @size=3 / 1, 2, 3 ]
     */
    const akdText = '[ / $size=3 $author="me" / 1, 2, 3 ]';

    const results = decode(akdText, { debug: false });
    const node = results.node;
    expect(results.errors).toHaveLength(0);

    expect(node.isList).toBe(true);
    // Meta should go to this specific node's attributes
    expect(node.attr['size']).toBe(3);
    expect(node.attr['author']).toBe('me');

    // Check content
    expect(node.elements).toHaveLength(3);
    expect(node.elements[0].value).toBe(1);

    const expected = '<[number]>[/$size=3 $author="me"/ 1,2,3]';
    assertRoundtrip(akdText, expected, false);
  });

  // ==============================================================================
  // 3. NESTED META (Lists within lists)
  // ==============================================================================

  it('should handle meta nested lists', () => {
    /**
     * Tests metadata assignment in nested lists.
     */
    const akdText = `
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
        `;

    const results = decode(akdText, { debug: false });
    const node = results.node;
    expect(results.errors).toHaveLength(0);

    // Root Node
    expect(node.isList).toBe(true);
    expect(node.attr['level']).toBe(0);

    // Inner Node 1
    const inner1 = node.elements[0];
    expect(inner1.isList).toBe(true);
    expect(inner1.attr['level']).toBe(1);

    // Inner Node 2
    const inner2 = node.elements[1];
    expect(inner2.isList).toBe(true);
    expect(inner2.attr['level']).toBe(2);

    const expected = '<[[number]]>[/$level=0/ [/$level=1/ 1,2],[/$level=2/ 3,4]]';
    assertRoundtrip(akdText, expected, false);
  });

  // ==============================================================================
  // 4. EDGE CASES & OVERRIDES
  // ==============================================================================

  it('should handle meta mixed with type override', () => {
    /**
     * Tests a scenario where we have metadata for the list AND a type override for an element.
     */
    const akdText = '[ / $info="mixed" / 1, 2, <string> "3" ]';
    const expected = '<[number]>[/$info="mixed"/ 1,2,<string> "3"]';

    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    // List Meta
    expect(node.attr['info']).toBe('mixed');

    // List Type Inference (Should be Number based on first element '1')
    expect(node.schema.element?.typeName).toBe('number');

    // Element Override
    const elLast = node.elements[2];
    expect(elLast.schema.typeName).toBe('string');
    expect(elLast.value).toBe('3');

    assertRoundtrip(node, expected, false);
  });

  it('should handle meta and explicit type in data', () => {
    /**
     * Tests a scenario where an explicit type is provided inside the / ... / block.
     * The parser must understand that type is the list type, and @tag is metadata.
     */
    const akdText = '[ / $tag=1 / 1, 2 ]';

    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    expect(node.isList).toBe(true);
    // Inferred type
    expect(node.schema.element?.typeName).toBe('number');
    expect(Object.keys(node.attr)).toHaveLength(1);

    const expected = '<[number]>[/$tag=1/ 1,2]';
    assertRoundtrip(node, expected, false);
  });
});
