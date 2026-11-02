/**
 * Differences between documents, merging, applying changes and the change
 * history kept in a document — the same results as the Rust crate and the
 * Python package (`ak-data diff | merge | apply | history`).
 *
 * A change is `add`, `remove`, `change` or `order` at a path
 * (`users[id=2].name`, `tags[1]`, `config.debug`) with the old and the new
 * value. Lists of records are matched by a key field (`id`, `key`, `name`,
 * `slug`, `sku`, `code`, `uuid` or the first field) when it is present and
 * unique in both lists, otherwise by position.
 *
 * The history is a list of change sets stored as the attribute `$changes`:
 * metadata, so `loads` of the document still gives exactly the data.
 *
 *   import { diff } from '@arkadia/data';
 *   const changes = diff.diff(oldData, newData);
 *   diff.apply(oldData, changes);                       // deep-equals newData
 *   text = diff.commit(text, newData, { title: 'Rename Alan', author: 'Ada' });
 *   diff.history(text);                                 // [{ id, date, … }]
 */

import { DEFAULT_CONFIG } from './config';
import { Decoder } from './core/Decoder';
import { Encoder } from './core/Encoder';
import { parseDataToNode } from './core/Parser';

export type Op = 'add' | 'remove' | 'change' | 'order';

export interface Change {
  op: Op;
  path: string;
  old: unknown;
  new: unknown;
}

export interface ChangeSet {
  id: string;
  date: string;
  author: string | null;
  title: string | null;
  description: string | null;
  changes: Change[];
}

export interface Info {
  title?: string | null;
  author?: string | null;
  description?: string | null;
  /** ISO 8601 (`2026-11-01T17:20:00Z`); now when missing. */
  date?: string | null;
}

export interface Conflict {
  index: number;
  path: string;
  reason: string;
}

export type Step =
  | { kind: 'key'; key: string }
  | { kind: 'index'; index: number }
  | { kind: 'match'; key: string; value: unknown };

export class ConflictError extends Error {
  readonly conflicts: Conflict[];
  constructor(conflicts: Conflict[]) {
    super(
      `${conflicts.length} change(s) do not fit: ${conflicts
        .slice(0, 3)
        .map((c) => `${c.path}: ${c.reason}`)
        .join('; ')}`,
    );
    this.name = 'ConflictError';
    this.conflicts = conflicts;
  }
}

const KEYS = ['id', 'key', 'name', 'slug', 'sku', 'code', 'uuid'];
type Obj = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const isObj = (v: unknown): v is Obj => v !== null && typeof v === 'object' && !Array.isArray(v);
const own = (o: Obj, k: string): boolean =>
  // biome-ignore lint/suspicious/noPrototypeBuiltins: Object.hasOwn is ES2022
  Object.prototype.hasOwnProperty.call(o, k);

/** Deep JSON equality (key order does not matter). */
export function equal(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a)) {
    return Array.isArray(b) && a.length === b.length && a.every((x, i) => equal(x, b[i]));
  }
  if (isObj(a)) {
    if (!isObj(b)) return false;
    const ka = Object.keys(a);
    return ka.length === Object.keys(b).length && ka.every((k) => own(b, k) && equal(a[k], b[k]));
  }
  return false;
}

const contains = (list: unknown[], x: unknown): boolean => list.some((y) => equal(x, y));
const scalar = (v: unknown): boolean =>
  v === null || typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean';
const isIdent = (s: string): boolean => /^[A-Za-z_][A-Za-z0-9_]*$/.test(s);
const json = (v: unknown): string => JSON.stringify(v);
const clone = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

function listKey(a: unknown[], b: unknown[]): string | null {
  const items = [...a, ...b];
  if (!items.length || !items.every(isObj)) return null;
  const first = Object.keys(items[0] as Obj)[0];
  const candidates = first === undefined ? KEYS : [...KEYS, first];
  const unique = (list: unknown[], k: string): boolean => {
    const seen: unknown[] = [];
    for (const x of list as Obj[]) {
      if (!own(x, k)) return false;
      const v = x[k];
      if (v === null || !scalar(v) || contains(seen, v)) return false;
      seen.push(v);
    }
    return true;
  };
  return candidates.find((k) => unique(a, k) && unique(b, k)) ?? null;
}

