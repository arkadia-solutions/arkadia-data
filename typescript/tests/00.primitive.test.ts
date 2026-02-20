import { describe, expect, it } from 'vitest';
import { decode, encode } from '../src/index';
import { assertRoundtrip } from './utils';

// ==================================================================================
// 1. DECODING TESTS (String -> Node)
// ==================================================================================

describe('AK Data Primitives', () => {
  it('should encode raw object', () => {
    const input = { foo: 'bar' };
    const expected = '<foo:string>("bar")';
    assertRoundtrip(input, expected);
  });

  it.each([
    // [Input Text, Expected Value, Expected Encoded Output]
    ['123', 123, '<number>123'],
    ['-50', -50, '<number>-50'],
    ['"hello"', 'hello', '<string>"hello"'],
    ['"hello world"', 'hello world', '<string>"hello world"'],
    ['true', true, '<bool>true'],
    ['false', false, '<bool>false'],
    ['null', null, '<null>null'],
  ])('should decode and encode primitive: %s', (text, expectedVal, expectedEnc) => {
    // 1. DECODE
    // We pass an options object (assuming the latest signature: decode(text, { debug: false }))
    const res = decode(text, { debug: false });

    expect(res.errors, `Parsing failed for input: ${text}`).toHaveLength(0);
    expect(res.node.value).toBe(expectedVal);
    expect(res.node.isPrimitive).toBe(true);

    // 2. ENCODE
    const encodedStr = encode(res.node, { colorize: false, compact: true }).trim();

    expect(encodedStr).toBe(expectedEnc);
  });

  it('should decode floats', () => {
    const cases: [string, number][] = [
      ['12.34', 12.34],
      ['-0.005', -0.005],
      ['0.0', 0.0],
    ];

    cases.forEach(([text, expected]) => {
      const res = decode(text);
      expect(res.errors).toHaveLength(0);
      expect(res.node.value).toBe(expected);
      expect(typeof res.node.value).toBe('number');
    });
  });

  it('should decode named record', () => {
    const text = '{id: 1, name: "Test"}';
    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    const node = res.node;

    expect(node.isRecord).toBe(true);
    expect(node.fields['id'].value).toBe(1);
    expect(node.fields['name'].value).toBe('Test');

    assertRoundtrip(node, '<id:number,name:string>(1,"Test")', false);
  });

  it('should decode positional record', () => {
    const text = '(10, "Alice")';
    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    const node = res.node;

    expect(node.isRecord).toBe(true);

    // Verify if the parser mapped positional fields to _0, _1
    expect(node.fields['_0'].value).toBe(10);
    expect(node.fields['_1'].value).toBe('Alice');

    assertRoundtrip(node, '<_0:number,_1:string>(10,"Alice")', false);
  });

  it('should decode raw string', () => {
    const text = '{color: red, status: active}';
    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    const node = res.node;
    expect(node.fields['color'].value).toBe('red');
    expect(node.fields['status'].value).toBe('active');

    assertRoundtrip(node, '<color:string,status:string>("red","active")', false);
  });
});

describe('String Escaping', () => {
  it('should decode string with escaped quotes', () => {
    // Input: { text: "say \"hello\"" }
    // In-memory value: say "hello"
    // Note: In JS string literals, we need extra backslashes to represent a literal backslash.
    const text = '{ text: "say \\"hello\\"" }';

    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    const node = res.node;
    // Check in-memory value
    expect(node.fields['text'].value).toBe('say "hello"');

    // Roundtrip check:
    // Encoder must add backslashes before quotes: "say \"hello\""
    assertRoundtrip(node, '<text:string>("say \\"hello\\"")', false);
  });

  it('should decode string with escaped backslashes', () => {
    // Input: { path: "C:\\Program Files" }
    // In-memory value: C:\Program Files
    // Note: "C:\\\\Program Files" in JS literal becomes C:\\Program Files in the string
    const text = '{ path: "C:\\\\Program Files" }';

    const res = decode(text, { debug: false });
    expect(res.errors).toHaveLength(0);

    const node = res.node;
    // Check in-memory value (single backslash)
    expect(node.fields['path'].value).toBe('C:\\Program Files');

    // Roundtrip check:
    // Encoder must escape the backslash: "C:\\Program Files"
    assertRoundtrip(node, '<path:string>("C:\\\\Program Files")', false);
  });

  it('should handle deeply nested escaped names and metadata keys', () => {
    /**
     * Validates that backticks work in nested schemas and metadata keys.
     * This tests:
     * 1. Schema name with spaces and symbols: @`User ID+`
     * 2. Metadata keys with symbols: $`attributes*`
     * 3. Field names with spaces and symbols: `ID of the user`
     * 4. Standard identifiers: is_user (no backticks)
     */
    const text = `
/* Use backticks for Schema names and Attributes with spaces */
@\`User ID+\` <
  // $\`attributes*\`="32" //
  \`Is User?\`: bool,
  $\`Attribute Special*\` \`ID of the user\`: string,
  \`is - special?\`: bool,
    is_user: bool
>

{
  // $\`numbers of ids\`=4 //
  $\`attr*\`=52  \`Is User?\`: true,
  \`ID of the user\`: "ID",
    \`is - special?\`: false,
    is_user: false
}`;

    // The expected output follows the AK Data rules:
    // - Metadata wrapped in // ... //
    // - Record data in ( ... )
    // - Booleans and Numbers as literals
    // - Identifiers escaped only if necessary
    const expected =
      `@\`User ID+\`<///*Use backticks for Schema names and Attributes with spaces*/ $\`attributes*\`="32"// \`Is User?\`:bool,$\`Attribute Special*\` \`ID of the user\`:string,\`is - special?\`:bool,is_user:bool>(//$\`numbers of ids\`=4// $\`attr*\`=52 true,"ID",false,false)`.trim();

    assertRoundtrip(text, expected, false);
  });
});
