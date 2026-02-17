import { MetaInfo } from '../models/Meta';
import { Node, Primitive } from '../models/Node';
import { Schema, SchemaKind } from '../models/Schema';

// --- ANSI Colors Helper ---
class Ansi {
  static RESET = '\x1b[0m';
  static DIM = '\x1b[2m';
  static BOLD = '\x1b[1m';
  static CYAN = '\x1b[36m';
  static YELLOW = '\x1b[33m';
  static GREEN = '\x1b[32m';
  static RED = '\x1b[31m';
  static MAGENTA = '\x1b[35m';
}

// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1b\[[0-9;]*m/g;

// --- Error/Warning Data Structures ---

export class DecodeError {
  message: string;
  position: number;
  context: string = '';
  schema: Schema | null = null;
  node: Node | null = null;

  constructor(
    message: string,
    position: number,
    schema: Schema | null = null,
    node: Node | null = null,
  ) {
    this.message = message;
    this.position = position;
    this.schema = schema;
    this.node = node;
  }

  toString(): string {
    return `[DecodeError] ${this.message} (at pos ${this.position})`;
  }
}

export class DecodeWarning {
  message: string;
  position: number;
  schema: Schema | null;
  node: Node | null;

  constructor(
    message: string,
    position: number,
    schema: Schema | null = null,
    node: Node | null = null,
  ) {
    this.message = message;
    this.position = position;
    this.schema = schema;
    this.node = node;
  }

  toString(): string {
    return `[DecodeWarn] ${this.message} (at pos ${this.position})`;
  }
}

export interface DecodeResult {
  node: Node;
  schema: Schema | null;
  errors: DecodeError[];
  warnings: DecodeWarning[];
}

// --- DECODER CLASS ---

export class Decoder {
  private static PRIMITIVES = new Set([
    'string',
    'bool',
    'number',
    'null',
    'int',
    'float',
    'binary',
  ]);
  private static PRIMITIVES_MAPPING: Record<string, string> = {
    string: 'string',
    bool: 'bool',
    number: 'number',
    null: 'null',
    int: 'number',
    float: 'number',
    binary: 'binary',
  };
  private static MAX_ERRORS = 50;

  private text: string;
  private debug: boolean;

  // Cursor State
  private i: number = 0;
  private line: number = 0;
  private col: number = 0;

  // Context State
  private pendingMeta: MetaInfo = new MetaInfo();

  // Hierarchy State
  private nodeStack: Node[] = [];
  private schemaStack: Schema[] = [];
  private errors: DecodeError[] = [];
  private warnings: DecodeWarning[] = [];
  private namedSchemas: Map<string, Schema> = new Map();

  constructor(
    text: string,
    schema: string = '',
    removeAnsiColors: boolean = false,
    debug: boolean = false,
  ) {
    let cleanText = schema + text;
    if (removeAnsiColors) {
      cleanText = cleanText.replace(ANSI_RE, '');
    }
    this.text = cleanText;
    this.debug = debug;
  }

  // =========================================================
  // ENTRY
  // =========================================================

  public decode(): DecodeResult {
    this._dbg('decode() start');
    this.parseMeta();

    let rootSchemaContext: Schema | null = null;

    // 1. Schema Processing Loop
    while (!this.eof()) {
      const ch = this.peek();

      // Inline Definition <x:int>
      if (ch === '<') {
        rootSchemaContext = this.parseSchemaBody();
        this.parseMeta();

        // Check lookahead for data start
        const next = this.peek();
        if (next === '(' || next === '{' || next === '[') break;
        continue;
      }

      // Named Schema @Name
      if (ch === '@') {
        const schema = this.parseSchemaAtRef();
        this.parseMeta();

        const next = this.peek();
        if (next === '@' || next === '<') continue;

        rootSchemaContext = schema;
        break;
      }
      break;
    }

    // 2. Push Context
    if (rootSchemaContext) {
      this.pushSchema(rootSchemaContext);
    }

    // 3. Parse Root Node
    let rootNode: Node;
    if (this.eof()) {
      rootNode = this.createNode(null);
    } else {
      rootNode = this.parseNode();
    }

    // 4. Cleanup Context
    if (rootSchemaContext) {
      this.popSchema();
      // Link schema if node ended up generic
      if (!rootNode.schema || rootNode.schema.isAny) {
        rootNode.schema = rootSchemaContext;
      }
    } else {
      rootSchemaContext = rootNode.schema;
    }

    // Final prefix scan
    this.parseMeta();
    this.applyMeta(rootNode);

    this.popNode(); // Just in case
    this._dbg('decode() end');

    return {
      node: rootNode,
      schema: rootSchemaContext,
      errors: this.errors,
      warnings: this.warnings,
    };
  }

