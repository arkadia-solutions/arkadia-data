import { describe, it, expect } from 'vitest';
import { decode } from '../src/index';
import { assertRoundtrip } from './utils';

describe('AI Data Record Handling', () => {

    // ==============================================================================
    // 1. SCHEMA DEFINITION META (Types defined in < ... >)
    // ==============================================================================

    it('should handle different type in record', () => {
        const aidText = `
        < 
          id: number
        >
        ( ["text"] )
        `;

        const result = decode(aidText, { debug: false });
        const node = result.node;
        expect(result.errors).toHaveLength(0);
        
        // 1. Check Record Meta (Outer)
        expect(node.isRecord).toBe(true);

        const expected = '<id:number>(<[string]> ["text"])';
        assertRoundtrip(node, expected, false);
    });

    it('should handle simple types', () => {
        // Input is a raw AID format string representing a dictionary
        const aidText = '{ a:"a", b:"b", c:"c", d: 3 }';
        
        // The parser infers the schema from the keys/values.
        // The encoder then outputs the inferred schema and converts the named record 
        // to a positional one because a schema exists.
        const expected = '<a:string,b:string,c:string,d:number>("a","b","c",3)';
        
        assertRoundtrip(aidText, expected, false);   
    });

    it('should handle record named type mismatch', () => {
        /**
         * Tests a scenario where a record field has a defined type (e.g., string),
         * but the actual value inside is of a different type (e.g., int).
         *
         * This ensures that the encodeRecord method uses applyTypeTag correctly.
         *
         * Schema: <tests: string>
         * Data: { tests: 3 }
         * Expected Output: ... (<number> 3)
         */
        const aidText = `
        <tests: string>
        {
         tests: 3
        }
        `;

        const expected = '<tests:string>(<number> 3)';
        assertRoundtrip(aidText, expected, false);   
    });

    it('should handle record positional type mismatch', () => {
        /**
         * Tests a scenario where a positional record field has a defined type (e.g., string),
         * but the actual value inside is of a different type (e.g., int).
         *
         * Schema: <tests: string>
         * Data: (3)
         * Expected Output: ... (<number> 3)
         */
        const aidText = `
        <tests: string>
        (3)
        `;

        const expected = '<tests:string>(<number> 3)';
        assertRoundtrip(aidText, expected, false);   
    });

});