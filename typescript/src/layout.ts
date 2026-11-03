/**
 * Readable layout of AK-DATA text (the same algorithm as the Rust crate's
 * `layout::pretty`): a group that fits the line width stays on one line, a
 * longer one is broken — records and lists of values fill lines, headers and
 * lists of records get one item per line. Whitespace is not significant in
 * AK-DATA, so the result decodes to the same value.
 *
 *   pretty('<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])', 40)
 *   // <users:<[id:number, name:string]>>
 *   // ([(1, "Ada"), (2, "Alan")])
 */

type LNode =
  | { kind: 'atom'; text: string; space: boolean }
  | { kind: 'group'; open: string; close: string; items: LNode[][]; space: boolean };

const CLOSE: Record<string, string> = { '<': '>', '(': ')', '[': ']', '{': '}' };

function isHeader(n: LNode): boolean {
  return n.kind === 'group' && n.open === '<';
}
function isMeta(n: LNode): boolean {
  return (
    n.kind === 'atom' &&
    (n.text.startsWith('/*') ||
      n.text.startsWith('//') ||
      n.text.startsWith('$') ||
      n.text.startsWith('#'))
  );
}

class Parser {
  i = 0;
  constructor(private readonly s: string) {}

  private quoted(q: string): string {
    let out = q;
    this.i++;
    while (this.i < this.s.length) {
      const c = this.s[this.i++];
      out += c;
      if (c === '\\' && q === '"' && this.i < this.s.length) {
        out += this.s[this.i++];
        continue;
      }
      if (c === q) break;
    }
    return out;
  }

  comment(): string {
    const s = this.s;
    let out = '';
    if (s[this.i + 1] === '*') {
      let depth = 0;
      while (this.i < s.length) {
        if (s[this.i] === '/' && s[this.i + 1] === '*') {
          depth++;
          out += '/*';
          this.i += 2;
          continue;
        }
        if (s[this.i] === '*' && s[this.i + 1] === '/') {
          depth--;
          out += '*/';
          this.i += 2;
          if (depth === 0) break;
          continue;
        }
        out += s[this.i++];
      }
      return out;
    }
    out = '//';
    this.i += 2;
    while (this.i < s.length) {
      if (s[this.i] === '/' && s[this.i + 1] === '/') {
        out += '//';
        this.i += 2;
        break;
      }
      if (s[this.i] === '"') {
        out += this.quoted('"');
        continue;
      }
      const c = s[this.i++];
      out += /\s/.test(c) ? ' ' : c;
    }
    return out;
  }

  items(close: string | null): LNode[][] {
    const s = this.s;
    const items: LNode[][] = [[]];
    let space = false;
    while (this.i < s.length) {
      const c = s[this.i];
      if (/\s/.test(c)) {
        space = true;
        this.i++;
        continue;
      }
      if (c === close) {
        this.i++;
        break;
      }
      let node: LNode;
      if (c === ',') {
        this.i++;
        items.push([]);
        space = false;
        continue;
      } else if (c in CLOSE) {
        this.i++;
        node = { kind: 'group', open: c, close: CLOSE[c], items: this.items(CLOSE[c]), space };
      } else if ('>)]}'.includes(c)) {
        this.i++;
        node = { kind: 'atom', text: c, space };
      } else if (c === '/' && (s[this.i + 1] === '*' || s[this.i + 1] === '/')) {
        node = { kind: 'atom', text: this.comment(), space };
      } else {
        let text = '';
        while (this.i < s.length) {
          const ch = s[this.i];
          if (/\s/.test(ch) || '<>()[]{},'.includes(ch)) break;
          if (ch === '/' && (s[this.i + 1] === '*' || s[this.i + 1] === '/')) break;
          if (ch === '"' || ch === '`') {
            text += this.quoted(ch);
            continue;
          }
          text += ch;
          this.i++;
        }
        node = { kind: 'atom', text, space };
      }
      space = false;
      items[items.length - 1].push(node);
    }
    if (items.length === 1 && items[0].length === 0) items.length = 0;
    else if (items.length && items[items.length - 1].length === 0) items.pop();
    return items;
  }
}

function gap(prev: LNode, next: LNode): boolean {
  return isHeader(prev) || next.space || isMeta(prev) || isMeta(next);
}

class Writer {
  out = '';
  col = 0;
  header = 0;
  constructor(
    readonly width: number,
    readonly tight: boolean,
  ) {}

  flatSeq(seq: LNode[]): string {
    let out = '';
    seq.forEach((n, i) => {
      if (i > 0) {
        const p = seq[i - 1];
        const space = this.tight ? isMeta(p) || isMeta(n) || isHeader(p) : gap(p, n);
        if (space) out += ' ';
      }
      out += this.flat(n);
    });
    return out;
  }

  flat(n: LNode): string {
    if (n.kind === 'atom') return n.text;
    return n.open + n.items.map((it) => this.flatSeq(it)).join(this.tight ? ',' : ', ') + n.close;
  }

