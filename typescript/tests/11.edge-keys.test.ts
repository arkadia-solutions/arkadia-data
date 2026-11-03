import { describe, expect, it } from 'vitest';

import { dumps, loads } from '../src/index';

const CASES: unknown[] = [
  { '`q`': 1 },
  [{ '`q`': 1 }, { '`q`': 2 }],
  { '': [], '0': null },
  [{ '': [], '0': null }, { '': 1 }, { '': 2 }],
  { '': 1, '0': 2 },
  { 'a\n': 1, 'x y': [{ '`': true }] },
  [],
  { rows: [] },
];

describe('keys a header cannot spell', () => {
  it.each(CASES.map((c) => [JSON.stringify(c), c]))('%s round-trips', (_, data) => {
    expect(loads(dumps(data))).toEqual(data);
    expect(loads(dumps(data, { indent: 2 }))).toEqual(data);
  });

  it('writes backtick keys by name and headers like Python', () => {
    expect(dumps({ '`q`': 1 })).toBe('{"`q`":1}');
    expect(dumps({ id: 1, name: 'x' }, { indent: 2 })).toBe('< id:number, name:string >\n(1, "x")');
  });
});