  // =========================================================
  // SCHEMA DEFINITION PARSING
  // =========================================================

  private parseSchemaAtRef(): Schema {
    this.advance(1); // @
    const typeName = this.parseIdent();
    this.skipWhitespace();

    if (this.peek() === '<') {
      this._dbg(`defining type ${typeName}`);
      const schema = this.parseSchemaBody(typeName);
      if (schema.isAny) schema.kind = SchemaKind.RECORD;
      this.namedSchemas.set(typeName, schema);
      return schema;
    }

    this._dbg(`referencing type ${typeName}`);
    if (this.namedSchemas.has(typeName)) {
      return this.namedSchemas.get(typeName)!;
    }

    return new Schema(SchemaKind.RECORD, { typeName });
  }

  private parseSchemaBody(typeName: string = ''): Schema {
    const typeNamePrefix = typeName ? `@${typeName}` : '';
    this._dbg(`START parse_schema_body '<' ${typeNamePrefix}`);

    if (!this.expect('<')) {
      const s = this.createSchema(SchemaKind.ANY, typeName);
      this.popSchema();
      return s;
    }

    const schema = this.createSchema(SchemaKind.RECORD, typeName);
    this.parseSchemaBodyContent(schema, '>');
    this.popSchema();

    this._dbg(`END parse_schema_body '>' ${typeNamePrefix}`);
    return schema;
  }

  private parseSchemaBodyContent(schema: Schema, endChar: string) {
    // Python style: iterate and parse meta into schema inside the loop
    let fieldSchema: Schema | null = null;

    while (!this.eof()) {
      this.parseMeta(schema); // Passes schema, so blocks /.../ apply to schema

      const ch = this.peek();
      if (ch === endChar) {
        this.advance(1);
        break;
      }

      // LIST Schema: < [ ... ] >
      if (ch === '[') {
        this.advance(1);
        this._dbg('LIST schema begin');
        schema.kind = SchemaKind.LIST;
        schema.clearFields(); // Python: schema._fields_list = []

        this.applyMeta(schema); // Apply any pending meta

        const elementSchema = new Schema(SchemaKind.ANY);
        this.parseSchemaBodyContent(elementSchema, ']');
        schema.element = elementSchema;

        this.parseMeta(schema);
        if (this.peek() === endChar) this.advance(1);
        this.applyMeta(schema);
        return;
      }

      if (ch === ',') {
        this.applyMeta(fieldSchema || schema);
        this.advance(1);
        continue;
      }

      const name = this.parseIdent();
      if (!name) {
        this.addError('Expected identifier');
        this.advance(1);
        continue;
      }

      this.skipWhitespace();

      // Detect Primitive List Definition [ int ]
      if (Decoder.PRIMITIVES.has(name) && this.peek() !== ':') {
        schema.kind = SchemaKind.PRIMITIVE;
        schema.typeName = Decoder.PRIMITIVES_MAPPING[name];
        continue;
      }

      if (this.peek() === ':') {
        this.advance(1);
        fieldSchema = this.parseSchemaType();
      } else {
        fieldSchema = new Schema(SchemaKind.PRIMITIVE, { typeName: 'any' });
      }

      fieldSchema.name = name;
      this.applyMeta(fieldSchema);

      // Trailing comments handling
      this.parseMeta(schema);
      this.applyMeta(fieldSchema || schema);

      schema.addField(fieldSchema);
    }
    this.applyMeta(fieldSchema || schema);
  }

