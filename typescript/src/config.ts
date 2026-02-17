/**
 * Configuration options for the AK Data Format Encoder.
 */
export interface EncoderConfig {
    /**
     * Embed schema directly inside sample data (useful for LLM prompting).
     * Example: [ (name: string /name of user/, age: int) ]
     * Default: false
     */
    promptOutput: boolean;

    /**
     * Number of spaces used for indentation.
     * Default: 2
     */
    indent: number;

    /**
     * Initial indentation offset (level).
     * Default: 0
     */
    startIndent: number;

    /**
     * Enable compact formatting. Removes unnecessary spaces and newlines.
     * Default: false
     */
    compact: boolean;

    /**
     * Escape newline characters in strings as literal \n and \r.
     * Default: false
     */
    escapeNewLines: boolean;

    /**
     * purely removes new lines from strings.
     * Default: false
     */
    removeNewLines: boolean;

    /**
     * Enable ANSI colorized output for terminal debugging.
     * Default: false
     */
    colorize: boolean;

    /**
     * Include comments in the output ).
     * Default: true
     */
    includeComments: boolean;

    /**
     * Include array size information (e.g. [ $size=5 : ... ]).
     * Default: false
     */
    includeArraySize: boolean;

    /**
     * Include the schema definition header (e.g. <name: string>).
     * Default: true
     */
    includeSchema: boolean;

    /**
     * Include metadata attributes and tags ($attr=1 #tag).
     * Default: true
     */
    includeMeta: boolean;

    /**
     * Include type signature after field names (e.g. name: string vs name).
     * Default: true
     */
    includeType: boolean;
}

/**
 * Default configuration values.
 */
export const DEFAULT_CONFIG: EncoderConfig = {
    indent: 2,
    startIndent: 0,
    compact: false,
    escapeNewLines: false,
    removeNewLines: false,
    colorize: false,
    includeComments: true,
    includeArraySize: false,
    includeSchema: true,
    includeMeta: true,
    includeType: true,
    promptOutput: false,
};

/**
 * Helper to merge partial user config with defaults.
 */
export function resolveConfig(config?: Partial<EncoderConfig>): EncoderConfig {
    return { ...DEFAULT_CONFIG, ...config };
}