function child(path: string, key: string): string {
  const part = isIdent(key) ? key : `[${json(key)}]`;
  if (path === '$') return part;
  return part.startsWith('[') ? `${path}${part}` : `${path}.${part}`;
}

const item = (path: string, label: string): string => `${path === '$' ? '' : path}[${label}]`;
const keyLabel = (key: string, v: unknown): string =>
  `${isIdent(key) ? key : json(key)}=${json(v)}`;

// ---------------------------------------------------------------------------
// diff / merge
// ---------------------------------------------------------------------------

function walk(a: unknown, b: unknown, path: string, out: Change[]): void {
  if (isObj(a) && isObj(b)) {
    for (const [k, va] of Object.entries(a)) {
      if (own(b, k)) walk(va, b[k], child(path, k), out);
      else out.push({ op: 'remove', path: child(path, k), old: va, new: null });
    }
    for (const [k, vb] of Object.entries(b)) {
      if (!own(a, k)) out.push({ op: 'add', path: child(path, k), old: null, new: vb });
    }
    return;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    const key = listKey(a, b);
    if (key !== null) {
      const ra = a as Obj[];
      const rb = b as Obj[];
      const removed: Change[] = [];
      for (const ia of ra) {
        const p = item(path, keyLabel(key, ia[key]));
        const match = rb.find((ib) => equal(ib[key], ia[key]));
        if (match) walk(ia, match, p, out);
        else removed.push({ op: 'remove', path: p, old: ia, new: null });
      }
      out.push(...removed.reverse());
      for (const ib of rb) {
        if (!ra.some((ia) => equal(ia[key], ib[key]))) {
          out.push({ op: 'add', path: item(path, keyLabel(key, ib[key])), old: null, new: ib });
        }
      }
      const ka = ra.map((x) => x[key]);
      const kb = rb.map((x) => x[key]);
      const naive = (src: unknown[], dst: unknown[]): unknown[] => [
        ...src.filter((k) => contains(dst, k)),
        ...dst.filter((k) => !contains(src, k)),
      ];
      if (!equal(naive(ka, kb), kb) || !equal(naive(kb, ka), ka)) {
        out.push({ op: 'order', path, old: ka, new: kb });
      }
      return;
    }
    const common = Math.min(a.length, b.length);
    for (let i = 0; i < common; i++) walk(a[i], b[i], item(path, String(i)), out);
    for (let i = a.length - 1; i >= common; i--) {
      out.push({ op: 'remove', path: item(path, String(i)), old: a[i], new: null });
    }
    for (let i = common; i < b.length; i++) {
      out.push({ op: 'add', path: item(path, String(i)), old: null, new: b[i] });
    }
    return;
  }
  if (!equal(a, b)) out.push({ op: 'change', path, old: a, new: b });
}

/** The changes that turn `a` into `b` (`apply(a, diff(a, b))` equals `b`). */
export function diff(a: unknown, b: unknown): Change[] {
  const out: Change[] = [];
  walk(a, b, '$', out);
  return out;
}

/**
 * `b` merged into `a`: records field by field (`b` wins, fields only in `a`
 * stay), lists of records by key (new records appended), other lists and
 * values replaced by `b`'s.
 */
export function merge(a: unknown, b: unknown): unknown {
  if (isObj(a) && isObj(b)) {
    const out: Obj = {};
    for (const [k, v] of Object.entries(a)) {
      Object.defineProperty(out, k, {
        value: own(b, k) ? merge(v, b[k]) : v,
        enumerable: true,
        writable: true,
        configurable: true,
      });
    }
    for (const [k, v] of Object.entries(b)) {
      if (!own(a, k)) {
        Object.defineProperty(out, k, {
          value: v,
          enumerable: true,
          writable: true,
          configurable: true,
        });
      }
    }
    return out;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    const key = listKey(a, b);
    if (key === null) return b;
    const ra = a as Obj[];
    const rb = b as Obj[];
    const out: unknown[] = ra.map((ia) => {
      const match = rb.find((ib) => equal(ib[key], ia[key]));
      return match ? merge(ia, match) : ia;
    });
    out.push(...rb.filter((ib) => !ra.some((ia) => equal(ia[key], ib[key]))));
    return out;
  }
  return b;
}

/** Counts of added, removed and changed values (`order` is not counted). */
export function summary(changes: Change[]): [number, number, number] {
  const n = (op: Op): number => changes.filter((c) => c.op === op).length;
  return [n('add'), n('remove'), n('change')];
}

