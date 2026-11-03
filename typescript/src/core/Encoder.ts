import type { EncoderConfig } from '../config';
import type { Meta } from '../models/Meta';
import { Node, type Primitive } from '../models/Node';
import { type Schema, SchemaKind } from '../models/Schema';
import { parseDataToNode } from './Parser';

class Colors {
  static RESET = '\x1b[0m';
  static STRING = '\x1b[92m'; // green
  static NUMBER = '\x1b[94m'; // blue
  static BOOL = '\x1b[95m'; // magenta
  static NULL = '\x1b[90m'; // gray
  static TYPE = '\x1b[96m'; // cyan
  static KEY = '\x1b[93m'; // yellow
  static SCHEMA = '\x1b[91m'; // red (for @TypeName)
  static TAG = '\x1b[35m';
  static ATTR = '\x1b[93m';
}

// Object.hasOwn needs ES2022; the package targets older runtimes too.
const hasOwn = (o: object, k: string): boolean =>
  // biome-ignore lint/suspicious/noPrototypeBuiltins: Object.hasOwn is ES2022
  Object.prototype.hasOwnProperty.call(o, k);

export class Encoder {
  private config: EncoderConfig;

  constructor(config: EncoderConfig) {
    this.config = config;
  }

  // -------------------------------------------------------------
  // PUBLIC ENTRY
  // -------------------------------------------------------------

  public encode(node: Node, indentLevel: number = 0, includeSchema: boolean = true): string {
    const baseIndent = this.config.startIndent + indentLevel;
    let schemaPrefix = '';

    // 2. Prepare Schema Header (e.g. <test: string>)
    const shouldRenderSchema = includeSchema && node.schema !== null && this.config.includeSchema;

    if (shouldRenderSchema) {
      let sTxt = this.encodeSchema(node.schema!, baseIndent).trim();

      // Jeśli wynik nie jest pusty i nie zaczyna się od < ani @, dodaj nawiasy < >
      if (sTxt && !sTxt.startsWith('<') && !sTxt.startsWith('@')) {
        sTxt = `<${sTxt}>`;
      }

      if (sTxt) {
        if (this.config.compact) {
          schemaPrefix = sTxt;
        } else {
          // Newline formatting for schema header
          schemaPrefix = `${sTxt}\n${' '.repeat(baseIndent)}`;
        }
      }
    }

    // 3. Encode Data
    const headerless =
      node.isRecord &&
      node.schema &&
      node.schema.fields.length === 0 &&
      Object.keys(node.fields).length > 0;
    if (
      node.isRecord &&
      node.schema &&
      !this.config.promptOutput &&
      (headerless || !this.fits(node, node.schema))
    ) {
      // The record's own schema cannot describe it (e.g. an empty key):
      // write it self-describing, without a header.
      return this.named(node);
    }

    let data = '';
    if (node.isList) {
      data = this.encodeList(node, baseIndent, false);
    } else if (node.isPrimitive) {
      data = this.encodePrimitiveNode(node);
    } else if (node.isRecord) {
      data = this.encodeRecord(node, baseIndent);
    } else {
      data = this.c('null', Colors.NULL);
    }

    // Final Assembly: Meta -> Schema -> Data
    return `${schemaPrefix}${data}`;
  }