  private parseSchemaType(): Schema {
    this.parseMeta(this.currentSchema);
    const ch = this.peek();

    if (ch === '[') {
      this.advance(1);
      const lst = new Schema(SchemaKind.LIST);
      this.applyMeta(lst);
      lst.element = this.parseSchemaType();
      this.expect(']');
      return lst;
    }

    if (ch === '@') {
      this.advance(1);
      const name = this.parseIdent();
      this.parseMeta(this.currentSchema);

      if (this.peek() === '<') {
        this._dbg(`Inline definition for @${name}`);
        const s = this.parseSchemaBody(name);
        if (s.isAny) s.kind = SchemaKind.RECORD;
        this.namedSchemas.set(name, s);
        return s;
      }
      if (this.namedSchemas.has(name)) return this.namedSchemas.get(name)!;
      return new Schema(SchemaKind.RECORD, { typeName: name });
    }

    if (ch === '<') {
      return this.parseSchemaBody();
    }

    const name = this.parseIdent();
    if (Decoder.PRIMITIVES.has(name)) {
      const s = new Schema(SchemaKind.PRIMITIVE, { typeName: Decoder.PRIMITIVES_MAPPING[name] });
      this.applyMeta(s);
      return s;
    }
    if (this.namedSchemas.has(name)) return this.namedSchemas.get(name)!;
    if (!name) return new Schema(SchemaKind.ANY);

    return new Schema(SchemaKind.RECORD, { typeName: name });
  }

  // =========================================================
  // NODE DISPATCHER
  // =========================================================

  private parseNode(_parent: Node | null = null): Node {
    this.parseMeta(this.currentNode);

    if (this.eof()) {
      this.addError('Unexpected EOF while expecting a node');
      return this.createNode(null);
    }

    const ch = this.peek();
    let node: Node;

    if (ch === '@') node = this.parseNodeWithSchemaRef();
    else if (ch === '<') node = this.parseNodeWithInlineSchema();
    else if (ch === '[') node = this.parseList();
    else if (ch === '(') node = this.parsePositionalRecord();
    else if (ch === '{') node = this.parseNamedRecord();
    else if (ch === '"') {
      this._dbg('Dispatch: String');
      node = this.parseString();
    } else if ((ch && /\d/.test(ch)) || ch === '-') {
      this._dbg('Dispatch: Number');
      node = this.parseNumber();
    } else if (ch && /[a-zA-Z_]/.test(ch)) {
      this._dbg('Dispatch: RawString/Ident');
      node = this.parseRawString();
    } else {
      this.addError(`Unexpected character '${ch}'`);
      this.advance(1);
      node = this.createNode(null);
    }

    this.applyMeta(node);
    return node;
  }

  private parseNodeWithSchemaRef(): Node {
    this._dbg('Start Node with Ref (@)');
    const schema = this.parseSchemaAtRef();
    this.pushSchema(schema);
    const node = this.parseNode();
    this.popSchema();
    node.schema = schema;
    return node;
  }

  private parseNodeWithInlineSchema(): Node {
    this._dbg('Start Node with Inline (<)');
    const schema = this.parseSchemaBody();
    this.pushSchema(schema);
    const node = this.parseNode();
    this.popSchema();
    node.schema = schema;
    return node;
  }

  // =========================================================
  // STRUCTURE PARSERS
  // =========================================================

  private parseList(): Node {
    this._dbg('Start LIST [');
    this.advance(1); // [

    const node = this.createNode();
    node.elements = [];

    if (node.schema.kind !== SchemaKind.LIST) {
      node.schema.kind = SchemaKind.LIST;
      node.schema.typeName = 'list';
      node.schema.element = new Schema(SchemaKind.ANY);
    }

    const parentSchema = node.schema;
    let childSchema = new Schema(SchemaKind.ANY);
    if (parentSchema && parentSchema.isList && parentSchema.element) {
      childSchema = parentSchema.element;
    }

    let childNode: Node | null = null;

    while (true) {
      this.parseMeta(node); // Passes node, so blocks /.../ apply to list
      this.pushSchema(childSchema);

      if (this.eof()) {
        this.addError('Unexpected EOF: List not closed');
        break;
      }

      if (this.peek() === ']') {
        this.applyMeta(childNode || node);
        this.advance(1);
        break;
      }
      if (this.peek() === ',') {
        this.applyMeta(childNode || node);
        this.advance(1);
        continue;
      }

      childNode = this.parseNode(node);
      node.elements.push(childNode);

      if (parentSchema.element && parentSchema.element.isAny && childNode.schema) {
        parentSchema.element = childNode.schema;
      }

      this.applyMeta(childNode || node);
      this.popNode();
      this.popSchema();
    }
    this.popSchema();
    this._dbg('End LIST ]');
    return node;
  }