/** The changes that undo `changes`. */
export function reverse(changes: Change[]): Change[] {
  const swap: Record<string, Op> = { add: 'remove', remove: 'add' };
  const out: Change[] = [...changes]
    .reverse()
    .map((c) => ({ op: swap[c.op] ?? c.op, path: c.path, old: c.new, new: c.old }));
  let i = 0;
  while (i < out.length) {
    if (out[i].op === 'order') {
      const list = out[i].path;
      const inside = (p: string): boolean =>
        list === '$' ? p.startsWith('[') : p.startsWith(list) && p[list.length] === '[';
      let last = -1;
      for (let j = out.length - 1; j > i; j--) {
        if (inside(out[j].path)) {
          last = j;
          break;
        }
      }
      if (last >= 0) {
        const [c] = out.splice(i, 1);
        out.splice(last, 0, c);
        continue;
      }
    }
    i++;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

/** `users[id=2].tags[1]` → steps; `$` → []. */
export function parsePath(path: string): Step[] {
  const steps: Step[] = [];
  const n = path.length;
  let i = path.startsWith('$') ? 1 : 0;
  const err = (msg: string): Error => new Error(`invalid path '${path}': ${msg}`);
  const ident = (): string => {
    const start = i;
    while (i < n && /[A-Za-z0-9_]/.test(path[i])) i++;
    return path.slice(start, i);
  };
  const string = (): string => {
    const start = i;
    i++;
    while (i < n && path[i] !== '"') i += path[i] === '\\' ? 2 : 1;
    i++;
    try {
      return JSON.parse(path.slice(start, i));
    } catch {
      throw err('bad quoted name');
    }
  };
  while (i < n) {
    const ch = path[i];
    if (ch === '.') {
      i++;
      const name = ident();
      if (!name) throw err("name expected after '.'");
      steps.push({ kind: 'key', key: name });
    } else if (ch === '[') {
      i++;
      if (i < n && /[0-9]/.test(path[i])) {
        const start = i;
        while (i < n && /[0-9]/.test(path[i])) i++;
        steps.push({ kind: 'index', index: Number(path.slice(start, i)) });
      } else {
        const name = path[i] === '"' ? string() : ident();
        if (path[i] === '=') {
          i++;
          const start = i;
          if (path[i] === '"') string();
          else while (i < n && path[i] !== ']') i++;
          let value: unknown;
          try {
            value = JSON.parse(path.slice(start, i));
          } catch {
            throw err('bad key value');
          }
          steps.push({ kind: 'match', key: name, value });
        } else {
          steps.push({ kind: 'key', key: name });
        }
      }
      if (path[i] !== ']') throw err("']' expected");
      i++;
    } else if (!steps.length && /[A-Za-z_]/.test(ch)) {
      steps.push({ kind: 'key', key: ident() });
    } else {
      throw err(`unexpected '${ch}'`);
    }
  }
  return steps;
}

const MISSING = Symbol('missing');

const findIndex = (list: unknown[], key: string, v: unknown): number =>
  list.findIndex((x) => isObj(x) && own(x, key) && equal(x[key], v));

function step(value: unknown, s: Step): unknown {
  if (s.kind === 'key' && isObj(value)) return own(value, s.key) ? value[s.key] : MISSING;
  if (s.kind === 'index' && Array.isArray(value))
    return s.index < value.length ? value[s.index] : MISSING;
  if (s.kind === 'match' && Array.isArray(value)) {
    const i = findIndex(value, s.key, s.value);
    return i >= 0 ? value[i] : MISSING;
  }
  return MISSING;
}

function get(value: unknown, steps: Step[]): unknown {
  let v: unknown = value;
  for (const s of steps) {
    if (v === MISSING) return MISSING;
    v = step(v, s);
  }
  return v;
}

const short = (v: unknown): string => {
  if (v === MISSING) return 'nothing';
  const s = json(v);
  return s.length <= 60 ? s : `${s.slice(0, 59)}…`;
};

function setAt(parent: unknown, s: Step, value: unknown): void {
  if (s.kind === 'key') {
    Object.defineProperty(parent as Obj, s.key, {
      value,
      enumerable: true,
      writable: true,
      configurable: true,
    });
  } else if (s.kind === 'index') (parent as unknown[])[s.index] = value;
  else (parent as unknown[])[findIndex(parent as unknown[], s.key, s.value)] = value;
}

function applyOne(box: { v: unknown }, c: Change, force: boolean): void {
  const steps = parsePath(c.path);
  if (c.op === 'order') {
    const list = get(box.v, steps);
    if (!Array.isArray(list)) throw new Error('no list here');
    const key = listKey(list, list);
    if (key === null) throw new Error('the list has no key field');
    const order = (c.new as unknown[]) ?? [];
    const pos = (x: unknown): number => {
      const i = order.findIndex((k) => equal(k, (x as Obj)[key]));
      return i < 0 ? order.length : i;
    };
    const sorted = list
      .map((x, i) => [pos(x), i, x] as const)
      .sort((p, q) => p[0] - q[0] || p[1] - q[1]);
    sorted.forEach((s, i) => {
      list[i] = s[2];
    });
    return;
  }
  if (!steps.length) {
    if (!force && c.op !== 'add' && !equal(box.v, c.old)) {
      throw new Error(`expected ${short(c.old)}, found ${short(box.v)}`);
    }
    box.v = clone(c.new);
    return;
  }
  const current = get(box.v, steps);
  const parent = get(box.v, steps.slice(0, -1));
  const last = steps[steps.length - 1];
  if (parent === MISSING || parent === null || typeof parent !== 'object') {
    throw new Error('the parent does not exist');
  }
  if (c.op === 'change') {
    if (current === MISSING) throw new Error('nothing to change here');
    if (!force && !equal(current, c.old))
      throw new Error(`expected ${short(c.old)}, found ${short(current)}`);
    setAt(parent, last, clone(c.new));
  } else if (c.op === 'add') {
    if (current !== MISSING) {
      if (equal(current, c.new)) return;
      if (!force) throw new Error(`already exists: ${short(current)}`);
      setAt(parent, last, clone(c.new));
      return;
    }
    if (last.kind === 'key' && isObj(parent)) setAt(parent, last, clone(c.new));
    else if (last.kind === 'index' && Array.isArray(parent)) {
      if (last.index > parent.length) {
        throw new Error(`index ${last.index} is past the end (${parent.length} items)`);
      }
      parent.splice(last.index, 0, clone(c.new));
    } else if (last.kind === 'match' && Array.isArray(parent)) parent.push(clone(c.new));
    else throw new Error('cannot add here');
  } else if (c.op === 'remove') {
    if (current === MISSING) throw new Error('nothing to remove here');
    if (!force && !equal(current, c.old))
      throw new Error(`expected ${short(c.old)}, found ${short(current)}`);
    if (last.kind === 'key') delete (parent as Obj)[last.key];
    else if (last.kind === 'index') (parent as unknown[]).splice(last.index, 1);
    else (parent as unknown[]).splice(findIndex(parent as unknown[], last.key, last.value), 1);
  } else {
    throw new Error(`unknown op ${String((c as Change).op)}`);
  }
}

/** Applies what fits (`force`: also over a different old value). */
export function applyWith(
  data: unknown,
  changes: Change[],
  force = false,
): { value: unknown; conflicts: Conflict[] } {
  const box = { v: clone(data) };
  const conflicts: Conflict[] = [];
  changes.forEach((c, index) => {
    try {
      applyOne(box, c, force);
    } catch (e) {
      conflicts.push({ index, path: c.path, reason: (e as Error).message });
    }
  });
  return { value: box.v, conflicts };
}

/** `changes` applied to `data`; throws ConflictError when a change does not fit. */
export function apply(
  data: unknown,
  changes: Change[],
  options: { force?: boolean } = {},
): unknown {
  const { value, conflicts } = applyWith(data, changes, options.force ?? false);
  if (conflicts.length && !options.force) throw new ConflictError(conflicts);
  return value;
}

// ---------------------------------------------------------------------------
// Change sets and history
// ---------------------------------------------------------------------------

/** Now in UTC: `2026-11-01T17:20:00Z`. */
export function now(): string {
  return `${new Date().toISOString().slice(0, 19)}Z`;
}

export function changesJson(changes: Change[]): Change[] {
  return changes.map((c) => ({ op: c.op, path: c.path, old: c.old ?? null, new: c.new ?? null }));
}

export function changesFromJson(value: unknown): Change[] {
  if (!Array.isArray(value)) throw new Error('changes must be a list');
  return value.map((c) => {
    if (!isObj(c) || !['add', 'remove', 'change', 'order'].includes(c.op as string)) {
      throw new Error('a change needs op: add, remove, change or order');
    }
    if (typeof c.path !== 'string') throw new Error('a change needs a path');
    return { op: c.op as Op, path: c.path, old: c.old ?? null, new: c.new ?? null };
  });
}

function utf8(text: string): number[] {
  const out: number[] = [];
  for (const ch of text) {
    const cp = ch.codePointAt(0) as number;
    if (cp < 0x80) out.push(cp);
    else if (cp < 0x800) out.push(0xc0 | (cp >> 6), 0x80 | (cp & 63));
    else if (cp < 0x10000) out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
    else
      out.push(
        0xf0 | (cp >> 18),
        0x80 | ((cp >> 12) & 63),
        0x80 | ((cp >> 6) & 63),
        0x80 | (cp & 63),
      );
  }
  return out;
}

function fnv1a(text: string): bigint {
  let h = BigInt('0xcbf29ce484222325');
  const prime = BigInt('0x100000001b3');
  const mask = BigInt('0xffffffffffffffff');
  for (const b of utf8(text)) {
    h ^= BigInt(b);
    h = (h * prime) & mask;
  }
  return h;
}

/**
 * The id of a change set: FNV-1a of the parent id, date, author, title,
 * description and the changes as compact JSON — 10 hex digits, as in Rust
 * and Python.
 */
export function changeId(
  parent: string | null,
  date: string,
  info: Info,
  changes: Change[],
): string {
  const text = [
    parent ?? '',
    date,
    info.author ?? '',
    info.title ?? '',
    info.description ?? '',
    json(changesJson(changes)),
  ].join('\n');
  return fnv1a(text).toString(16).padStart(16, '0').slice(0, 10);
}

/** A change set; `parent` is the id of the previous one in the history. */
export function changeSet(
  changes: Change[],
  info: Info = {},
  parent: string | null = null,
): ChangeSet {
  const date = info.date || now();
  const clean = {
    title: info.title || null,
    author: info.author || null,
    description: info.description || null,
  };
  return {
    id: changeId(parent, date, clean, changes),
    date,
    ...clean,
    changes: changesJson(changes),
  };
}

/** `{id, date, author, title, description, changes}` in this field order. */
function setJson(s: ChangeSet): Obj {
  return {
    id: s.id,
    date: s.date,
    author: s.author ?? null,
    title: s.title ?? null,
    description: s.description ?? null,
    changes: changesJson(s.changes),
  };
}

function setFromJson(v: unknown): ChangeSet {
  if (!isObj(v) || !own(v, 'changes')) throw new Error("a change set needs 'changes'");
  const s = (k: string): string | null => (typeof v[k] === 'string' ? (v[k] as string) : null);
  return {
    id: s('id') ?? '',
    date: s('date') ?? '',
    author: s('author'),
    title: s('title'),
    description: s('description'),
    changes: changesFromJson(v.changes),
  };
}

function compact(data: unknown): string {
  return new Encoder({
    ...DEFAULT_CONFIG,
    compact: true,
    escapeNewLines: true,
    indent: 2,
    includeType: true,
    includeComments: true,
    colorize: false,
    includeArraySize: false,
    arraySizeMin: 1,
  }).encode(parseDataToNode(data));
}

function decodeText(text: string): unknown {
  const r = new Decoder(text, '', true).decode();
  if (r.errors.length) throw new Error(String(r.errors[0]));
  return r.node.dict();
}

class Scan {
  i = 0;
  constructor(readonly t: string) {}
  peek(): string {
    return this.t[this.i] ?? '';
  }
  at(s: string): boolean {
    return this.t.startsWith(s, this.i);
  }
  ws(): void {
    while (this.i < this.t.length && /\s/.test(this.t[this.i])) this.i++;
  }
  string(q: string): void {
    this.i++;
    while (this.i < this.t.length) {
      const ch = this.t[this.i++];
      if (ch === '\\' && q === '"') this.i++;
      else if (ch === q) return;
    }
  }
  comment(): void {
    this.i += 2;
    let depth = 1;
    while (depth && this.i < this.t.length) {
      if (this.at('/*')) {
        depth++;
        this.i += 2;
      } else if (this.at('*/')) {
        depth--;
        this.i += 2;
      } else this.i += this.t[this.i] === '\\' ? 2 : 1;
    }
  }
  ident(): string {
    if (this.peek() === '`') {
      const start = this.i + 1;
      this.string('`');
      return this.t.slice(start, Math.max(start, this.i - 1));
    }
    const start = this.i;
    while (this.i < this.t.length && /[A-Za-z0-9_]/.test(this.t[this.i])) this.i++;
    return this.t.slice(start, this.i);
  }
  group(): void {
    let depth = 0;
    while (this.i < this.t.length) {
      const ch = this.t[this.i];
      if (ch === '"' || ch === '`') {
        this.string(ch);
        continue;
      }
      if (this.at('/*')) {
        this.comment();
        continue;
      }
      if ('<[({'.includes(ch)) depth++;
      else if ('>])}'.includes(ch)) {
        depth--;
        if (depth <= 0) {
          this.i++;
          return;
        }
      }
      this.i++;
    }
  }
  token(): void {
    while (this.i < this.t.length && !/[\s<>()[\]{},/]/.test(this.t[this.i])) this.i++;
  }
  value(): void {
    this.ws();
    const ch = this.peek();
    if (ch === '<') {
      this.group();
      this.value();
    } else if (ch === '@') {
      this.i++;
      this.ident();
      this.ws();
      if (this.peek() === '<') this.group();
      this.value();
    } else if (ch && '[({'.includes(ch)) this.group();
    else if (ch === '"') this.string('"');
    else this.token();
  }
  attribute(out: Obj): void {
    this.i++;
    const name = this.ident();
    this.ws();
    let value: unknown = true;
    if (this.peek() === '=') {
      this.i++;
      this.ws();
      const start = this.i;
      this.value();
      const raw = this.t.slice(start, this.i);
      try {
        value = decodeText(raw);
      } catch {
        value = raw;
      }
    }
    Object.defineProperty(out, name, {
      value,
      enumerable: true,
      writable: true,
      configurable: true,
    });
  }
}

/**
 * The attributes of the document itself (`$name=value` outside the data, in
 * or out of `// … //` blocks), e.g. `$changes`.
 */
export function attributes(text: string): Obj {
  const s = new Scan(text);
  const out: Obj = {};
  for (;;) {
    s.ws();
    const ch = s.peek();
    if (!ch) break;
    if (s.at('/*')) s.comment();
    else if (s.at('//')) {
      s.i += 2;
      for (;;) {
        s.ws();
        const c = s.peek();
        if (!c) break;
        if (s.at('//')) {
          s.i += 2;
          break;
        }
        if (s.at('/*')) s.comment();
        else if (c === '$') s.attribute(out);
        else if (c === '#') {
          s.i++;
          s.ident();
        } else {
          const start = s.i;
          s.ident();
          s.ws();
          if (s.peek() === '=') {
            s.i++;
            s.ws();
            s.value();
          }
          if (s.i === start) s.i++;
        }
      }
    } else if (ch === '$') s.attribute(out);
    else if (ch === '#' || ch === '@') {
      s.i++;
      s.ident();
    } else if ('<[({'.includes(ch)) s.group();
    else if (ch === '"') s.string('"');
    else {
      const start = s.i;
      s.token();
      if (s.i === start) s.i++;
    }
  }
  return out;
}

/** The history of a document: its `$changes` attribute (oldest first). */
export function history(text: string): ChangeSet[] {
  const value = attributes(text).changes;
  if (!Array.isArray(value)) return [];
  const out: ChangeSet[] = [];
  for (const v of value) {
    try {
      out.push(setFromJson(v));
    } catch {
      // not a change set
    }
  }
  return out;
}

/** `data` as compact AK-DATA with `// $changes=[…] //` after it. */
export function withHistory(data: unknown, past: ChangeSet[]): string {
  const body = compact(data);
  if (!past.length) return body;
  return `${body} // $changes=${compact(past.map(setJson))} //`;
}

/**
 * The document `text` updated to `data`, the change recorded in its history
 * (unchanged when the data is the same).
 */
export function commit(text: string, data: unknown, info: Info = {}): string {
  let old: unknown;
  let past: ChangeSet[] = [];
  try {
    old = JSON.parse(text);
  } catch {
    old = decodeText(text);
    past = history(text);
  }
  const changes = diff(old, data);
  if (changes.length) {
    past = [...past, changeSet(changes, info, past.length ? past[past.length - 1].id : null)];
  }
  return withHistory(data, past);
}
