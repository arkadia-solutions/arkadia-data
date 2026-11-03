import { describe, expect, test } from 'vitest';
import { AKDataError, dumps, HINT, loads, loadsAny, toPrompt } from '../src/index';

describe('json-like API', () => {
  const obj = {
    users: [
      { id: 1, name: 'Ada' },
      { id: 2, name: 'Alan' },
    ],
    ok: true,
  };

  test('dumps/loads round-trip', () => {
    const text = dumps(obj);
    expect(text).toBe('<users:<[id:number,name:string]>,ok:bool>([(1,"Ada"),(2,"Alan")],true)');
    expect(loads(text)).toEqual(obj);
    expect(loads(dumps(obj, { indent: 2 }))).toEqual(obj);
    expect(loads(dumps(obj, { types: false }))).toEqual(obj);
  });

  test('errors and model output', () => {
    expect(() => loads('<a:number>(1')).toThrow(AKDataError);
    expect(loadsAny('```json\n{"a": 1}\n```')).toEqual({ a: 1 });
    expect(loadsAny('<a:number>(1)')).toEqual({ a: 1 });
  });

  test('toPrompt', () => {
    const block = toPrompt([{ a: 1 }, { a: 2 }]);
    expect(block.startsWith(HINT)).toBe(true);
    expect(block).toContain('<[a:number]>[(1),(2)]');
  });
});

describe('estimateTokens', () => {
  test('matches the Python heuristic on simple text', async () => {
    const { estimateTokens } = await import('../src/index');
    expect(estimateTokens('hello_world foo_bar 123456 ząb')).toBe(7);
    expect(estimateTokens('{"a": [1, 2, 3]}')).toBeGreaterThan(5);
  });
});