  private parsePositionalRecord(): Node {
    this._dbg('Start RECORD (');
    this.advance(1); // (

    const node = this.createNode();
    if (node.schema.kind !== SchemaKind.RECORD) {
      node.schema.kind = SchemaKind.RECORD;
      node.schema.typeName = 'any';
    }

    let index = 0;
    const predefinedFields = node.schema.fields ? [...node.schema.fields] : [];
    let valNode: Node | null = null;

    while (!this.eof()) {
      this.parseMeta(node);

      if (this.peek() === ')') {
        this.applyMeta(valNode || node);
        this.advance(1);
        break;
      }
      if (this.peek() === ',') {
        this.applyMeta(valNode || node);
        this.advance(1);
        continue;
      }

      let fieldSchema = new Schema(SchemaKind.ANY);
      if (index < predefinedFields.length) {
        fieldSchema = predefinedFields[index];
      }

      this.pushSchema(fieldSchema);
      valNode = this.parseNode();

      if (index < predefinedFields.length) {
        const name = predefinedFields[index].name;
        node.fields[name] = valNode;
      } else {
        const name = `_${index}`;
        const inferred = new Schema(valNode.schema.kind, {
          typeName: valNode.schema.typeName || 'any',
        });
        inferred.name = name;
        node.schema.addField(inferred);
        node.fields[name] = valNode;
      }

      this.applyMeta(valNode || node);
      this.popNode();
      this.popSchema();
      index++;
    }
    this._dbg('End RECORD )');
    return node;
  }

  private parseNamedRecord(): Node {
    this._dbg('Start NAMED RECORD {');
    this.advance(1); // {

    const node = this.createNode();
    node.fields = {};

    if (node.schema.kind !== SchemaKind.RECORD) {
      node.schema.kind = SchemaKind.RECORD;
      node.schema.typeName = 'any';
    }

    const currentSchema = node.schema;
    let valNode: Node | null = null;

    while (!this.eof()) {
      this.parseMeta(node);

      if (this.peek() === '}') {
        this.applyMeta(valNode || node);
        this.advance(1);
        break;
      }
      if (this.peek() === ',') {
        this.applyMeta(valNode || node);
        this.advance(1);
        continue;
      }

      let keyName = this.parseIdent();
      if (!keyName) {
        if (this.peek() === '"') {
          keyName = this.readQuotedString();
        } else {
          this.addError('Expected key in record');
          this.advance(1);
          continue;
        }
      }

      this.skipWhitespace();
      this.expect(':');

      let fieldSchema = new Schema(SchemaKind.ANY);
      if (currentSchema && currentSchema.isRecord) {
        const existing = currentSchema.getField(keyName);
        if (existing) fieldSchema = existing;
      }

      this.pushSchema(fieldSchema);
      valNode = this.parseNode();

      if (currentSchema.isRecord) {
        const existing = currentSchema.getField(keyName);
        if (existing && existing.isAny && !valNode.schema.isAny) {
          valNode.schema.name = keyName;
          currentSchema.replaceField(valNode.schema);
        } else if (!existing) {
          const inferred = new Schema(valNode.schema.kind, {
            typeName: valNode.schema.typeName || 'any',
          });
          inferred.name = keyName;
          node.schema.addField(inferred);
        }
      }

      node.fields[keyName] = valNode;
      this.applyMeta(valNode || node);
      this.popNode();
      this.popSchema();
    }
    this._dbg('End NAMED RECORD }');
    return node;
  }

  // =========================================================
  // PREFIX & META PARSING
  // =========================================================

  private parseMeta(obj: Node | Schema | null = null): void {
    while (!this.eof()) {
      this.skipWhitespace();
      const ch = this.peek();
      const nextCh = this.peekNext();

      if (ch === '/' && nextCh === '*') {
        this.pendingMeta.comments.push(this.parseCommentBlock());
        continue;
      }

      if (ch === '/' && nextCh !== '*') {
        this.parseMetaBlock(obj);
        continue;
      }

      if (ch === '$' || ch === '#' || ch === '!') {
        this.parseModifierInline();
        continue;
      }
      break;
    }
  }

  private parseCommentBlock(): string {
    this._dbg('START block comment');
    this.advance(2);
    let nesting = 1;
    const content: string[] = [];

    while (!this.eof() && nesting > 0) {
      const ch = this.text[this.i];

      if (ch === '\\') {
        this.advance(1);
        if (!this.eof()) content.push(this.text[this.i]);
        this.advance(1);
        continue;
      }

      if (ch === '/' && this.peekNext() === '*') {
        nesting++;
        this.advance(2);
        content.push('/*');
        continue;
      }
      if (ch === '*' && this.peekNext() === '/') {
        nesting--;
        this.advance(2);
        if (nesting > 0) content.push('*/');
        continue;
      }

      content.push(ch);
      this.advance(1);
    }

    if (nesting > 0) this.addError('Unterminated comment');
    return content.join('').trim();
  }

