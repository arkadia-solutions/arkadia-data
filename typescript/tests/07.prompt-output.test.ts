import { describe, expect, it } from 'vitest';
import { decode, encode } from '../src/index';

// ==============================================================================
// 1. PROMPT OUTPUT TESTS (LLM-Friendly Blueprint Mode)
// ==============================================================================

const PROMPT_CONFIG = {
  promptOutput: true,
  compact: false,
  includeSchema: false,
  colorize: false,
  indent: 2,
};

describe('AK Data Prompt Output (LLM Blueprints)', () => {
  it('should transform a record into a key-type-comment blueprint', () => {
    /**
     * Validates that promptOutput=true transforms a record into a
     * key-type-comment blueprint using { } braces instead of ( ) parentheses.
     */
    const akdText = `
    @User <
      id: number /* unique id */,
      name: string /* display name */
    >
    `;

    const result = decode(akdText);
    expect(result.errors).toHaveLength(0);

    const output = encode(result.node, PROMPT_CONFIG).trim();

    const expected = [
      '{',
      '  id: number /* unique id */,',
      '  name: string /* display name */',
      '}',
    ].join('\n');
    expect(output).toBe(expected);
  });

  it('should show a single example element inside a list with a continuation comment', () => {
    /**
     * Validates that promptOutput=true shows only a single example element
     * inside a list with a continuation comment (...).
     */
    const akdText = `
    <[ /* id */ id: number, name: string, val: <id: string, num: number> ]>
    [ (1, "n", ("id", 3)), (2), (3) ]
    `;

    const result = decode(akdText);
    expect(result.errors).toHaveLength(0);

    const output = encode(result.node, PROMPT_CONFIG).trim();

    const expected = [
      '[',
      '  {',
      '    id: number /* id */,',
      '    name: string,',
      '    val: {',
      '      id: string,',
      '      num: number',
      '    }',
      '  },',
      '  ... /* repeat pattern for additional items */',
      ']',
    ].join('\n');

    expect(output).toBe(expected);
  });

  it('should expand nested structures into blueprints in prompt mode', () => {
    /**
     * Verifies that nested structures also expand into blueprints in prompt mode.
     */
    const akdText = `
    <
      name: string,
      meta: < ver: number /* version number */ >
    >
    ("App", (1.0))
    `;

    const result = decode(akdText);
    expect(result.errors).toHaveLength(0);

    const output = encode(result.node, PROMPT_CONFIG).trim();

    const expected = [
      '{',
      '  name: string,',
      '  meta: {',
      '    ver: number /* version number */',
      '  }',
      '}',
    ].join('\n');
    expect(output).toBe(expected);
  });

  it('should preserve escaped identifiers (backticks) in prompt mode', () => {
    /**
     * Ensures that escaped identifiers (backticks) are preserved in prompt mode.
     */
    const akdText = '< `User ID`: number /* system id */ > (123)';

    const result = decode(akdText);
    expect(result.errors).toHaveLength(0);

    const output = encode(result.node, PROMPT_CONFIG).trim();

    const expected = ['{', '  `User ID`: number /* system id */', '}'].join('\n');
    expect(output).toBe(expected);
  });
});