  public encodeSchema(schema: Schema, indent: number, includeMeta: boolean = true): string {
    if (!schema) return '';

    const ind = ' '.repeat(indent);
    let prefix = '';

    const pad = this.config.compact ? '' : ' ';

    // Avoid printing internal/default type names
    if (schema.typeName && schema.isRecord && !schema.isAny) {
      const escapedName = this.escapeIdent(schema.typeName);
      prefix = this.c(`@${escapedName}`, Colors.SCHEMA);
    }

    // Przygotowanie meta (ale jeszcze nie użycie, bo w liście może się zmienić)
    // W Pythonie: meta = self._meta_wrapped(schema) if include_meta else ""
    // Tutaj obliczamy dynamicznie tam gdzie potrzeba, bo w liście modyfikujemy obiekt schema.

    // --- PRIMITIVE ---
    if (schema.isPrimitive) {
      const metaPrefix = includeMeta ? this.metaInline(schema) : '';
      // Python: return ind + ((meta_prefix + " ") if meta_prefix else "") + self._c(...)
      const metaStr = metaPrefix ? `${metaPrefix} ` : '';
      const escapedType = this.escapeIdent(schema.typeName);
      return ind + metaStr + this.c(escapedType, Colors.TYPE);
    }

    // --- LIST ---
    // --- DEBUG ---
    if (schema.isList) {
      if (schema.element) {
        schema.applyMeta(schema.element);
        schema.element.clearMeta();
      }
      const listMeta = includeMeta ? this.metaWrapped(schema) : '';

      // Special Case: List of Records < [ ... ] >
      if (schema.element?.isRecord) {
        // We reuse the _record_fields logic but wrap in <[ ... ]>
        const innerFields = this.encodeSchemaFields(schema.element);

        // FIX: Use 'pad' variable to remove spaces in compact mode
        return `${ind + prefix}<${pad}[${listMeta}${innerFields}${pad}]${pad}>`;
      }

      // Standard List [Type]
      const inner = this.encodeSchema(schema.element!, 0, false).trim();
      return `${ind}[${listMeta}${this.c(inner, Colors.TYPE)}]`;
    }

    // --- RECORD ---
    if (schema.isRecord) {
      // Get Record-level meta (e.g. < / $ver=1 / ... >)
      const recordMeta = includeMeta ? this.metaWrapped(schema) : '';

      if (!schema.fields || schema.fields.length === 0) {
        // If the record is generic (no fields, no specific type name, no meta),
        // return an empty string to avoid printing "<>" or "<any>" before the "{...}".
        if (!prefix && !recordMeta && schema.isAny) {
          return '';
        }
        return `${ind + prefix}<${pad}${recordMeta}any${pad}>`;
      }

      // Encode Fields
      const innerFields = this.encodeSchemaFields(schema);

      // FIX: Use 'pad' variable to remove spaces in compact mode
      return `${ind + prefix}<${pad}${recordMeta}${innerFields}${pad}>`;
    }

    // Fallback (ANY)
    const meta = includeMeta ? this.metaWrapped(schema) : '';
    return `${ind}<${meta}any>`;
  }

  // --- Helper to deduplicate field encoding logic ---
  private encodeSchemaFields(schema: Schema): string {
    const parts: string[] = [];
    const pad = this.config.compact ? '' : ' ';

    for (const field of schema.fields) {
      let str = '';

      const metaPrefix = this.metaInline(field);
      if (metaPrefix) {
        str += `${metaPrefix} `;
      }

      // 3. Field Name
      str += this.c(this.escapeIdent(field.name), Colors.KEY);

      // 4. Field Type
      const fieldType = this.encodeSchema(field, 0, false).trim();

      // Logic to decide when to print the type signature
      const isStructure = !field.isPrimitive;
      const isExplicitPrimitive = this.config.includeType && field.typeName !== 'any';

      if (fieldType && (isStructure || isExplicitPrimitive)) {
        str += `:${this.c(fieldType, Colors.TYPE)}`;
      }

      parts.push(str);
    }

    const sep = `,${pad}`;
    return parts.join(sep);
  }

  // -------------------------------------------------------------
  // HELPER: SCHEMA COMPATIBILITY CHECK
  // -------------------------------------------------------------

  private schemasAreCompatible(nodeSchema: Schema | null, expectedSchema: Schema | null): boolean {
    if (Encoder.isOpen(expectedSchema)) return true;
    if (!expectedSchema) return true;
    if (!nodeSchema) return true;

    // null decodes as null under any primitive type: no tag needed.
    if (nodeSchema.isPrimitive && nodeSchema.typeName === 'null' && expectedSchema.isPrimitive) {
      return true;
    }

    // Check general kind
    if (nodeSchema.kind !== expectedSchema.kind) return false;

    // Check specific primitive type name (e.g. int vs string)
    if (nodeSchema.isPrimitive && expectedSchema.isPrimitive) {
      return nodeSchema.typeName === expectedSchema.typeName;
    }

    return true;
  }

  private getTypeLabel(schema: Schema): string {
    if (schema.isPrimitive) return this.escapeIdent(schema.typeName || 'any');
    if (schema.isList) {
      const inner = schema.element ? this.getTypeLabel(schema.element) : 'any';
      return `[${inner}]`;
    }
    if (schema.isRecord && schema.typeName && schema.typeName !== 'any') {
      return this.escapeIdent(schema.typeName);
    }
    return 'any';
  }

  private applyTypeTag(
    valStr: string,
    nodeSchema: Schema | null,
    expectedSchema: Schema | null,
  ): string {
    if (this.schemasAreCompatible(nodeSchema, expectedSchema)) {
      return valStr;
    }

    // Mismatch detected -> Wrap with tag
    const label = nodeSchema ? this.getTypeLabel(nodeSchema) : 'any';
    const tag = this.c(`<${label}>`, Colors.SCHEMA);
    return `${tag} ${valStr}`;
  }

  // -------------------------------------------------------------
  // META AND COMMENTS (Unified Logic)
  // -------------------------------------------------------------