  private parseModifierInline(): void {
    const ch = this.peek();
    if (ch === '$') this.parseMetaAttribute(this.pendingMeta);
    else if (ch === '#') this.parseMetaTag(this.pendingMeta);
    else if (ch === '!') this.parseMetaFlag(this.pendingMeta);
    else this.advance(1);
  }

  private parseMetaBlock(obj: Node | Schema | null = null): MetaInfo {
    this.expect('/');
    this._dbg('START meta header /.../');
    const meta = new MetaInfo();

    while (!this.eof()) {
      this.skipWhitespace();
      const ch = this.peek();
      const nextCh = this.peekNext();

      if (ch === '/' && nextCh === '*') {
        meta.comments.push(this.parseCommentBlock());
        continue;
      }

      if (ch === '/') {
        this.advance(1);
        break;
      }

      if (ch === '$') {
        this.parseMetaAttribute(meta);
        continue;
      }
      if (ch === '#') {
        this.parseMetaTag(meta);
        continue;
      }
      if (ch === '!') {
        this.parseMetaFlag(meta);
        continue;
      }

      // Implicit Attribute (Legacy support: key=value without $)
      if (/[a-zA-Z0-9_]/.test(ch || '')) {
        const key = this.parseIdent();
        let val: Primitive = true;

        this.skipWhitespace();
        if (this.peek() === '=') {
          this.advance(1);
          val = this.parsePrimitiveValue();
        }
        this.addWarning(`Implicit attribute '${key}'. Use '$${key}' instead.`);

        meta.attr[key] = val;
        continue;
      }

      this.addError(`Unexpected token in meta block: ${ch}`);
      this.advance(1);
    }

    if (obj) {
      obj.applyMeta(meta);
    } else {
      this.addWarning(`There is no parent to add the meta block '${meta}'`);
      this.pendingMeta.applyMeta(meta);
    }

    this._dbg('END meta header');
    return meta;
  }

  private parseMetaAttribute(meta: MetaInfo): void {
    this.advance(1); // $
    const key = this.parseIdent();
    let val: Primitive = true;
    this.skipWhitespace();
    if (this.peek() === '=') {
      this.advance(1);
      val = this.parsePrimitiveValue();
    }
    meta.attr[key] = val;
    this._dbg(`Meta Attr: $${key}=${val}`);
  }

  private parseMetaTag(meta: MetaInfo): void {
    this.advance(1); // #
    const tag = this.parseIdent();
    meta.tags.push(tag);
    this._dbg(`Meta Tag: #${tag}`);
  }

  private parseMetaFlag(meta: MetaInfo): void {
    this.advance(1); // !
    const flag = this.parseIdent();
    if (flag === 'required') {
      meta.required = true;
      this._dbg('Meta Flag: !required');
    } else {
      this.addWarning(`Unknown flag: !${flag}`);
    }
  }

  // =========================================================
  // HELPERS & LOW-LEVEL PARSERS
  // =========================================================

  private parseIdent(): string {
    this.skipWhitespace();
    const start = this.i;
    if (this.eof()) return '';

    const ch = this.text[this.i];
    if (!/[a-zA-Z_]/.test(ch)) return '';

    this.advance(1);
    while (!this.eof()) {
      const c = this.text[this.i];
      if (/[a-zA-Z0-9_]/.test(c)) this.advance(1);
      else break;
    }
    return this.text.substring(start, this.i);
  }

  private parseString(): Node {
    const val = this.readQuotedString();
    return this.createNode(val);
  }

  private parseNumber(): Node {
    const val = this.readNumber();
    return this.createNode(val);
  }

  private parseRawString(): Node {
    const raw = this.parseIdent();
    let val: Primitive = raw;
    if (raw === 'true') val = true;
    else if (raw === 'false') val = false;
    else if (raw === 'null') val = null;
    return this.createNode(val);
  }

  private parsePrimitiveValue(): Primitive {
    const ch = this.peek();
    if (!ch) return null;
    if (ch === '"') return this.readQuotedString();
    if (/\d/.test(ch) || ch === '-') return this.readNumber();

    const raw = this.parseIdent();
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    if (raw === 'null') return null;
    return raw;
  }

