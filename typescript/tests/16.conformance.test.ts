import { describe, expect, it } from 'vitest';
import { decode, encode } from '../src/index';
import corpus from './fixtures/conformance.json';

describe('shared 0.2 semantic corpus', () => {
  for (const [i, data] of corpus.cases.entries()) {
    it(`case ${i}`, () => {
      for (const compact of [true, false]) {
        const out = decode(encode(data, { compact }));
        expect(out.errors).toEqual([]);
        expect(out.node.dict()).toEqual(data);
      }
    });
  }
});