  private buildMetaString(obj: Meta, wrapped: boolean = false): string {
    const items: string[] = [];
    const pad = this.config.compact ? '' : ' ';

    // 1. Comments
    if (this.config.includeComments && obj.comments) {
      for (const c of obj.comments) {
        const cleaned = c.trim();
        items.push(this.c(`/*${pad}${cleaned}${pad}*/`, Colors.NULL));
      }
    }

    // 2. Modifiers
    if ((obj as Schema).required) {
      items.push(this.c('$required', Colors.TAG));
    }

    // 3. Attributes & Tags
    if (this.config.includeMeta) {
      const currentAttr = obj.attr || {};
      for (const [k, v] of Object.entries(currentAttr)) {
        const escapedKey = this.escapeIdent(k);
        if (typeof v === 'boolean' && v === true) {
          items.push(this.c(`$${escapedKey}`, Colors.ATTR));
        } else {
          // A structured value ($changes=[…]) is written as compact AK-DATA.
          const valStr =
            v !== null && typeof v === 'object'
              ? new Encoder({
                  ...this.config,
                  compact: true,
                  escapeNewLines: true,
                  colorize: false,
                  includeArraySize: false,
                }).encode(parseDataToNode(v))
              : this.primitiveValue(v as Primitive);
          items.push(this.c(`$${escapedKey}=`, Colors.ATTR) + valStr);
        }
      }

      const currentTags = obj.tags || [];
      for (const t of currentTags) {
        items.push(this.c(`#${t}`, Colors.TAG));
      }
    }

    if (items.length === 0) {
      return '';
    }

    const content = items.join(' ');

    if (wrapped) {
      const wrappedContent =
        this.c(`//${pad}`, Colors.SCHEMA) + content + this.c(`${pad}//`, Colors.SCHEMA);
      return this.config.compact ? `${wrappedContent} ` : ` ${wrappedContent} `;
    }

    // Inline: /* c1 */ !req $a=1
    return content;
  }

  private metaInline(obj: Meta): string {
    return this.buildMetaString(obj, false);
  }

  private metaWrapped(obj: Meta): string {
    return this.buildMetaString(obj, true);
  }

  // -------------------------------------------------------------
  // HELPERS
  // -------------------------------------------------------------
  private c(text: string, color: string): string {
    if (!this.config.colorize) return text;
    return `${color}${text}${Colors.RESET}`;
  }

  private encodePrimitiveNode(node: Node): string {
    const innerMeta = this.metaInline(node);
    const str = this.primitiveValue(node.value as Primitive);
    return (innerMeta ? `${innerMeta} ` : '') + str;
  }

  private primitiveValue(v: Primitive): string {
    if (typeof v === 'string') return this.encodeString(v);
    if (v === true) return this.c('true', Colors.BOOL);
    if (v === false) return this.c('false', Colors.BOOL);
    if (v === null || v === undefined) return this.c('null', Colors.NULL);
    return this.c(String(v), Colors.NUMBER);
  }