  push(t: string) {
    const nl = t.lastIndexOf('\n');
    this.col = nl >= 0 ? [...t.slice(nl + 1)].length : this.col + [...t].length;
    this.out += t;
  }
  newline(indent: number) {
    this.out += `\n${' '.repeat(indent)}`;
    this.col = indent;
  }
  fits(t: string, extra: number) {
    return this.col + [...t].length + extra <= this.width;
  }

  seq(seq: LNode[], indent: number, extra: number) {
    const whole = this.flatSeq(seq);
    if (this.fits(whole, extra)) {
      this.push(whole);
      return;
    }
    seq.forEach((n, i) => {
      if (i > 0 && gap(seq[i - 1], n)) this.push(' ');
      this.node(n, indent, i + 1 === seq.length ? extra : 0);
    });
  }

  node(n: LNode, indent: number, extra: number) {
    const text = this.flat(n);
    if (this.fits(text, extra) || n.kind === 'atom') {
      this.push(text);
      return;
    }
    const h = n.open === '<' ? 1 : 0;
    this.header += h;
    this.group(n.open, n.close, n.items, indent, extra);
    this.header -= h;
  }

  group(open: string, close: string, items: LNode[][], indent: number, extra: number) {
    if (items.length === 1) {
      this.push(open);
      this.seq(items[0], indent, extra + 1);
      this.push(close);
      return;
    }
    const valuesOnly = items.every((it) => it.every((n) => n.kind === 'atom'));
    const col0 = this.col + 1;
    const eachFits = items.every((it) => col0 + [...this.flatSeq(it)].length < this.width);
    const fill =
      this.header === 0 &&
      eachFits &&
      (open === '(' || open === '{' || (open === '[' && valuesOnly));
    this.push(open);
    if (fill) {
      items.forEach((item, i) => {
        const last = i + 1 === items.length;
        const tail = last ? extra + 1 : 1;
        if (i > 0) {
          if (this.fits(` ${this.flatSeq(item)}`, tail)) this.push(' ');
          else this.newline(col0);
        }
        this.seq(item, col0, tail);
        if (!last) this.push(',');
      });
      this.push(close);
      return;
    }
    items.forEach((full, i) => {
      this.newline(indent + 2);
      const last = i + 1 === items.length;
      // Comments in front of an item get their own line.
      let lead = 0;
      while (lead < full.length) {
        const n = full[lead];
        if (n.kind !== 'atom' || !n.text.startsWith('/*')) break;
        lead++;
      }
      let item = full;
      if (lead > 0 && lead < full.length) {
        for (const n of full.slice(0, lead)) {
          this.push(this.flat(n));
          this.newline(indent + 2);
        }
        item = full.slice(lead);
      }
      this.seq(item, indent + 2, last ? 0 : 1);
      if (!last) this.push(',');
    });
    this.newline(indent);
    this.push(close);
  }
}

function strip(nodes: LNode[], comments: boolean, attributes: boolean): LNode[] {
  const out: LNode[] = [];
  for (const n of nodes) {
    if (isMeta(n)) {
      const keep = n.kind === 'atom' && n.text.startsWith('/*') ? comments : attributes;
      if (!keep) continue;
    }
    if (n.kind === 'group') {
      const items = n.items
        .map((it) => strip(it, comments, attributes))
        .filter((it) => it.length > 0);
      out.push({ ...n, items });
    } else out.push(n);
  }
  return out;
}

/**
 * Compact text keeping only the chosen metadata: `comments` keeps comments,
 * `attributes` keeps $attributes, #tags and // … // blocks.
 */
export function stripMeta(text: string, comments = false, attributes = false): string {
  return render(
    strip(new Parser(text).items(null).flat(), comments, attributes),
    Number.MAX_SAFE_INTEGER / 4,
    false,
    true,
  );
}

function layout(text: string, width: number, lines: boolean, tight: boolean): string {
  return render(new Parser(text).items(null).flat(), width, lines, tight);
}

function render(nodes: LNode[], width: number, lines: boolean, tight: boolean): string {
  const w = new Writer(Math.max(width, 20), tight);
  nodes.forEach((n, i) => {
    if (i > 0) {
      const prev = nodes[i - 1];
      const typeName = prev.kind === 'atom' && prev.text.startsWith('@');
      const ownLine = isHeader(prev) || isMeta(prev) || (isHeader(n) && !typeName);
      if (ownLine && lines) w.newline(0);
      else if (tight ? isMeta(prev) || isMeta(n) : gap(prev, n)) w.push(' ');
    }
    w.node(n, 0, 0);
  });
  return w.out;
}

/** AK-DATA laid out to `width` columns (default 80); decodes to the same value. */
export function pretty(text: string, width = 80): string {
  return layout(text, width, true, false);
}

/** The same AK-DATA on one line without optional spaces (metadata kept). */
export function compact(text: string): string {
  return layout(text, Number.MAX_SAFE_INTEGER / 4, false, true);
}