  private readQuotedString(): string {
    this.expect('"');
    let res = '';

    while (!this.eof()) {
      const ch = this.text[this.i];

      // End of string found
      if (ch === '"') {
        break;
      }

      // Escape sequence start
      if (ch === '\\') {
        this.advance(1); // Skip the backslash

        if (this.eof()) {
          this.addError('Unexpected EOF inside string escape');
          break;
        }

        const esc = this.text[this.i];

        if (esc === 'n') res += '\n';
        else if (esc === 't') res += '\t';
        else if (esc === 'r') res += '\r';
        else if (esc === '"') res += '"';
        else if (esc === '\\') res += '\\';
        else res += esc; // Fallback: append character literally

        this.advance(1); // Move past the escaped char
        continue;
      }

      // Normal character
      res += ch;
      this.advance(1);
    }

    this.expect('"');
    return res;
  }

  private readNumber(): number {
    const start = this.i;
    if (this.peek() === '-') this.advance(1);
    while (/\d/.test(this.peek() || '')) this.advance(1);

    if (this.peek() === '.') {
      this.advance(1);
      while (/\d/.test(this.peek() || '')) this.advance(1);
    }

    if (['e', 'E'].includes(this.peek() || '')) {
      this.advance(1);
      if (['+', '-'].includes(this.peek() || '')) this.advance(1);
      while (/\d/.test(this.peek() || '')) this.advance(1);
    }

    const raw = this.text.substring(start, this.i);
    const num = parseFloat(raw);
    if (isNaN(num)) {
      this.addError(`Invalid number format: ${raw}`);
      return 0;
    }
    return num;
  }

  // =========================================================
  // STACK & STATE HELPERS
  // =========================================================

  private get currentSchema(): Schema | null {
    return this.schemaStack.length > 0 ? this.schemaStack[this.schemaStack.length - 1] : null;
  }

  private createSchema(kind: SchemaKind, typeName: string = ''): Schema {
    const s = new Schema(kind, { typeName });
    this.applyMeta(s);
    this.pushSchema(s);
    return s;
  }

  private pushSchema(s: Schema): void {
    this.schemaStack.push(s);
    this._dbg(`PUSH SCHEMA ${s.toString().substring(0, 30)}...`);
  }

  private popSchema(): Schema | null {
    const s = this.schemaStack.pop() || null;
    if (s && s.isList && s.element) {
      s.applyMeta(s.element);
      s.element.clearMeta();
    }
    this._dbg(`POP SCHEMA ${s ? s.toString().substring(0, 30) : 'null'}...`);

    return s;
  }

  private get currentNode(): Node | null {
    return this.nodeStack.length > 0 ? this.nodeStack[this.nodeStack.length - 1] : null;
  }

  private pushNode(n: Node): void {
    this.nodeStack.push(n);
    this._dbg(`PUSH NODE ${n.toString().substring(0, 30)}...`);
  }

  private popNode(): Node | null {
    const n = this.nodeStack.pop() || null;
    this._dbg(`POP NODE ${n ? n.toString().substring(0, 30) : 'null'}...`);
    return n;
  }

  private createNode(value: Primitive = null): Node {
    let currentS = this.currentSchema;
    if (!currentS) {
      currentS = new Schema(SchemaKind.ANY);
      this.pushSchema(currentS);
    }

    let finalS = currentS;

    if (value !== null) {
      let inferred: Schema | null = null;
      if (typeof value === 'boolean')
        inferred = new Schema(SchemaKind.PRIMITIVE, { typeName: 'bool' });
      else if (typeof value === 'number')
        inferred = new Schema(SchemaKind.PRIMITIVE, { typeName: 'number' });
      else if (typeof value === 'string')
        inferred = new Schema(SchemaKind.PRIMITIVE, { typeName: 'string' });

      if (inferred) {
        let compatible = false;
        if (currentS.kind === SchemaKind.ANY) {
          compatible = true;
          finalS = inferred;
        } else if (currentS.typeName === inferred.typeName) {
          compatible = true;
        } else if (
          currentS.typeName === 'number' &&
          (inferred.typeName === 'int' || inferred.typeName === 'float')
        ) {
          compatible = true;
        }

        if (!compatible) {
          finalS = inferred;
        }
      }
    } else {
      if (currentS.isRecord || currentS.isList) {
        finalS = currentS;
      } else {
        finalS = new Schema(SchemaKind.PRIMITIVE, { typeName: 'null' });
      }
    }

    const node = new Node(finalS, { value });
    this.applyMeta(node);
    this.pushNode(node);
    return node;
  }

