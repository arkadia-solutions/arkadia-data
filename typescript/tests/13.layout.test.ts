import { describe, expect, it } from 'vitest';

import { compact, dumps, loads, pretty } from '../src/index';

const SAMPLE =
  '<orders:<[id:string,customer:<id:number,name:string>,items:<[sku:string,qty:number]>,total:number]>>([("A1",(7,"Ada"),[("KB-01",2),("MS-02",1)],178.0),("A2",(9,"Alan Turing"),[],0),<any> {id:"A3",note:"no items"}])';

describe('layout', () => {
  it('keeps short text on one line', () => {
    expect(pretty('<[number]>[1,2,3]')).toBe('<[number]>\n[1, 2, 3]');
  });

  it('matches the Rust layout', () => {
    expect(pretty('<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])', 40)).toBe(
      '<users:<[id:number, name:string]>>\n([(1, "Ada"), (2, "Alan")])',
    );
    expect(pretty(SAMPLE, 60).startsWith('<orders:<[\n  id:string,')).toBe(true);
  });

  it('decodes to the same value at every width', () => {
    for (const w of [20, 40, 60, 80, 200]) {
      expect(loads(pretty(SAMPLE, w))).toEqual(loads(SAMPLE));
    }
    expect(loads(compact(pretty(SAMPLE, 30)))).toEqual(loads(SAMPLE));
    const data = { a: 'x, (y) <z>', b: [{ q: '"' }] };
    expect(loads(pretty(dumps(data), 10))).toEqual(data);
  });

  it('keeps comments and named types', () => {
    const t = '/* c */ @U<id:number> <a:@U,b:[@U]>((1),[(2),(3)])';
    expect(pretty(t, 20)).toContain('/* c */');
    expect(loads(pretty(t, 20))).toEqual(loads(t));
  });
});
