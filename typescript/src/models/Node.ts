import { Meta, MetaInfo, MetaProps } from './Meta';
import { Schema } from './Schema';

export interface NodeProps extends MetaProps {
    name?: string;
    value?: any;
    fields?: Record<string, Node>;
    elements?: Node[];
}

/**
 * Canonical runtime data object for AI.DATA.
 * A Node always refers to a Schema which defines how data should be interpreted.
 */
export class Node extends Meta {
    schema: Schema;
    name: string;
    value: any;
    fields: Record<string, Node>;
    elements: Node[];

    constructor(schema: Schema, props: NodeProps = {}) {
        super(props);
        this.schema = schema;
        this.name = props.name || "";
        this.value = props.value ?? null;
        this.fields = props.fields || {};
        this.elements = props.elements ? [...props.elements] : [];
    }

    // -----------------------------------------------------------
    // Introspection helpers
    // -----------------------------------------------------------

    get isPrimitive(): boolean { return this.schema && this.schema.isPrimitive; }
    get isRecord(): boolean { return this.schema && this.schema.isRecord; }
    get isList(): boolean { return this.schema && this.schema.isList; }

    // -----------------------------------------------------------
    // Meta
    // -----------------------------------------------------------

    clearMeta(): void {
        this.clearCommonMeta();
    }

    applyMeta(info: MetaInfo): void {
        // Applies ALL metadata (common stuff: meta dict, comments)
        this.applyCommonMeta(info);
    }



    // -----------------------------------------------------------
    // Conversion Methods (dict / json)
    // -----------------------------------------------------------

    /**
     * Recursively converts the Node into a standard JavaScript object/array/primitive.
     * Equivalent to Python's .dict() method.
     */
    dict(): any {
        if (this.isPrimitive) {
            return this.value;
        }

        if (this.isList) {
            return this.elements.map(element => element.dict());
        }

        if (this.isRecord) {
            const result: Record<string, any> = {};
            for (const [key, fieldNode] of Object.entries(this.fields)) {
                result[key] = fieldNode.dict();
            }
            return result;
        }

        return this.value;
    }

    /**
     * Converts the Node to a JSON string.
     * * @param indent Number of spaces for indentation.
     * @param colorize If true, applies ANSI colors to keys, strings, numbers, etc.
     */
    JSON(indent: number = 2, colorize: boolean = false): string {
        // 1. Convert to standard JS object
        const data = this.dict();

        // 2. Dump to string
        const jsonStr = JSON.stringify(data, null, indent);

        if (!colorize) {
            return jsonStr;
        }

        // 3. Apply Colors (Regex Tokenizer)
        // ANSI codes matching the Encoder class
        const C = {
            RESET: "\x1b[0m",
            STRING: "\x1b[92m", // Green
            NUMBER: "\x1b[94m", // Blue
            BOOL: "\x1b[95m",   // Magenta
            NULL: "\x1b[90m",   // Gray
            KEY: "\x1b[93m"     // Yellow
        };

        // Regex to capture JSON tokens:
        // Group 1: Keys ("key": )
        // Group 2: String values ("value")
        // Group 3: Booleans/Null
        // Group 4: Numbers
        const tokenPattern = /(".*?"\s*:)|(".*?")|\b(true|false|null)\b|(-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g;

        return jsonStr.replace(tokenPattern, (match) => {
            // Check based on content patterns
            
            // Key: Ends with ':' (ignoring whitespace) and starts with '"'
            if (/^".*":\s*$/.test(match)) {
                return `${C.KEY}${match}${C.RESET}`;
            }

            // String value: Starts with '"'
            if (match.startsWith('"')) {
                return `${C.STRING}${match}${C.RESET}`;
            }

            // Boolean
            if (match === "true" || match === "false") {
                return `${C.BOOL}${match}${C.RESET}`;
            }

            // Null
            if (match === "null") {
                return `${C.NULL}${match}${C.RESET}`;
            }

            // Number (Fallthrough)
            return `${C.NUMBER}${match}${C.RESET}`;
        });
    }
    
    // -----------------------------------------------------------
    // Debug / Representation
    // -----------------------------------------------------------

    /**
     * Technical debug representation.
     * Format: <Node(KIND:type) value/len=... details...>
     */
    toString(): string {
        // 1. Type Info
        let typeLabel = "UNKNOWN";
        if (this.schema) {
            const kind = this.schema.kind;
            const typeName = this.schema.typeName;

            if (this.isList) {
                const elType = this.schema.element ? (this.schema.element.typeName || "any") : "any";
                typeLabel = `LIST[${elType}]`;
            } else if (this.isRecord && typeName !== "record" && typeName !== "any") {
                typeLabel = `RECORD:${typeName}`;
            } else {
                typeLabel = `${kind}:${typeName}`;
            }
        }

        const header = `<Node(${typeLabel})`;
        const content: string[] = [];

        // 2. Content Info
        if (this.isPrimitive) {
            let v = String(this.value);
            if (typeof this.value === 'string') v = `"${v}"`;
            if (v.length > 50) v = v.substring(0, 47) + "...";
            content.push(`val=${v}`);
        } else if (this.isList) {
            content.push(`len=${this.elements.length}`);
        } else if (this.isRecord) {
            const keys = Object.keys(this.fields);
            let keysStr = "";
            if (keys.length > 3) {
                keysStr = keys.slice(0, 3).join(", ") + ", ...";
            } else {
                keysStr = keys.join(", ");
            }
            content.push(`fields=[${keysStr}]`);
        } else {
            // Fallback
            let v = String(this.value);
            if (v.length > 50) v = v.substring(0, 47) + "...";
            content.push(`val=${v}`);
        }

        // 3. Meta Indicators
        if (this.comments.length > 0) {
            content.push(`comments=${this.comments.length}`);
        }
        if (Object.keys(this.attr).length > 0) {
            content.push(`attr=[${Object.keys(this.attr).join(', ')}]`);
        }
        if (this.tags.length > 0) {
            content.push(`tags=[${this.tags.join(', ')}]`);
        }

        const detailsStr = content.length > 0 ? " " + content.join(" ") : "";
        return `${header}${detailsStr}>`;
    }


}