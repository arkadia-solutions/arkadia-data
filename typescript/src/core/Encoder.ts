import { EncoderConfig } from '../config';
import { Meta } from '../models/Meta';
import { Node, Primitive } from '../models/Node';
import { Schema } from '../models/Schema';

class Colors {
  static RESET = '\x1b[0m';
  static STRING = '\x1b[92m'; // green
  static NUMBER = '\x1b[94m'; // blue
  static BOOL = '\x1b[95m'; // magenta
  static NULL = '\x1b[90m'; // gray
  static TYPE = '\x1b[96m'; // cyan
  static KEY = '\x1b[93m'; // yellow
  static SCHEMA = '\x1b[91m'; // red (for @TypeName)
  static TAG = '\x1b[91m';
  static ATTR = '\x1b[93m';
}

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
          schemaPrefix = sTxt + '\n' + ' '.repeat(baseIndent);
        }
      }
    }

    // 3. Encode Data
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
      prefix = this.c(`@${schema.typeName}`, Colors.SCHEMA);
    }

    // Przygotowanie meta (ale jeszcze nie użycie, bo w liście może się zmienić)
    // W Pythonie: meta = self._meta_wrapped(schema) if include_meta else ""
    // Tutaj obliczamy dynamicznie tam gdzie potrzeba, bo w liście modyfikujemy obiekt schema.

    // --- PRIMITIVE ---
    if (schema.isPrimitive) {
      const metaPrefix = includeMeta ? this.metaInline(schema) : '';
      // Python: return ind + ((meta_prefix + " ") if meta_prefix else "") + self._c(...)
      const metaStr = metaPrefix ? metaPrefix + ' ' : '';
      return ind + metaStr + this.c(schema.typeName, Colors.TYPE);
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
      if (schema.element && schema.element.isRecord) {
        // We reuse the _record_fields logic but wrap in <[ ... ]>
        const innerFields = this.encodeSchemaFields(schema.element);

        // FIX: Use 'pad' variable to remove spaces in compact mode
        return ind + prefix + '<' + pad + '[' + listMeta + innerFields + pad + ']' + pad + '>';
      }

      // Standard List [Type]
      const inner = this.encodeSchema(schema.element!, 0, false).trim();
      return ind + '[' + listMeta + this.c(inner, Colors.TYPE) + ']';
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
        return ind + prefix + '<' + pad + recordMeta + 'any' + pad + '>';
      }

      // Encode Fields
      const innerFields = this.encodeSchemaFields(schema);

      // FIX: Use 'pad' variable to remove spaces in compact mode
      return ind + prefix + '<' + pad + recordMeta + innerFields + pad + '>';
    }

    // Fallback (ANY)
    const meta = includeMeta ? this.metaWrapped(schema) : '';
    return ind + `<${meta}any>`;
  }

  // --- Helper to deduplicate field encoding logic ---
  private encodeSchemaFields(schema: Schema): string {
    const parts: string[] = [];
    const pad = this.config.compact ? '' : ' ';

    for (const field of schema.fields) {
      let str = '';

      const metaPrefix = this.metaInline(field);
      if (metaPrefix) {
        str += metaPrefix + ' ';
      }

      // 3. Field Name
      str += this.c(field.name, Colors.KEY);

      // 4. Field Type
      const fieldType = this.encodeSchema(field, 0, false).trim();

      // Logic to decide when to print the type signature
      const isStructure = !field.isPrimitive;
      const isExplicitPrimitive = this.config.includeType && field.typeName !== 'any';

      if (fieldType && (isStructure || isExplicitPrimitive)) {
        str += `:${pad}${this.c(fieldType, Colors.TYPE)}`;
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
    if (!expectedSchema || expectedSchema.isAny) return true;
    if (!nodeSchema) return true;

    // Check general kind
    if (nodeSchema.kind !== expectedSchema.kind) return false;

    // Check specific primitive type name (e.g. int vs string)
    if (nodeSchema.isPrimitive && expectedSchema.isPrimitive) {
      return nodeSchema.typeName === expectedSchema.typeName;
    }

    return true;
  }

  private getTypeLabel(schema: Schema): string {
    if (schema.isPrimitive) return schema.typeName || 'any';
    if (schema.isList) {
      const inner = schema.element ? this.getTypeLabel(schema.element) : 'any';
      return `[${inner}]`;
    }
    if (schema.isRecord && schema.typeName && schema.typeName !== 'any') {
      return schema.typeName;
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
      items.push(this.c('!required', Colors.TAG));
    }

    // 3. Attributes & Tags
    if (this.config.includeMeta) {
      const currentAttr = obj.attr || {};
      for (const [k, v] of Object.entries(currentAttr)) {
        const valStr = this.primitiveValue(v);
        items.push(this.c(`$${k}=`, Colors.ATTR) + valStr);
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
        this.c(`/${pad}`, Colors.SCHEMA) + content + this.c(`${pad}/`, Colors.SCHEMA);
      return this.config.compact ? wrappedContent + ' ' : ' ' + wrappedContent + ' ';
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

  private escapeNewlines(text: string): string {
    return text.replace(/\r\n/g, '\\n').replace(/\r/g, '\\n').replace(/\n/g, '\\n');
  }

  private encodePrimitiveNode(node: Node): string {
    const innerMeta = this.metaInline(node);
    const str = this.primitiveValue(node.value as Primitive);
    return (innerMeta ? innerMeta + ' ' : '') + str;
  }

  private primitiveValue(v: Primitive): string {
    if (typeof v === 'string') return this.encodeString(v);
    if (v === true) return this.c('true', Colors.BOOL);
    if (v === false) return this.c('false', Colors.BOOL);
    if (v === null || v === undefined) return this.c('null', Colors.NULL);
    return this.c(String(v), Colors.NUMBER);
  }

  private encodeString(v: string): string {
    let content = v;
    if (this.config.escapeNewLines) {
      content = this.escapeNewlines(content);
    }
    content = content.replace(/"/g, '\\"');
    return this.c(`"${content}"`, Colors.STRING);
  }

  // -------------------------------------------------------------
  // LIST
  // -------------------------------------------------------------

  private listHeader(node: Node): string {
    let header = '[';
    if (this.config.includeArraySize) {
      const size = node.elements.length;
      header += `${this.c('$size', Colors.KEY)}=${this.c(String(size), Colors.NUMBER)}${this.c(':', Colors.TYPE)}`;
    }
    return header;
  }

  private joinLines(items: string[], sep: string): string {
    if (this.config.compact) return items.join(sep);
    if (sep === '\n') return items.join(sep);
    return items.join(`${sep} `);
  }

  private encodeList(node: Node, indent: number, includeSchema: boolean = false): string {
    const ind = ' '.repeat(indent);
    const childIndent = indent + this.config.indent;

    const innerMeta = this.metaWrapped(node);

    // 1. Generate Header Schema (if requested)
    let schemaHeader = '';
    if (includeSchema && node.schema && node.schema.element) {
      schemaHeader = this.encodeSchema(node.schema.element, 0).trim();
    }
    if (schemaHeader) {
      schemaHeader = schemaHeader + ' ';
    }

    const expectedChild = node.schema ? node.schema.element : null;

    // --- COMPACT MODE ---
    if (this.config.compact) {
      const items: string[] = [];

      for (const el of node.elements) {
        // IMPORTANT: We disable schema inclusion for elements to avoid duplication <...>
        // unless types mismatch drastically.
        let val = this.encode(el, 0, false).trim();

        // Check compatibility & Inject override if needed
        if (!this.schemasAreCompatible(el.schema, expectedChild)) {
          const label = el.schema ? this.getTypeLabel(el.schema) : 'any';
          const tag = this.c(`<${label}>`, Colors.SCHEMA);
          val = `${tag} ${val}`;
        }

        items.push(val);
      }

      return ind + '[' + innerMeta + schemaHeader + items.join(',') + ']';
    }

    // --- PRETTY MODE ---
    const header = this.listHeader(node);
    const out: string[] = [ind + header];

    if (innerMeta) {
      out.push(' '.repeat(childIndent) + innerMeta.trim());
    }

    if (schemaHeader) {
      out.push(' '.repeat(childIndent) + schemaHeader.trim());
    }

    for (const el of node.elements) {
      // IMPORTANT: Disable schema for children
      let val = this.encode(el, childIndent - this.config.startIndent, false).trim();

      // Check compatibility & Inject override if needed
      if (!this.schemasAreCompatible(el.schema, expectedChild)) {
        const label = el.schema ? this.getTypeLabel(el.schema) : 'any';
        const tag = this.c(`<${label}>`, Colors.SCHEMA);
        val = `${tag} ${val}`;
      }

      out.push(' '.repeat(childIndent) + val);
    }

    out.push(ind + ']');
    return this.joinLines(out, '\n');
  }

  // -------------------------------------------------------------
  // RECORD
  // -------------------------------------------------------------
  private encodeRecord(node: Node, indent: number): string {
    const innerMeta = this.metaWrapped(node);

    const parts: string[] = [];
    if (node.schema.fields && node.schema.fields.length > 0) {
      for (const fieldDef of node.schema.fields) {
        const fieldNode = node.fields[fieldDef.name];
        if (fieldNode) {
          let val = this.encode(fieldNode, indent - this.config.startIndent, false).trim();
          val = this.applyTypeTag(val, fieldNode.schema, fieldDef);
          parts.push(val);
        } else {
          parts.push(this.c('null', Colors.NULL));
        }
      }
      const sep = this.config.compact ? ',' : ', ';
      return '(' + innerMeta + parts.join(sep) + ')';
    } else {
      return '(' + innerMeta + this.c('null', Colors.NULL) + ')';
    }
  }
}
