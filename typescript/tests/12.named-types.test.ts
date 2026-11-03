import { describe, expect, it } from 'vitest';

import { loads } from '../src/index';

describe('named types', () => {
  it('can be reused by sibling fields', () => {
    expect(loads('@Point<x:number,y:number> <start:@Point,end:@Point>((0,0),(3,4))')).toEqual({
      start: { x: 0, y: 0 },
      end: { x: 3, y: 4 },
    });
  });

  it('can be reused in fields and lists', () => {
    expect(loads('@U<id:number> <a:@U,b:[@U],c:@U>((1),[(2),(3)],(4))')).toEqual({
      a: { id: 1 },
      b: [{ id: 2 }, { id: 3 }],
      c: { id: 4 },
    });
  });
});
