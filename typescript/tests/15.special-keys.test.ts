import { describe, expect, it } from 'vitest';
import { decode, encode } from '../src/index';

describe('untrusted JSON property names', () => {
  const keys = ['__proto__', 'constructor', 'prototype', 'toString', 'hasOwnProperty'];
  for (const key of keys) {
    for (const compact of [true, false]) {
      it(`preserves ${key}, compact=${compact}`, () => {
        const source = JSON.parse(`{"${key}":{"isAdmin":true},"safe":1}`);
        for (const data of [source, { nested: source }, [source, source]]) {
          const out = decode(encode(data, { compact }));
          expect(out.errors).toEqual([]);
          expect(JSON.stringify(out.node.dict())).toBe(JSON.stringify(data));
        }
        expect((Object.prototype as Record<string, unknown>).isAdmin).toBeUndefined();
      });
    }
  }
  it('keeps __proto__ as an own data property in a named record', () => {
    const result = decode('{__proto__:{isAdmin:true},safe:1}');
    expect(result.errors).toEqual([]);
    const data = result.node.dict() as Record<string, unknown>;
    expect(Object.hasOwn(data, '__proto__')).toBe(true);
    expect(Object.getPrototypeOf(data)).toBe(Object.prototype);
    expect(data.safe).toBe(1);
  });
});