  private encodeString(v: string): string {
    // 1. Escape backslashes first! (Critical step)
    // We must turn a single literal \ into \\ before processing quotes.
    let content = v.replace(/\\/g, '\\\\');

    // 2. Escape quotes
    // Turn " into \"
    content = content.replace(/"/g, '\\"');

    // 3. Handle newlines and control characters if configured
    if (this.config.escapeNewLines) {
      content = content.replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t');
    }

    // Wrap in quotes and colorize
    return this.c(`"${content}"`, Colors.STRING);
  }

  /**
   * Wraps identifier in backticks if it contains spaces or special characters.
   * Regex: [a-zA-Z_][a-zA-Z0-9_]*
   */
  private escapeIdent(name: string): string {
    if (!name) return '""'; // empty key: only valid in named records {"": value}

    // Standard identifier pattern
    const pattern = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

    if (pattern.test(name)) {
      return name;
    }

    // If it doesn't match, wrap it in backticks
    return `\`${name}\``;
  }

  // -------------------------------------------------------------
  // LOSSLESS ENCODING: positional only when the decoder can map it
  // -------------------------------------------------------------

  /** True when `expected` puts no structural constraint on a value. */
  private static isOpen(expected: Schema | null): boolean {
    if (!expected || expected.kind === SchemaKind.ANY) return true;
    if (expected.isRecord) return expected.fields.length === 0;
    return expected.isPrimitive && expected.typeName === 'any';
  }

  /** True when `node` can be written positionally under `expected`. */
  private fits(node: Node, expected: Schema | null): boolean {
    if (Encoder.isOpen(expected) || !expected) return true;
    if (!node.schema) return true;
    if (node.isRecord) {
      if (!expected.isRecord) return false;
      const names = expected.fields.map((f) => f.name);
      const keys = Object.keys(node.fields);
      // Same names as the header, or as its first k fields (the decoder leaves
      // the missing trailing fields out); differing values are tagged in encodeRecord.
      const k = keys.length;
      return (
        k >= 1 &&
        k <= names.length &&
        new Set(names).size === names.length &&
        names.slice(0, k).every((n) => hasOwn(node.fields, n))
      );
    }
    if (node.isList) return expected.isList;
    return true;
  }

  private elementValue(el: Node, expected: Schema | null): string {
    if (el.isRecord || el.isList) return this.value(el, expected);
    const val = this.encode(el, 0, false).trim();
    if (!this.schemasAreCompatible(el.schema, expected)) {
      const label = el.schema ? this.getTypeLabel(el.schema) : 'any';
      return `${this.c(`<${label}>`, Colors.SCHEMA)} ${val}`;
    }
    return val;
  }

  /** Key of a named record; a key with a backtick is written quoted. */
  private recordKey(key: string): string {
    if (!key.includes('`')) return this.escapeIdent(key);
    const body = key
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
    return `"${body}"`;
  }

  /** Self-describing record form {key: value} that needs no header. */
  private named(node: Node): string {
    const sep = this.config.compact ? ',' : ', ';
    const items: string[] = [];
    for (const [key, child] of Object.entries(node.fields)) {
      const k = this.c(this.recordKey(key), Colors.KEY);
      items.push(`${k}:${this.config.compact ? '' : ' '}${this.value(child, null)}`);
    }
    return `{${this.metaWrapped(node)}${items.join(sep)}}`;
  }

  /** Elements of a nested list, without a header (it is in the parent's). */
  /** $size=N on a list (includeArraySize, lists of arraySizeMin+ items). */
  private size(node: Node): void {
    if (this.config.includeArraySize && node.elements.length >= this.config.arraySizeMin) {
      node.attr.size = node.elements.length;
    }
  }

  private listValues(node: Node, element: Schema | null): string {
    this.size(node);
    const sep = this.config.compact ? ',' : ', ';
    const items = node.elements.map((el) => this.elementValue(el, element));
    return `[${this.metaWrapped(node)}${items.join(sep)}]`;
  }

  /**
   * Encodes a nested value that the decoder will read with schema `expected`.
   * Positional forms are used only when `expected` describes the value;
   * otherwise the value describes itself (named record, tagged list).
   */
  private value(node: Node, expected: Schema | null): string {
    const open = Encoder.isOpen(expected);
    const anyTag = `${this.c('<any>', Colors.SCHEMA)} `;

    if (node.isRecord) {
      if (!open && this.fits(node, expected)) return this.encodeRecord(node, 0, expected);
      const named = this.named(node);
      return open ? named : anyTag + named;
    }

    if (node.isList) {
      if (!open && expected && expected.isList) return this.listValues(node, expected.element);
      const element = node.schema ? node.schema.element : null;
      if (
        element &&
        !Encoder.isOpen(element) &&
        node.elements.every((el) => this.fits(el, element)) &&
        (element.isRecord || !open) &&
        !(element.isRecord && node.elements.length < 2)
      ) {
        // The list carries its own header, e.g. <[id:number,name:string]>.
        let tag = this.encodeSchema(node.schema!, 0, false).trim();
        if (!tag.startsWith('<')) tag = `<${tag}>`;
        return `${this.c(tag, Colors.SCHEMA)} ${this.listValues(node, element)}`;
      }
      const body = this.listValues(node, null);
      return open ? body : anyTag + body;
    }

    const val = this.encode(node, 0, false).trim();
    return this.applyTypeTag(val, node.schema, expected);
  }

  // -------------------------------------------------------------
  // LIST
  // -------------------------------------------------------------
  private encodeList(node: Node, indent: number, includeSchema: boolean = false): string {
    const ind = ' '.repeat(indent);
    const childIndent = indent + this.config.indent;
    const isPrompt = this.config.promptOutput;

    this.size(node);
    const innerMeta = this.metaWrapped(node);

    // 1. Generate Header Schema (Standard only)
    let schemaHeader = '';
    if (!isPrompt && includeSchema && node.schema?.element) {
      schemaHeader = this.encodeSchema(node.schema.element, 0).trim();
      if (schemaHeader) schemaHeader += ' ';
    }

    const expectedChild = node.schema ? node.schema.element : null;

    // --- PROMPT MODE (Full Structural Expansion) ---
    if (isPrompt) {
      let res = `${ind}[\n`;
      if (innerMeta) {
        res += `${' '.repeat(childIndent) + innerMeta.trim()}\n`;
      }

      if (node.schema?.element) {
        // Force recursion into the element's structure using a Dummy Node
        const dummy = new Node(node.schema.element, { value: null });

        // We trim() the blueprint because we manually handle child indentation
        const blueprint = this.encode(dummy, childIndent, false).trim();

        res += `${' '.repeat(childIndent) + blueprint},\n`;
        res += `${' '.repeat(childIndent)}... /* repeat pattern for additional items */\n`;
      } else {
        res += `${' '.repeat(childIndent)}/* any content */\n`;
      }

      res += `${ind}]`;
      return res;
    }

    // --- COMPACT MODE ---
    if (this.config.compact) {
      const items: string[] = [];
      for (const el of node.elements) {
        items.push(this.elementValue(el, expectedChild));
      }
      return `${ind}[${innerMeta}${schemaHeader}${items.join(',')}]`;
    }

    // --- PRETTY MODE ---
    let res = `${ind}[\n`;
    if (innerMeta) {
      res += `${' '.repeat(childIndent) + innerMeta.trim()}\n`;
    }
    if (schemaHeader) {
      res += `${' '.repeat(childIndent) + schemaHeader.trim()}\n`;
    }

    const elementLines: string[] = [];
    for (const el of node.elements) {
      elementLines.push(' '.repeat(childIndent) + this.elementValue(el, expectedChild));
    }

    if (elementLines.length > 0) {
      res += `${elementLines.join(',\n')}\n`;
    }

    res += `${ind}]`;
    return res;
  }

  // -------------------------------------------------------------
  // RECORD
  // -------------------------------------------------------------
  private encodeRecord(node: Node, indent: number, expected: Schema | null = null): string {
    const innerMeta = this.metaWrapped(node);
    const parts: string[] = [];
    const isPrompt = this.config.promptOutput;
    const baseInd = ' '.repeat(indent);
    const childInd = ' '.repeat(indent + this.config.indent);
    // Positional order is the order of the schema the decoder will apply.
    const layout = expected?.isRecord ? expected : node.schema;

    if (layout?.fields && layout.fields.length > 0) {
      let fields = layout.fields;
      if (!isPrompt) {
        // A record that has only the first k fields of the header is written
        // with k values (missing trailing fields stay absent).
        let last = -1;
        fields.forEach((f, i) => {
          if (hasOwn(node.fields, f.name)) last = i;
        });
        if (last >= 0) fields = fields.slice(0, last + 1);
      }
      for (const fieldDef of fields) {
        if (isPrompt) {
          // --- PROMPT MODE: Type Label or Structural Expansion ---
          const fieldName = this.escapeIdent(fieldDef.name);
          let fieldValStructure: string;

          if (fieldDef.isPrimitive) {
            // For primitives, use the type name (e.g., "number")
            fieldValStructure = this.c(this.getTypeLabel(fieldDef), Colors.TYPE);
          } else {
            // For structures (Records/Lists), recurse to get { } or [ ]
            const dummyField = new Node(fieldDef, { value: null });
            fieldValStructure = this.encode(dummyField, indent + this.config.indent, false).trim();
          }

          let line = `${this.c(fieldName, Colors.KEY)}: ${fieldValStructure}`;

          if (fieldDef.comments && fieldDef.comments.length > 0) {
            const comment = fieldDef.comments[0].trim();
            line += ` ${this.c(`/* ${comment} */`, Colors.NULL)}`;
          }
          parts.push(line);
        } else {
          // --- STANDARD MODE (Data values) ---
          const fieldNode = node.fields[fieldDef.name];
          if (fieldNode) {
            parts.push(this.value(fieldNode, fieldDef));
          } else {
            parts.push(this.c('null', Colors.NULL));
          }
        }
      }
    } else if (
      !isPrompt &&
      Object.keys(node.fields).length === 0 &&
      !(layout && (layout.comments.length || Object.keys(layout.attr).length || layout.tags.length))
    ) {
      // An empty JSON object. (A schema carrying meta keeps "<// meta // any>(null)".)
      return `{${innerMeta}}`;
    } else {
      parts.push(this.c('null', Colors.NULL));
    }

    if (isPrompt) {
      const body = parts.join(`,\n${childInd}`);
      const metaStr = innerMeta ? `${childInd + innerMeta.trim()}\n` : '';
      return `{\n${metaStr}${childInd}${body}\n${baseInd}}`;
    }

    const sep = this.config.compact ? ',' : ', ';
    return `(${innerMeta}${parts.join(sep)})`;
  }
}
