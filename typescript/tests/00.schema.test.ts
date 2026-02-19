import { describe, expect, it } from 'vitest';
import { Schema, SchemaKind } from '../src/index';

describe('AI Schema test', () => {
  it('should encode raw object', () => {
    const schema = new Schema(SchemaKind.DICT, {
      name: 'TestSchema',
      comments: ['This is a comment'],
      attr: { foo: 'bar' },
      tags: ['tag1', 'tag2'],
      required: true,
    });
    const expected =
      '<Schema(DICT) name="TestSchema" $required attr=["foo"] tags=[tag1, tag2] comments=1>';
    const expected_val = {
      comments: ['This is a comment'],
      attr: {
        foo: 'bar',
      },
      tags: ['tag1', 'tag2'],
      _fieldsList: [],
      _fieldsMap: {},
      kind: 'DICT',
      typeName: 'any',
      name: 'TestSchema',
      element: null,
      key: null,
      value: null,
      required: true,
    };
    expect(schema).toMatchObject(expected_val);
    expect(schema.toString()).toBe(expected);
  });
});
