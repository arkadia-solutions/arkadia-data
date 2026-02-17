import { describe, it, expect } from 'vitest';
import { encode, decode, parse, SchemaKind } from '../src/index';
import { assertRoundtrip } from './utils';

describe('AK List Handling', () => {
  it('should decode list of primitives', () => {
    /**
     * Validates simple lists.
     */
    const text = '[1, 2, 3]';
    const expected = '<[number]>[1,2,3]';

    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    const node = res.node;
    // Check elements (Node logic stores simple lists in elements)
    const values = node.elements.map((el) => el.value);
    expect(values).toEqual([1, 2, 3]);

    assertRoundtrip(node, expected, false);
  });

  it('should infer mixed list type from first element', () => {
    /**
     * Tests if the list type is inferred based on the first element ("a" -> string).
     * As a result, the number 3 (int) should be treated as a mismatch and marked with the <number> tag.
     */
    // 1. Input data: List starts with strings but has an int at the end
    const data = { tests: ['a', 'b', 'c', 3] };

    // 2. Encoding (inference happens here in Parser.ts)
    const node = parse(data);

    expect(node.schema).not.toBeNull();
    expect(node.schema.isRecord).toBe(true);
    expect(node.fields).toHaveProperty('tests');

    const testsNode = node.fields['tests'];
    expect(testsNode.isList).toBe(true);
    expect(testsNode.schema).not.toBeNull();
    expect(testsNode.schema.element).not.toBeNull();

    expect(testsNode.schema.element?.kind).toBe(SchemaKind.PRIMITIVE);
    expect(testsNode.schema.element?.typeName).toBe('string'); // Inferred from first element "a"

    expect(testsNode.elements).toHaveLength(4);

    const output = encode(data, { compact: true, colorize: false });

    // We expect the list NOT to be [any], but [string] (implied or explicit),
    // so strings will be "clean", and the number will get a tag.

    // Check if 'a' is treated normally (as a string in a string list)
    expect(output).toContain('"a"');

    // KEY: Check if 3 got a tag because it doesn't match the inferred String type
    // TS Encoder outputs <number>
    expect(output).toContain('<number> 3');

    // Ensure there is NO tag next to strings (because they match the list type)
    expect(output).not.toContain('<string> "a"');

    const expected = '<tests:[string]>(["a","b","c",<number> 3])';
    assertRoundtrip(node, expected, false);
  });

  it('should generate tags for explicit any list due to primitive mismatch', () => {
    /**
     * Tests the scenario where a list is defined as [any].
     * * Behavior:
     * 1. 'any' is parsed as a PRIMITIVE type named "any".
     * 2. The Decoder updates the schema based on the first element found ("a" -> string).
     * 3. Because "string" != "number" (for value 3), the Encoder sees a mismatch and adds explicit tags.
     */

    // 1. Input in AKD format
    const akdText = `
        <tests: [any]>
        (
            ["a", "b", "c", 3]
        )
        `;

    // 2. Decode
    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    // 3. Verify Internal State
    const testsNode = node.fields['tests'];

    // Verify the list definition
    const elementSchema = testsNode.schema.element;
    expect(elementSchema?.kind).toBe(SchemaKind.PRIMITIVE);

    // Decoder logic updates "any" element schema based on the first item found
    expect(elementSchema?.typeName).toBe('string');

    // Verify the actual elements
    expect(testsNode.elements[0].schema.typeName).toBe('string');
    expect(testsNode.elements[3].schema.typeName).toBe('number');

    // 4. Encode
    const expected = '<tests:[string]>(["a","b","c",<number> 3])';
    assertRoundtrip(node, expected, false);
  });

  it('should handle inference happy path', () => {
    /**
     * Theory: If a list has no type (or [any]), the first element ("a")
     * should refine the list schema to [string].
     */
    const dataStr = '["a", "b"]'; // No header = SchemaKind.ANY

    const result = decode(dataStr, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    expect(node.isList).toBe(true);
    expect(node.schema.element?.typeName).toBe('string'); // Inferred!

    const expected = '<[string]>["a","b"]';
    assertRoundtrip(node, expected, false);
  });

  it('should handle inference mismatch (string vs number)', () => {
    /**
     * Theory: First element "a" sets list to [string].
     * The number 3 is mismatch and gets tagged.
     */
    const dataStr = '["a", 3]';

    const result = decode(dataStr, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    // The list should have become [string] due to "a"
    expect(node.schema.element?.typeName).toBe('string');

    const expected = '<[string]>["a",<number> 3]';
    assertRoundtrip(node, expected, false);
  });

  it('should handle inference mismatch (number vs string)', () => {
    /**
     * Theory: First element 3 sets list to [number].
     * The string "a" is mismatch and gets tagged.
     */
    const dataStr = '[3, "a"]';

    const result = decode(dataStr, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    // The list should have become [number] due to 3
    expect(node.schema.element?.typeName).toBe('number');

    const expected = '<[number]>[3,<string> "a"]';
    assertRoundtrip(node, expected, false);
  });

  it('should fix schema crash on override logic', () => {
    /**
     * Theory: We expect a String, but we get a List.
     * This triggers 'needs_override' logic in the Encoder.
     */
    // Header says 'test' is a string, but body has a list
    const akdText = `
        <test: string>
        (
            ["a", "b"]
        )
        `;

    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    // The Encoder sees a List Node vs String Schema -> Mismatch -> Adds Tag
    const expected = '<test:string>(<[string]> ["a","b"])';
    assertRoundtrip(node, expected, false);
  });

  it('should handle primitive list with implicit output', () => {
    const akdText = `
         <ab>
        {
            ab:  ["a", "b", "c", 3]
        }
        `;

    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    const expected = '<ab:[string]>(["a","b","c",<number> 3])';
    assertRoundtrip(node, expected, false);
  });

  it('should handle simple mixed types', () => {
    const akdText = '["a", "b", "c", 3]';

    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    const expected = '<[string]>["a","b","c",<number> 3]';
    assertRoundtrip(node, expected, false);
  });

  it('should handle inner list types', () => {
    // <[[int]]>[[2,3,4],[5,6,7]]
    const akdText = '<[[int]]>[[2,3,4],[5,6,7]]';

    const result = decode(akdText, { debug: false });
    const node = result.node;
    expect(result.errors).toHaveLength(0);

    // 'int' normalizes to 'number' in the TS implementation
    const expected = '<[[number]]>[[2,3,4],[5,6,7]]';
    assertRoundtrip(node, expected, false);
  });
});
