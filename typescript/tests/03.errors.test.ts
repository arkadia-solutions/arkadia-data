import { describe, it, expect } from 'vitest';
import { encode, decode } from '../src/index';

// ==================================================================================
// 4. ROUND TRIP (Encode -> Decode) with Errors
// ==================================================================================

describe('A Data Error Handling', () => {
  it('should report errors on unstripped ANSI codes', () => {
    /**
     * Validates that the Decoder handles ANSI codes gracefully (by reporting errors)
     * if they are not stripped out before decoding.
     */
    const originalData = [
      { id: 1, active: true },
      { id: 2, active: false },
    ];

    // 1. Encode WITH colors
    // Note: We use camelCase keys for config in TypeScript
    const encodedText = encode(originalData, {
      compact: true,
      includeSchema: true,
      colorize: true,
    });

    // 2. Decode WITHOUT stripping colors (simulate user error)
    // Pass removeAnsiColors: false explicitely
    const res = decode(encodedText, { removeAnsiColors: false, debug: false });

    // 3. Assertions
    expect(res.errors.length).toBeGreaterThan(0); // Decoder should report errors on raw ANSI codes

    // Optional: Verify error content
    const messages = res.errors.map((e) => e.message);
    const hasUnexpectedChar = messages.some((m) => m.includes('Unexpected character'));
    expect(hasUnexpectedChar).toBe(true);
  });

  // ==================================================================================
  // 5. PARSING ERROR SCENARIOS
  // ==================================================================================

  it('should fail on unclosed list', () => {
    /**
     * Ensures parsing fails for malformed lists.
     */
    const text = '[1, 2, 3'; // Missing closing bracket
    const res = decode(text, { debug: false });

    expect(res.errors.length).toBeGreaterThan(0);

    const msg = res.errors[0].message;
    // Check for typical error messages related to missing tokens or EOF
    const isExpectedError = msg.includes('Expected') || msg.includes('got') || msg.includes('EOF');
    expect(isExpectedError).toBe(true);
  });

  it('should fail on unexpected character', () => {
    /**
     * Ensures parsing fails for illegal characters.
     */
    const text = '(1, ?)';
    const res = decode(text, { debug: false });

    expect(res.errors.length).toBeGreaterThan(0);
    expect(res.errors[0].message).toContain('Unexpected character');
  });
});
