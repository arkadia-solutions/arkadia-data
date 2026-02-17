
export interface MetaProps {
    comments?: string[];
    attr?: Record<string, any>;
    tags?: string[];
}

/**
 * Mixin/Base class that adds metadata storage capabilities to Node and Schema.
 */
export class Meta {
    comments: string[];
    attr: Record<string, any>;
    tags: string[];

    constructor({ comments, attr, tags }: MetaProps = {}) {
        this.comments = comments ? [...comments] : [];
        this.attr = attr ? { ...attr } : {};
        this.tags = tags ? [...tags] : [];
    }

    /**
     * Clears ALL metadata (comments, attributes, tags).
     */
    clearCommonMeta(): void {
        this.comments = [];
        this.attr = {};
        this.tags = [];
    }

    /**
     * Merges only the common fields (attributes, comments, tags)
     * from a MetaInfo object. Safe for both Node and Schema.
     */
    applyCommonMeta(info: Meta): void {
        // Append comments
        if (info.comments.length > 0) {
            this.comments.push(...info.comments);
        }

        // Merge attributes ($key=value)
        if (Object.keys(info.attr).length > 0) {
            Object.assign(this.attr, info.attr);
        }

        // Append tags
        if (info.tags.length > 0) {
            this.tags.push(...info.tags);
        }
    }
}

/**
 * A temporary container (DTO) holding parsed metadata from a / ... / block.
 * It contains BOTH Schema constraints (!required) and Node attributes ($key=val).
 */
export class MetaInfo extends Meta {
    required: boolean;

    constructor(props: MetaProps & { required?: boolean } = {}) {
        super(props);
        this.required = props.required || false;
    }

    /**
     * Merges everything from another MetaInfo object, including 'required' flag.
     */
    applyMeta(info: MetaInfo): void {
        // Apply common fields (comments, attr, tags)
        this.applyCommonMeta(info);

        // Override required meta (Schema Only)
        if (info.required) {
            this.required = true;
        }
    }

    /**
     * Allows usage checks like 'if meta.isEmpty()' to see if any metadata was collected.
     * Equivalent to Python's __bool__.
     */
    isEmpty(): boolean {
        return (
            this.comments.length === 0 &&
            Object.keys(this.attr).length === 0 &&
            this.tags.length === 0 &&
            !this.required
        );
    }

    /**
     * Debug representation mimicking the actual ADF format style.
     * Example: <MetaInfo !required #tag $key=val >
     */
    toString(): string {
        const parts: string[] = [];

        // 1. Flags
        if (this.required) {
            parts.push("!required");
        }

        // 2. Tags
        for (const t of this.tags) {
            parts.push(`#${t}`);
        }

        // 3. Attributes
        for (const [k, v] of Object.entries(this.attr)) {
            // Simplistic value repr for debug
            let valStr: string;
            if (typeof v === 'string') {
                valStr = `"${v}"`;
            } else {
                valStr = String(v);
            }
            parts.push(`$${k}=${valStr}`);
        }

        // 4. Comments (Summary)
        if (this.comments.length > 0) {
            if (this.comments.length === 1) {
                const c = this.comments[0];
                const preview = c.length > 15 ? c.substring(0, 15) + '..' : c;
                parts.push(`/* ${preview} */`);
            } else {
                parts.push(`/* ${this.comments.length} comments */`);
            }
        }

        const content = parts.join(" ");
        return content ? `<MetaInfo ${content}>` : "<MetaInfo (empty)>";
    }

}