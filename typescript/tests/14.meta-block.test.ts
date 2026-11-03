import { describe, expect, it } from 'vitest';

import { decode } from '../src/index';

describe('unclosed // meta block', () => {
  // A digit inside an unclosed // block used to loop forever.
  it.each(['<a:number //>(1)', '<a:// 12 3 //number>(1)', '(1) // 9 //', '//', '<id:string,//'])(
    'terminates: %s',
    (text) => {
      const r = decode(text);
      expect(r.node).toBeDefined();
    },
  );
});
