import { Meta, MetaInfo, MetaProps } from './Meta';

export enum SchemaKind {
  PRIMITIVE = 'PRIMITIVE', // int, string, bool, null
  RECORD = 'RECORD', // User, Point, or anonymous <...>
  LIST = 'LIST', // Array/Sequence
  DICT = 'DICT', // Future-proofing: Key-Value pairs
  ANY = 'ANY', // Fallback
}

export interface SchemaProps extends MetaProps {
  typeName?: string;
  name?: string;
  fields?: Schema[];
  element?: Schema;
  key?: Schema;
  value?: Schema;
  required?: boolean;
}

export class Schema extends Meta {
  kind: SchemaKind;
  typeName: string;
  name: string;

  // Structure references
  element: Schema | null;
  key: Schema | null;
  value: Schema | null;

  // Flags
  required: boolean;

  // Internal fields storage
  private _fieldsList: Schema[] = [];
  private _fieldsMap: Map<string, Schema> = new Map();

  constructor(kind: SchemaKind, props: SchemaProps = {}) {
    super(props);

    this.kind = kind;
    this.typeName = props.typeName || 'any';
    this.name = props.name || '';

    this.element = props.element || null;
    this.key = props.key || null;
    this.value = props.value || null;
    this.required = props.required || false;

    if (props.fields) {
      props.fields.forEach((f) => this.addField(f));
    }
  }

  // -----------------------------------------------------------
  // Properties (Is...)
  // -----------------------------------------------------------

  get isPrimitive(): boolean {
    return this.kind === SchemaKind.PRIMITIVE;
  }
  get isRecord(): boolean {
    return this.kind === SchemaKind.RECORD;
  }
  get isList(): boolean {
    return this.kind === SchemaKind.LIST;
  }

  get isAny(): boolean {
    return (
      this.kind === SchemaKind.ANY ||
      (this.typeName === 'any' && this.kind === SchemaKind.PRIMITIVE) ||
      (this.typeName === 'any' && this.kind === SchemaKind.RECORD)
    );
  }

  get fields(): Schema[] {
    return this._fieldsList;
  }

  // -----------------------------------------------------------
  // Field Management
  // -----------------------------------------------------------

  clearFields(): void {
    this._fieldsList = [];
    this._fieldsMap.clear();
  }

  addField(field: Schema): void {
    // Python logic: Auto-switch to RECORD if adding fields
    if (this.kind !== SchemaKind.RECORD) {
      this.kind = SchemaKind.RECORD;
    }

    // Auto-naming if missing
    const fName = field.name || String(this._fieldsList.length);
    field.name = fName;

    this._fieldsList.push(field);
    this._fieldsMap.set(fName, field);
  }

  /**
   * Equivalent to Python's __getitem__.
   * Allows access by numeric index or field name string.
   */
  getField(key: number | string): Schema | undefined {
    if (!this.isRecord) {
      throw new Error(`Schema kind ${this.kind} is not subscriptable (not a RECORD).`);
    }
    if (typeof key === 'number') {
      return this._fieldsList[key];
    }
    return this._fieldsMap.get(key);
  }

  /**
   * Replaces an existing field with a new definition based on field.name.
   * Preserves the original order in the fields list.
   * If the field does not exist, it appends it (like addField).
   */
  replaceField(field: Schema): void {
    const fName = field.name;
    if (!fName) {
      throw new Error('Cannot replace a field without a name.');
    }

    if (this._fieldsMap.has(fName)) {
      // 1. Retrieve the old object to find its index
      const oldField = this._fieldsMap.get(fName)!;
      const idx = this._fieldsList.indexOf(oldField);

      if (idx !== -1) {
        // 2. Replace in list (preserve order)
        this._fieldsList[idx] = field;
      } else {
        // Fallback safety (should not happen if map/list synced)
        this._fieldsList.push(field);
      }

      // 3. Update map
      this._fieldsMap.set(fName, field);
    } else {
      // Field doesn't exist, treat as add
      this.addField(field);
    }
  }

  // -----------------------------------------------------------
  // Meta Management
  // -----------------------------------------------------------

  clearMeta(): void {
    this.clearCommonMeta();
    this.required = false;
  }

  applyMeta(info: MetaInfo | Schema | undefined): void {
    if (!info) return;
    // 1. Apply common stuff (meta dict, comments, tags)
    this.applyCommonMeta(info);

    // 2. Apply Schema-specific constraints
    if (info.required) {
      this.required = true;
    }
  }

  // -----------------------------------------------------------
  // Debug / Representation
  // -----------------------------------------------------------

  /**
   * Technical debug representation.
   * Format: <Schema(KIND:type_name) name='...' details...>
   */
  toString(): string {
    // 1. Basic Info: Kind and TypeName
    const kindStr = this.kind;

    let typeLabel = '';
    if (this.typeName && this.typeName !== 'any' && this.typeName !== this.kind) {
      typeLabel = `:${this.typeName}`;
    }

    const header = `<Schema(${kindStr}${typeLabel})`;

    // 2. Field Name
    const nameStr = this.name ? ` name="${this.name}"` : '';

    // 3. Details
    const details: string[] = [];

    if (this.required) details.push('!required');

    const attrKeys = Object.keys(this.attr);
    if (attrKeys.length > 0)
      details.push(`attr=[${attrKeys.map((a) => '"' + a + '"').join(', ')}]`);

    if (this.tags.length > 0) details.push(`tags=[${this.tags.join(', ')}]`);
    if (this.comments.length > 0) details.push(`comments=${this.comments.length}`);

    // Structure: Record
    if (this.isRecord) {
      const count = this._fieldsList.length;
      if (count > 0) {
        const limit = 3;
        const fieldNames = this._fieldsList.slice(0, limit).map((f) => f.name);
        if (count > limit) fieldNames.push('...');
        details.push(`fields(${count})=[${fieldNames.join(', ')}]`);
      } else {
        details.push('fields=[]');
      }
    }
    // Structure: List
    else if (this.isList) {
      const elType = this.element ? this.element.typeName || 'None' : 'None';
      const elKind = this.element ? this.element.kind : 'ANY';
      details.push(`element=${elKind}:${elType}`);
    }

    const detailsStr = details.length > 0 ? ' ' + details.join(' ') : '';

    return `${header}${nameStr}${detailsStr}>`;
  }
}