  private applyMeta(obj: Node | Schema): void {
    obj.applyMeta(this.pendingMeta);
    this.pendingMeta = new MetaInfo();
  }

  private advance(n: number = 1): string {
    let lastChar = '';
    for (let k = 0; k < n; k++) {
      if (this.i >= this.text.length) break;
      const c = this.text[this.i];
      lastChar = c;
      if (c === '\n') {
        this.line++;
        this.col = 1;
      } else {
        this.col++;
      }
      this.i++;
    }
    return lastChar;
  }

  private skipWhitespace(): void {
    while (!this.eof()) {
      const ch = this.peek();
      if (ch && /\s/.test(ch)) {
        this.advance(1);
      } else {
        break;
      }
    }
  }

  private eof(): boolean {
    return this.i >= this.text.length;
  }
  private peek(): string | null {
    return this.eof() ? null : this.text[this.i];
  }
  private peekNext(): string | null {
    return this.i + 1 < this.text.length ? this.text[this.i + 1] : null;
  }

  private expect(ch: string): boolean {
    if (this.peek() !== ch) {
      this.addError(`Expected '${ch}', got '${this.peek()}'`);
      return false;
    }
    this.advance(1);
    return true;
  }

  private addError(msg: string): void {
    if (this.errors.length >= Decoder.MAX_ERRORS) return;
    this._dbg(`ERROR: ${msg}`);
    this.errors.push(new DecodeError(msg, this.i, this.currentSchema, this.currentNode));
  }

  private addWarning(msg: string): void {
    this._dbg(`WARNING: ${msg}`);
    this.warnings.push(new DecodeWarning(msg, this.i, this.currentSchema, this.currentNode));
  }

  private _dbg(msg: string): void {
    if (!this.debug) return;

    const locStr = `${this.line + 1}:${this.col + 1}`;

    const depth = this.nodeStack.length;
    let treePrefix = '';
    if (depth > 0) {
      // Python: "│ " * (depth - 1)
      treePrefix = Ansi.DIM + '│ '.repeat(depth - 1) + '├─ ' + Ansi.RESET;
    }

    const start = Math.max(0, this.i - 10);
    const end = Math.min(this.text.length, this.i + 11);

    // Raw Before: replace newlines, pad start
    const rawBefore = this.text.substring(start, this.i).padStart(10).replace(/\n/g, '↩︎');

    // Raw Current: handle EOF, replace whitespace
    // Note: undefined check needed if i is out of bounds (EOF)
    const charAtI = this.text[this.i] || ' ';
    const rawCurrent = charAtI.replace(/\n/g, '↩︎').replace(/ /g, '·').replace(/\t/g, '→');

    // Raw After: replace newlines, pad end
    const rawAfter = this.text
      .substring(this.i + 1, end)
      .padEnd(10)
      .replace(/\n/g, '↩︎');

    const context = `${Ansi.DIM}${rawBefore}${Ansi.RESET}${Ansi.YELLOW}${rawCurrent}${Ansi.RESET}${Ansi.DIM}${rawAfter}${Ansi.RESET}`;

    let msgColor = Ansi.RESET;
    if (msg.includes('ERROR')) {
      msgColor = Ansi.RED;
    } else if (msg.includes('WARNING')) {
      msgColor = Ansi.YELLOW;
    } else if (msg.includes('→')) {
      msgColor = Ansi.GREEN;
    } else if (msg.includes('PUSH') || msg.includes('POP')) {
      msgColor = Ansi.MAGENTA;
    } else if (msg.includes('START') || msg.includes('END')) {
      msgColor = Ansi.DIM;
    }

    console.log(
      `${Ansi.CYAN}|${locStr.padStart(8)}|${Ansi.RESET}${Ansi.DIM} ${Ansi.RESET}${context}${Ansi.DIM}${Ansi.CYAN}|${Ansi.RESET} ${Ansi.YELLOW}${treePrefix}${Ansi.YELLOW}@${depth}${Ansi.RESET} ${Ansi.DIM}|${Ansi.RESET} ${msgColor}${msg}${Ansi.RESET}`,
    );
  }
}
