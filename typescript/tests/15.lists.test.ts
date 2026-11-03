// Lists of records with optional fields and list sizes ($size=N metadata).
// Same cases as python/tests/test_20_lists.py and rust/tests/api.rs.
import { describe, expect, it } from 'vitest';
import { dumps, loads } from '../src/index';

const CASES: [unknown, string][] = [
  [
    {
      items: [
        { a: 1, b: 2, c: 3 },
        { a: 1, b: 2 },
        { a: 4, b: 5, c: 6, d: 7 },
      ],
    },
    '<items:<[a:number,b:number,c:number,d:number]>>([(1,2,3),(1,2),(4,5,6,7)])',
  ],
  [
    {
      cust: [
        { id: 7, name: 'Ada', email: 'a@x' },
        { id: 8, name: 'B' },
        { id: 9, name: 'C', email: null },
      ],
    },
    '<cust:<[id:number,name:string,email:string]>>([(7,"Ada","a@x"),(8,"B"),(9,"C",null)])',
  ],
  [
    [{ name: 'planner', steps: 12 }, { name: 'writer', temp: 0.4 }, { name: 'reviewer' }],
    '<[name:string,steps:number,temp:number]>[("planner",12),<any> {name:"writer",temp:0.4},("reviewer")]',
  ],
  [{ a: [{ x: 1 }, { y: 2 }] }, '<a:[any]>([{x:1},{y:2}])'],
];

const SIZES: [unknown, number, string][] = [
  [
    {
      t: [1, 2, 3],
      u: [1],
      rows: [
        { id: 1, tags: ['a', 'b'] },
        { id: 2, tags: [] },
      ],
    },
    2,
    '<t:[number],u:[number],rows:<[id:number,tags:[string]]>>([//$size=3// 1,2,3],[1],[//$size=2// (1,[//$size=2// "a","b"]),(2,[])])',
  ],
  [[{ id: 1, n: 'x' }, { id: 2 }], 1, '<[id:number,n:string]>[//$size=2// (1,"x"),(2)]'],
];

describe('lists', () => {
  it('records with optional fields share one header', () => {
    for (const [data, expected] of CASES) {
      const text = dumps(data);
      expect(text).toBe(expected);
      expect(loads(text)).toEqual(data);
    }
  });

  it('writes list sizes', () => {
    for (const [data, min, expected] of SIZES) {
      const text = dumps(data, { sizes: min });
      expect(text).toBe(expected);
      expect(loads(text)).toEqual(data);
      expect(loads(dumps(data, { indent: 2, sizes: min }))).toEqual(data);
    }
  });
});
