/**
 * Lossless round-trip: JSON -> AK-Data -> JSON must return the same value.
 * Mirrors python/tests/test_08_roundtrip.py.
 */
import { describe, expect, test } from 'vitest';
import { decode, encode } from '../src/index';

const CONFIGS = [{ compact: true }, { compact: false }, { compact: true, escapeNewLines: true }];

const CASES: unknown[] = [
  { items: [{ a: 1 }, [1, 2]] },
  { t: [{ i: { tags: ['a'] } }, { i: { nums: [1] } }] },
  { t: [{ i: { pairs: [['a']] } }, { i: ['x', 1] }] },
  { i: {} },
  [{}, { a: 1 }],
  {},
  [],
  [[{ a: 1 }, { a: 2 }], [{ a: 3 }]],
  [[], [null, 1]],
  [[], [{ a: 1 }, { a: 2 }]],
  { items: [{ a: 1, b: 2 }, { a: 3 }] },
  { items: [{ a: 1 }, { a: 'x' }, { a: null }, { a: [1] }] },
  [1, 'a', true, null, 2.5, { k: 'v' }, [1]],
  { 'x y': { ł: 'ząb', 'v-1': '(x)' } },
  { s: ['q"t', 'a,b', 'new\nline', '<any>', '{', 'null', 'true', '12'] },
  {
    pairs: [
      ['a', 'b'],
      ['c', 'd'],
    ],
    deep: [[[{ id: 1 }]]],
  },
  { '': 1 },
  { a: { '': 1 }, t: [{ '': 1 }, { '': 2 }] },
];

const KEYS = ['a', 'b', 'c', 'id', 'name', 'x y', 'ł', 'tags', 'v-1'];
const PRIMS = [
  null,
  true,
  false,
  0,
  1,
  -3,
  2.5,
  '',
  's',
  'a,b',
  '(x)',
  'new\nline',
  'q"t',
  '<any>',
  '{',
  'null',
  'true',
  '12',
  'ząb',
  ' pad ',
];

function rng(seed: number): () => number {
  let a = seed + 0x6d2b79f5;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gen(r: () => number, depth = 0): unknown {
  const pick = <T>(xs: T[]): T => xs[Math.floor(r() * xs.length)];
  const int = (lo: number, hi: number) => lo + Math.floor(r() * (hi - lo + 1));
  const sample = (n: number) => [...KEYS].sort(() => r() - 0.5).slice(0, n);
  const x = r();
  if (depth > 3 || x < 0.35) return pick(PRIMS);
  if (x < 0.65) return Array.from({ length: int(0, 4) }, () => gen(r, depth + 1));
  if (x < 0.8) {
    const keys = sample(int(1, 3));
    return Array.from({ length: int(1, 4) }, () =>
      Object.fromEntries((r() < 0.8 ? keys : sample(2)).map((k) => [k, gen(r, depth + 2)])),
    );
  }
  return Object.fromEntries(sample(int(0, 4)).map((k) => [k, gen(r, depth + 1)]));
}

function sortKeys(x: unknown): unknown {
  if (Array.isArray(x)) return x.map(sortKeys);
  if (x && typeof x === 'object') {
    const o = x as Record<string, unknown>;
    return Object.fromEntries(
      Object.keys(o)
        .sort()
        .map((k) => [k, sortKeys(o[k])]),
    );
  }
  return x;
}

function roundtrip(value: unknown, config: object) {
  const text = encode(value, config);
  const result = decode(text);
  expect(result.errors, text).toHaveLength(0);
  expect(JSON.stringify(sortKeys(result.node.dict())), text).toBe(JSON.stringify(sortKeys(value)));
}

describe('lossless round-trip', () => {
  test.each(CASES.map((c, i) => [i, c]))('known case %i', (_i, value) => {
    for (const config of CONFIGS) roundtrip(value, config);
  });

  test.each([0, 1, 2, 3, 4])('random documents, seed %i', (seed) => {
    const r = rng(seed);
    for (let i = 0; i < 300; i++) {
      const value = gen(r);
      for (const config of CONFIGS) roundtrip(value, config);
    }
  });
});
