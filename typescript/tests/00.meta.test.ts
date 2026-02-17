import { describe, it, expect } from 'vitest';
import { MetaInfo } from '../src/index';

describe('AI Data Meta', () => {
    it('should Meta be properly formatted', () => {
        const meta = new MetaInfo({

            comments: ["This is a comment"],
            attr: { foo: "bar" },
            tags: ["tag1", "tag2"],
            required: true
        });
        const expected = '<MetaInfo !required #tag1 #tag2 $foo="bar" /* This is a comme.. */>';
        // const expectedJSON
        const expected_val = {
            "comments": [
                "This is a comment"
            ],
            "attr": {
                "foo": "bar"
            },
            "tags": [
                "tag1",
                "tag2"
            ],
            "required": true
        }
        expect(meta).toMatchObject(expected_val);
        expect(meta.toString()).toBe(expected);
    });
});
