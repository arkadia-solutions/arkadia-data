import { describe, expect, it } from 'vitest';
import { diff as d, loads } from '../src/index';
import fixtures from './fixtures/diff.json';

describe('diff / merge / apply — the same results as Rust and Python', () => {
  for (const c of fixtures.cases) {
    it(c.name, () => {
      const changes = d.diff(c.a, c.b);
      expect(d.changesJson(changes)).toEqual(c.changes);
      expect(d.merge(c.a, c.b)).toEqual(c.merged);
      expect(d.apply(c.a, changes)).toEqual(c.b);
      expect(d.apply(c.b, d.reverse(changes))).toEqual(c.a);
      const set = d.changeSet(
        changes,
        { title: 't', author: 'Ada', date: '2026-11-01T10:00:00Z' },
        '0123456789',
      );
      expect(set.id).toBe(c.id);
      expect(d.withHistory(c.b, [set])).toBe(c.document);
      expect(loads(c.document)).toEqual(c.b);
      expect(d.history(c.document)).toEqual([set]);
    });
  }
});

describe('apply, paths, commit', () => {
  it('reports conflicts', () => {
    const changes = d.diff({ a: 1 }, { a: 2 });
    expect(() => d.apply({ a: 5 }, changes)).toThrow(/expected 1, found 5/);
    expect(d.apply({ a: 5 }, changes, { force: true })).toEqual({ a: 2 });
  });

  it('parses paths', () => {
    expect(d.parsePath('users[id=2].tags[1]["a b"][name="x]"]')).toEqual([
      { kind: 'key', key: 'users' },
      { kind: 'match', key: 'id', value: 2 },
      { kind: 'key', key: 'tags' },
      { kind: 'index', index: 1 },
      { kind: 'key', key: 'a b' },
      { kind: 'match', key: 'name', value: 'x]' },
    ]);
    expect(d.parsePath('$')).toEqual([]);
    expect(() => d.parsePath('a..b')).toThrow();
  });

  it('records the history without changing the data', () => {
    let text = d.commit(
      '{"n": 1}',
      { n: 2 },
      { title: 'Bump', author: 'Ada', date: '2026-11-01T10:00:00Z' },
    );
    text = d.commit(text, { n: 3 }, { title: 'Bump again', date: '2026-11-01T11:00:00Z' });
    expect(loads(text)).toEqual({ n: 3 });
    expect(d.history(text).map((s) => s.title)).toEqual(['Bump', 'Bump again']);
    expect(d.commit(text, { n: 3 })).toBe(text);
  });

  it('round-trips random edits', () => {
    let seed = 7;
    const r = (n: number): number => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed % n;
    };
    const gen = (depth: number): unknown => {
      switch (r(depth > 2 ? 4 : 7)) {
        case 0:
          return r(5);
        case 1:
          return 'abc'[r(3)];
        case 2:
          return r(2) === 0;
        case 3:
          return null;
        case 4:
          return Array.from({ length: r(4) }, () => gen(depth + 1));
        case 5: {
          const ids = [0, 1, 2, 3, 4, 5];
          return Array.from({ length: r(5) }, () => ({
            id: ids.splice(r(ids.length), 1)[0],
            v: gen(depth + 1),
          }));
        }
        default: {
          const o: Record<string, unknown> = {};
          for (let i = r(4); i > 0; i--) o[['x', 'y', 'z', 'w w'][r(4)]] = gen(depth + 1);
          return o;
        }
      }
    };
    for (let i = 0; i < 2000; i++) {
      const a = gen(0);
      const b = gen(0);
      const changes = d.diff(a, b);
      expect(d.apply(a, changes)).toEqual(b);
      expect(d.apply(b, d.reverse(changes))).toEqual(a);
    }
  });
});
