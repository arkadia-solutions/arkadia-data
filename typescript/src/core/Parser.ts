import { Node, type Primitive } from '../models/Node';
import { Schema, SchemaKind } from '../models/Schema';

export class EncodingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'EncodingError';
  }
}

// --------------------------------------------------------------
// Helper: Type Wrapper
// --------------------------------------------------------------
const TYPE_STRING = 'string';
const TYPE_NUMBER = 'number';
const TYPE_BOOL = 'bool';
const TYPE_NULL = 'null';
// const TYPE_ANY = "any";

// --------------------------------------------------------------
// Primitive -> Node(primitive)
// --------------------------------------------------------------

function parsePrimitive(v: Primitive): Node {
  let schema: Schema;

  if (typeof v === 'string') {
    schema = new Schema(SchemaKind.PRIMITIVE, { typeName: TYPE_STRING });
  } else if (typeof v === 'boolean') {
    schema = new Schema(SchemaKind.PRIMITIVE, { typeName: TYPE_BOOL });
  } else if (typeof v === 'number') {
    schema = new Schema(SchemaKind.PRIMITIVE, { typeName: TYPE_NUMBER });
  } else if (v === null || v === undefined) {
    schema = new Schema(SchemaKind.PRIMITIVE, { typeName: TYPE_NULL });
  } else {
    throw new EncodingError(`Unsupported primitive: ${v}`);
  }

  return new Node(schema, { value: v });
}

// --------------------------------------------------------------
// List -> Node(list)
// --------------------------------------------------------------

function parseList(arr: unknown[]): Node {
  // 1. EMPTY LIST
  if (arr.length === 0) {
    const elementSchema = new Schema(SchemaKind.PRIMITIVE, { typeName: 'any' });
    const listSchema = new Schema(SchemaKind.LIST, { element: elementSchema });
    return new Node(listSchema, { elements: [] });
  }

  // 2. PARSE ALL ITEMS
  const parsedItems: Node[] = arr.map((v) => parseDataToNode(v));

  const unifiedElementSchema = elementSchema(parsedItems);

  // 4. FINALIZE
  const listSchema = new Schema(SchemaKind.LIST, {
    typeName: 'list',
    element: unifiedElementSchema,
  });

  return new Node(listSchema, { elements: parsedItems });
}

/**
 * The header schema of a list.
 *
 * Lists of records get the field layout shared by most of them, so those
 * records can be written positionally under one header; the others are
 * written self-describing ({key: value}). When no layout is shared by at
 * least two records (or the only one) and half of the list, the list gets
 * no record header.
 */
/**
 * The most frequent non-null primitive type (first seen wins ties), or null
 * when there is none. Nulls never need a type tag, so they do not vote.
 */
function commonType(schemas: Schema[]): string | null {
  const counts = new Map<string, number>();
  for (const sc of schemas) {
    if (sc.kind === SchemaKind.PRIMITIVE && sc.typeName !== 'null') {
      counts.set(sc.typeName, (counts.get(sc.typeName) || 0) + 1);
    }
  }
  let best: string | null = null;
  let n = 0;
  for (const [t, c] of counts) {
    if (c > n) {
      best = t;
      n = c;
    }
  }
  return best;
}

/** A header cannot spell a key with a backtick; such records are named. */
export function headerSafe(key: string): boolean {
  return !key.includes('`');
}

function headerable(node: Node): boolean {
  return Object.keys(node.fields).every(headerSafe);
}

function elementSchema(items: Node[]): Schema {
  const first = items[0].schema;
  if (first.kind === SchemaKind.PRIMITIVE) {
    // The most common non-null type; other values get an inline <type> tag.
    const common = commonType(items.map((i) => i.schema));
    if (common && common !== first.typeName) {
      return new Schema(SchemaKind.PRIMITIVE, { typeName: common });
    }
    return first;
  }
  if (first.kind !== SchemaKind.RECORD) {
    // Lists: the first element sets the type; others are tagged.
    return first;
  }

  const counts = new Map<string, number>();
  const layout = new Map<string, Schema>();
  for (const item of items) {
    if (item.schema.kind !== SchemaKind.RECORD || !headerable(item)) continue;
    const keys = JSON.stringify(Object.keys(item.fields).sort());
    counts.set(keys, (counts.get(keys) || 0) + 1);
    if (!layout.has(keys)) layout.set(keys, item.schema);
  }

  let bestKeys = '';
  let bestCount = 0;
  for (const [keys, count] of counts) {
    if (count > bestCount) {
      bestKeys = keys;
      bestCount = count;
    }
  }
  const exact = (bestCount >= 2 || items.length === 1) && bestCount * 2 >= items.length;
  const union = unionSchema(items);
  if (union && union.fitting > (exact ? bestCount : 0)) return union.schema;
  if (exact) {
    const element = new Schema(SchemaKind.RECORD);
    const fitting = items.filter(
      (i) =>
        i.schema.kind === SchemaKind.RECORD &&
        headerable(i) &&
        JSON.stringify(Object.keys(i.fields).sort()) === bestKeys,
    );
    for (let field of layout.get(bestKeys)!.fields) {
      if (field.kind === SchemaKind.PRIMITIVE) {
        const common = commonType(
          fitting
            .filter((i) => hasOwn(i.fields, field.name))
            .map((i) => i.fields[field.name].schema),
        );
        if (common && common !== field.typeName) {
          field = new Schema(SchemaKind.PRIMITIVE, { typeName: common, name: field.name });
        }
      }
      element.addField(field);
    }
    return element;
  }
  return new Schema(SchemaKind.PRIMITIVE, { typeName: 'any' });
}

