import { Node } from '../models/Node';
import { Schema, SchemaKind } from '../models/Schema';

export class EncodingError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "EncodingError";
    }
}

// --------------------------------------------------------------
// Helper: Type Wrapper
// --------------------------------------------------------------
const TYPE_STRING = "string";
const TYPE_NUMBER = "number";
const TYPE_BOOL = "bool";
const TYPE_NULL = "null";
// const TYPE_ANY = "any";

// --------------------------------------------------------------
// Primitive -> Node(primitive)
// --------------------------------------------------------------

function parsePrimitive(v: any): Node {
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

function parseList(arr: any[]): Node {
    // 1. EMPTY LIST
    if (arr.length === 0) {
        const elementSchema = new Schema(SchemaKind.PRIMITIVE, { typeName: "any" });
        const listSchema = new Schema(SchemaKind.LIST, { element: elementSchema });
        return new Node(listSchema, { elements: [] });
    }

    // 2. PARSE ALL ITEMS
    const parsedItems: Node[] = arr.map(v => parseDataToNode(v));

    // Use the first element as the baseline
    const firstSchema = parsedItems[0].schema;
    const isListOfRecords = (firstSchema.kind === SchemaKind.RECORD);

    let unifiedElementSchema: Schema;

    // 3. DETERMINE ELEMENT SCHEMA
    if (isListOfRecords) {
        // RECORDS: Create a unified schema containing ALL fields from ALL items.
        unifiedElementSchema = new Schema(SchemaKind.RECORD, { typeName: "record" });
        const seenFields = new Set<string>();

        for (const item of parsedItems) {
            // Skip non-record items if mixed list (or handle as error depending on strictness)
            if (item.schema.kind === SchemaKind.RECORD) {
                for (const field of item.schema.fields) {
                    if (!seenFields.has(field.name)) {
                        unifiedElementSchema.addField(field);
                        seenFields.add(field.name);
                    }
                }
            }
        }
    } else {
        // PRIMITIVES: Simply take the schema of the first element.
        // We assume the list is homogeneous based on the first item.
        unifiedElementSchema = firstSchema;
    }

    // 4. FINALIZE
    const listSchema = new Schema(SchemaKind.LIST, { 
        typeName: "list", 
        element: unifiedElementSchema 
    });

    return new Node(listSchema, { elements: parsedItems });
}

// --------------------------------------------------------------
// Dict -> Node(record)
// --------------------------------------------------------------

function parseDict(obj: Record<string, any>): Node {
    /**
     * JSON objects -> named records.
     */
    const fieldsData: Record<string, Node> = {};
    const schema = new Schema(SchemaKind.RECORD);

    for (const [key, rawValue] of Object.entries(obj)) {
        const childNode = parseDataToNode(rawValue);

        // Assign field name to the child's schema so it knows it is a field
        childNode.schema.name = key;

        fieldsData[key] = childNode;
        schema.addField(childNode.schema);
    }

    return new Node(schema, { fields: fieldsData });
}

// --------------------------------------------------------------
// Main entrypoint
// --------------------------------------------------------------

export function parseDataToNode(value: any): Node {
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
        return parseDict(value);
    }

    throw new EncodingError(`Unsupported structure type: ${typeof value}`);
}