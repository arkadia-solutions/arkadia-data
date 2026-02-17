import { describe, it, expect } from 'vitest';
import { Schema, SchemaKind, Node } from '../src/index';

describe('AI Node test', () => {
    it('should encode raw object', () => {
        const schema = new Schema(
            SchemaKind.DICT,
            {
                name: "TestSchema",
                comments: ["This is a comment"],
                attr: { foo: "bar" },
                tags: ["tag1", "tag2"],
                required: true

            });
        const node = new Node(schema, {
            value: 3,
        })

        const expected = '<Node(DICT:any) val=3>';
        const expected_val = {
            "comments": [],
            "attr": {},
            "tags": [],
            "schema": {
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
                "_fieldsList": [],
                "_fieldsMap": {},
                "kind": "DICT",
                "typeName": "any",
                "name": "TestSchema",
                "element": null,
                "key": null,
                "value": null,
                "required": true
            },
            "name": "",
            "value": 3,
            "fields": {},
            "elements": []
        }
        expect(node).toMatchObject(expected_val);
        expect(node.toString()).toBe(expected);
    });
});