// Object.hasOwn needs ES2022; fields are objects without a prototype.
const hasOwn = (o: object, k: string): boolean =>
  // biome-ignore lint/suspicious/noPrototypeBuiltins: Object.hasOwn is ES2022
  Object.prototype.hasOwnProperty.call(o, k);

/** The record's keys are exactly the first k names of a header (k >= 1). */
function prefixFits(item: Node, names: string[]): boolean {
  const keys = Object.keys(item.fields);
  const k = keys.length;
  if (k < 1 || k > names.length) return false;
  const head = new Set(names.slice(0, k));
  return keys.every((key) => head.has(key));
}

/**
 * A header with every field of the records — the most frequent first — under
 * which a record whose keys are its first k fields is written positionally with
 * k values (the decoder leaves the missing trailing fields out). Null when fewer
 * than two records, or fewer than half of the list, fit.
 */
function unionSchema(items: Node[]): { schema: Schema; fitting: number } | null {
  // Records whose every key a header can spell (an empty key cannot be).
  const records = items.filter(
    (i) =>
      i.schema.kind === SchemaKind.RECORD &&
      headerable(i) &&
      Object.keys(i.fields).every((k) => k !== ''),
  );
  if (records.length < 2) return null;
  const freq = new Map<string, number>();
  const base = new Map<string, Schema>();
  const order: string[] = [];
  for (const r of records) {
    for (const [name, child] of Object.entries(r.fields)) {
      freq.set(name, (freq.get(name) || 0) + 1);
      if (!base.has(name)) {
        base.set(name, child.schema);
        order.push(name);
      }
    }
  }
  const names = order
    .map((name, i) => ({ name, i }))
    .sort((a, b) => freq.get(b.name)! - freq.get(a.name)! || a.i - b.i)
    .map((x) => x.name);
  const fitting = records.filter((r) => prefixFits(r, names)).length;
  if (fitting < 2 || fitting * 2 < items.length) return null;
  const element = new Schema(SchemaKind.RECORD);
  for (const name of names) {
    let field = base.get(name)!;
    if (field.kind === SchemaKind.PRIMITIVE) {
      const common = commonType(
        records.filter((r) => hasOwn(r.fields, name)).map((r) => r.fields[name].schema),
      );
      if (common && common !== field.typeName) {
        field = new Schema(SchemaKind.PRIMITIVE, { typeName: common, name });
      }
    }
    element.addField(field);
  }
  return { schema: element, fitting };
}

// --------------------------------------------------------------
// Dict -> Node(record)
// --------------------------------------------------------------

function parseDict(obj: Record<string, unknown>): Node {
  /**
   * JSON objects -> named records.
   */
  const fieldsData: Record<string, Node> = Object.create(null);
  const schema = new Schema(SchemaKind.RECORD);

  for (const [key, rawValue] of Object.entries(obj)) {
    const childNode = parseDataToNode(rawValue);

    // Assign field name to the child's schema so it knows it is a field
    childNode.schema.name = key;

    fieldsData[key] = childNode;
    schema.addField(childNode.schema);
  }

  if (!Object.keys(obj).every(headerSafe)) {
    // A key a header cannot spell: the record is written by name.
    schema.clearFields();
  }

  return new Node(schema, { fields: fieldsData });
}

// --------------------------------------------------------------
// Main entrypoint
// --------------------------------------------------------------

export function parseDataToNode(value: Node | unknown): Node {
  if (value instanceof Node) {
    return value;
  }

  // 1. Primitive Check
  if (
    value === null ||
    value === undefined ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return parsePrimitive(value);
  }

  // 2. List Check
  if (Array.isArray(value)) {
    return parseList(value);
  }

  // 3. Object Check (Dict)
  if (typeof value === 'object') {
    return parseDict(value as Record<string, unknown>);
  }

  throw new EncodingError(`Unsupported structure type: ${typeof value}`);
}
