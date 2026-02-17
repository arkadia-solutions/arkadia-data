import { describe, it, expect } from 'vitest';
import { decode } from '../src/index';
import { assertRoundtrip } from './utils';

// ==================================================================================
// 2. SCHEMA DEFINITION & TYPING
// ==================================================================================

describe('AK Data Schema Definitions', () => {

    it('should handle schema definition and usage', () => {
        /**
         * Validates that a type defined with @Type<...> is correctly applied
         * to the following value.
         */
        // Define schema first, then use it explicitly
        const fullText = '@User<id:int, name:string> @User(1, "Admin")';
        const res = decode(fullText, { debug: false });

        expect(res.errors).toHaveLength(0);
        
        const node = res.node;
        // Check if schema is linked correctly
        expect(node.schema).not.toBeNull();
        expect(node.schema?.typeName).toBe("User");

        // Since we have a schema, positional arguments should be mapped to fields
        // Check by key (Decoder maps positional to fields if schema exists)
        expect(node.fields["id"].value).toBe(1);
        expect(node.fields["name"].value).toBe("Admin");

        assertRoundtrip(
            node, 
            '@User<id:number,name:string>(1,"Admin")',
            false
        );
    });

    it('should handle nested schema structure', () => {
        /**
         * Validates nested structural types.
         */
        // We define Profile, then User uses it.
        const text = `
        @Profile<level:int>
        @User<id:int, profile: @Profile>
        @User(1, {level: 99})
        `;
        
        const res = decode(text, { debug: false });

        expect(res.errors).toHaveLength(0);
        const node = res.node;

        // id should be 1
        expect(node.fields["id"].value).toBe(1);

        // profile should be a node
        const profileNode = node.fields["profile"];
        expect(profileNode).toBeDefined();
        expect(profileNode.fields["level"].value).toBe(99);

        assertRoundtrip(
            node, 
            "@User<id:number,profile:@Profile<level:number>>(1,(99))",
            false
        );
    });

});