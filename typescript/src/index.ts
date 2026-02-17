import { DEFAULT_CONFIG, EncoderConfig } from './config';
import { Decoder, DecodeResult } from './core/Decoder';
import { Encoder } from './core/Encoder';
import { parseDataToNode } from './core/Parser';
import { Meta, MetaInfo, MetaProps } from './models/Meta';
import { Node } from './models/Node';
import { Schema, SchemaKind } from './models/Schema';

// Re-export types and classes
export { DecodeResult, EncoderConfig, Meta, MetaInfo, MetaProps, Node, Schema, SchemaKind };

// =============================================================
// PUBLIC API
// =============================================================

/**
 * Encode input data into valid **AK Data** format.
 */
export function encode(data: Node | unknown, config: Partial<EncoderConfig> = {}): string {
  const node = parseDataToNode(data);
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
  schema: string = '',
): DecodeResult {
  const { removeAnsiColors = false, debug = false } = options;
  const decoder = new Decoder(text, schema, removeAnsiColors, debug);
  return decoder.decode();
}

/**
 * Convert raw JavaScript object/value into a Node.
 */
export function parse(data: unknown): Node {
  return parseDataToNode(data);
}
