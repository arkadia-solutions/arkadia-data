import { EncoderConfig, DEFAULT_CONFIG } from './config';
import { Encoder } from './core/Encoder';
import { Decoder, DecodeResult } from './core/Decoder';
import { parseDataToNode } from './core/Parser';
import { Node } from './models/Node';
import { Schema, SchemaKind } from './models/Schema';
import { MetaInfo, Meta, MetaProps } from './models/Meta';

// Re-export types and classes
export { Node, Schema, SchemaKind, DecodeResult, EncoderConfig, 
    Meta, MetaInfo, MetaProps };

// =============================================================
// PUBLIC API
// =============================================================

/**
 * Encode input data into valid **AK Data** format.
 */
export function encode(data: any | Node, config: Partial<EncoderConfig> = {}): string {
    let node: Node;
    node = parseDataToNode(data);
    const finalConfig: EncoderConfig = { ...DEFAULT_CONFIG, ...config };
    const encoder = new Encoder(finalConfig);
    return encoder.encode(node);
}

/**
 * Decode AK Data format text into a Node structure.
 */
export function decode(
    text: string,
    options: { removeAnsiColors?: boolean; debug?: boolean } = {},
    schema: string = ""
): DecodeResult {
    const { removeAnsiColors = false, debug = false } = options;
    const decoder = new Decoder(text, schema, removeAnsiColors, debug);
    return decoder.decode();
}

/**
 * Convert raw JavaScript object/value into a Node.
 */
export function parse(data: any): Node {
    return parseDataToNode(data);
}