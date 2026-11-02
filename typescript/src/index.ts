import type { EncoderConfig } from './config';
import { DEFAULT_CONFIG } from './config';
import type { DecodeResult } from './core/Decoder';
import { Decoder } from './core/Decoder';
import { Encoder } from './core/Encoder';
import { parseDataToNode } from './core/Parser';
import type { MetaProps } from './models/Meta';
import { Meta, MetaInfo } from './models/Meta';
import { Node } from './models/Node';
import { Schema, SchemaKind } from './models/Schema';

export type { DecodeResult, EncoderConfig, MetaProps };
// Re-export classes, and types as type-only (safe for isolatedModules bundlers)
export { Meta, MetaInfo, Node, Schema, SchemaKind };

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

// =============================================================
// JSON-LIKE API (ak-data 0.2)
// =============================================================

/** One-line description of AK-Data for system prompts (~95 tokens). */
export const HINT =
  'Data is in AK-Data format: <field:type,...> is a header; (v1,v2) is a ' +
  'record whose values follow the header order; {key:value} is a named ' +
  'record; [..] is a list; <[...]> describes every record in the list; ' +
  '<type> before a value overrides its type; a record with fewer values has ' +
  'only the first fields; //$size=N// is the number of items in a list.';

export class AKDataError extends Error {
  readonly errors: unknown[];
  constructor(errors: unknown[]) {
    super(`Invalid AK-Data (${errors.length} error(s)): ${String(errors[0] ?? 'unknown error')}`);
    this.name = 'AKDataError';
    this.errors = errors;
  }
}

export interface DumpsOptions {
  /** undefined = compact single line (best for prompts); a number = readable form. */
  indent?: number;
  /** Primitive types in headers (default true). */
  types?: boolean;
  comments?: boolean;
  colorize?: boolean;
  /**
   * Write the number of elements of every list with at least this many elements
   * as metadata ([//$size=90// …]), so a model does not have to count them.
   */
  sizes?: number;
}

/**
 * Serialize a value to AK-Data, like JSON.stringify.
 *   dumps({ users: [{ id: 1, name: 'Ada' }, { id: 2, name: 'Alan' }] })
 *   // <users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])
 */
export function dumps(data: unknown, options: DumpsOptions = {}): string {
  const compact = options.indent === undefined;
  return encode(data, {
    compact,
    escapeNewLines: compact,
    indent: options.indent ?? 2,
    includeType: options.types ?? true,
    includeComments: options.comments ?? true,
    colorize: options.colorize ?? false,
    includeArraySize: options.sizes !== undefined,
    arraySizeMin: options.sizes ?? 1,
  });
}

/** Parse AK-Data text into plain values, like JSON.parse. Throws AKDataError. */
export function loads(text: string, options: { strict?: boolean } = {}): unknown {
  const result = decode(text, { removeAnsiColors: true });
  if (result.errors.length && options.strict !== false) throw new AKDataError(result.errors);
  return result.node.dict();
}

/** Parse model output that may be JSON or AK-Data (code fences allowed). */
export function loadsAny(text: string): unknown {
  let body = text.trim();
  if (body.startsWith('```')) {
    body = body.slice(body.indexOf('\n') + 1);
    body = body.slice(0, body.lastIndexOf('```')).trim();
  }
  try {
    return JSON.parse(body);
  } catch {
    return loads(body);
  }
}

/** A ready-to-paste block for a system prompt or a tool result. */
export function toPrompt(
  data: unknown,
  options: { hint?: boolean; compact?: boolean; label?: string } = {},
): string {
  const { hint = true, compact = true, label = 'data' } = options;
  const body = encode(data, { compact, escapeNewLines: compact });
  return `${hint ? `${HINT}\n` : ''}<${label}>\n${body}\n</${label}>`;
}

/** diff / merge / apply / history: `diff.diff(a, b)`, `diff.apply(a, changes)`, `diff.commit(text, data, info)`. */
export * as diff from './diff';
export { compact, pretty, stripMeta } from './layout';
export type { AnswerShape, PromptFormat, PromptOptions } from './prompt';
export {
  buildPrompt,
  encodeAs,
  FORMAT_DEFINITION,
  FORMAT_NAMES,
  normalizeFormat,
  TOON_DEFINITION,
} from './prompt';
export { estimateTokens } from './tokens';
