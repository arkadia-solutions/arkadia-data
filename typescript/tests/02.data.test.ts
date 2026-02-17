import { describe, it, expect } from 'vitest';
import { encode, decode } from '../src/index';
import { assertRoundtrip } from './utils';

// ==================================================================================
// 3. ENCODING TESTS (JS Object -> String)
// ==================================================================================

describe('AI Data Encoding', () => {

    it('should encode simple dict', () => {
        /**
         * Validates encoding a JS Object to AI.DATA format.
         */
        const data = { x: 10, y: 20 };
        
        const result = encode(data, { compact: true });
        const expected = '<x:number,y:number>(10,20)';
        
        expect(result).toBe(expected);
        
        assertRoundtrip(
            result, 
            expected, 
            false
        );
    });

    it('should encode list of objects', () => {
        /**
         * Validates encoding a list of objects.
         */
        const data = [{ name: "A", val: 1 }, { name: "B", val: 2 }];
        
        const result = encode(data, { compact: true, colorize: false });
        const expected = '<[name:string,val:number]>[("A",1),("B",2)]';
        
        expect(result).toBe(expected);

        assertRoundtrip(
            result, 
            expected,
            false
        );
    });

    it('should handle round trip consistency', () => {
        /**
         * Golden Test: Encode -> Decode -> Compare.
         */
        const originalData = [
            { id: 1, active: true, tags: ["a", "b"] },
            { id: 2, active: false, tags: ["c"] },
        ];
        
        const expected = '<[id:number,active:bool,tags:[string]]>[(1,true,["a","b"]),(2,false,["c"])]';

        // 1. Encode
        // Note: converted snake_case config keys to camelCase for TS
        const encodedText = encode(
            originalData,
            { compact: true, includeSchema: true, colorize: false }
        );

        expect(encodedText).toBe(expected);
        assertRoundtrip(encodedText, expected, false);

        // 2. Decode
        const res = decode(encodedText, { debug: false });
        
        // Optional: inspect schema structure

        expect(res.errors).toHaveLength(0);

        // 3. Convert back to JS object (equivalent to .dict() in Python)
        const decodedData = res.node.dict()

        // 4. Compare
        expect(decodedData).toHaveLength(2);
        expect(decodedData[0].id).toBe(1);
        expect(decodedData[0].active).toBe(true);
        expect(decodedData[0].tags).toEqual(["a", "b"]);
        expect(decodedData[1].active).toBe(false);

        // Deep equality check
        expect(decodedData).toEqual(originalData);
    });

});