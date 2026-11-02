/**
 * Copy-paste prompts: data + format definition + question + answer format,
 * for ChatGPT, Gemini, Claude or any chat model. Same text as the Python
 * package (arkadia.bench.prompts), so prompts are identical across languages.
 */
import { DEFAULT_CONFIG, type EncoderConfig } from './config';
import { Encoder } from './core/Encoder';
import { parseDataToNode } from './core/Parser';
import { pretty } from './layout';

function encode(data: unknown, config: Partial<EncoderConfig>): string {
  return new Encoder({ ...DEFAULT_CONFIG, ...config }).encode(parseDataToNode(data));
}

export const FORMAT_DEFINITION =
  'AK-DATA (Arkadia Data Format): <a:type,b:type> is a header; (v1,v2) is a record whose values follow the header order.\n' +
  '<[a:type,...]>[(...),(...)] is a list of records sharing that header; headers nest, e.g. items:<[sku:string,qty:number]>.\n' +
  '{key:value} is a record with names; <type> or <any> before a value overrides the header type.\n' +
  'Strings are quoted; numbers, true, false, null as in JSON; /*...*/, $attr, #tag are metadata, not data.\n' +
  'A record with fewer values than its header has only the first fields; //$size=N// before list items is their count.';

export const TOON_DEFINITION =
  'TOON (Token-Oriented Object Notation) — how to read it:\n' +
  '- Indentation shows nesting; "key: value" is a field.\n' +
  '- key[N]{f1,f2,...}: is followed by N rows of comma-separated values in field order.\n' +
  '- key[N]: a,b,c is a list of N values; "- " starts an item of a list of objects.';

export type PromptFormat = 'json' | 'json-min' | 'toon' | 'akd' | 'akcd';

export const FORMAT_NAMES: Record<PromptFormat, string> = {
  json: 'JSON',
  'json-min': 'JSON (minified)',
  toon: 'TOON',
  akd: 'AK-DATA',
  akcd: 'AK-DATA COMPACT',
};

const ALIASES: Record<string, PromptFormat> = {
  json: 'json',
  'json-min': 'json-min',
  toon: 'toon',
  akd: 'akd',
  'ak-data': 'akd',
  akdata: 'akd',
  akcd: 'akcd',
  'ak-data-compact': 'akcd',
  compact: 'akcd',
};

/** Accepts json, toon, ak-data, ak-data-compact (any case, spaces or underscores). */
export function normalizeFormat(name: string): PromptFormat {
  const key =
    ALIASES[
      name
        .trim()
        .toLowerCase()
        .replace(/[_\s]+/g, '-')
    ];
  if (!key)
    throw new Error(`Unknown format '${name}'. Use one of: json, toon, ak-data, ak-data-compact`);
  return key;
}

/** Answer shape: list name and [field, type] pairs. */
export interface AnswerShape {
  name: string;
  fields: [string, string][];
}

export interface PromptOptions {
  answer?: AnswerShape;
  definition?: boolean;
  /** TOON encoder (e.g. `encode` from @toon-format/toon); required for format 'toon'. */
  toonEncode?: (data: unknown) => string;
}

export function encodeAs(
  data: unknown,
  format: PromptFormat,
  toonEncode?: (d: unknown) => string,
): string {
  switch (format) {
    case 'json':
      return JSON.stringify(data, null, 2);
    case 'json-min':
      return JSON.stringify(data);
    case 'akd':
      return encode(data, { compact: false });
    case 'akcd':
      return encode(data, { compact: true, escapeNewLines: true });
    case 'toon':
      if (!toonEncode)
        throw new Error(
          "TOON needs the optional package '@toon-format/toon' (npm i @toon-format/toon)",
        );
      return toonEncode(data);
  }
}

function answerInstruction(format: PromptFormat, answer: AnswerShape): string {
  const { name, fields } = answer;
  if (format === 'akd' || format === 'akcd') {
    const header = `<${name}:<[${fields.map(([f, t]) => `${f}:${t}`).join(',')}]>>`;
    return (
      'Answer in AK-DATA only (no prose, no code fences), with exactly this ' +
      `header and one record per item:\n${header}`
    );
  }
  if (format === 'toon') {
    const cols = fields.map(([f]) => f).join(',');
    return `Answer in TOON only (no prose, no code fences): ${name}[N]{${cols}}: followed by one row per item.`;
  }
  const shape = fields.map(([f, t]) => `"${f}": <${t}>`).join(', ');
  return `Answer with JSON only (no prose): {"${name}": [{${shape}}, ...]}`;
}

/** The full prompt text: intro, format definition, data, question, answer format. */
export function buildPrompt(
  data: unknown,
  question: string,
  format: string = 'akcd',
  options: PromptOptions = {},
): string {
  const fmt = normalizeFormat(format);
  // Readable AK-DATA is laid out to 80 columns (same as Python and Rust).
  const payload =
    fmt === 'akd'
      ? pretty(encodeAs(data, 'akcd'), 80)
      : encodeAs(data, fmt, options.toonEncode).replace(/\n+$/, '');
  const intro: Partial<Record<PromptFormat, string>> = {
    akd: 'AK-DATA',
    akcd: 'AK-DATA (compact, single-line form)',
  };
  const parts = [`The data below is in ${intro[fmt] ?? FORMAT_NAMES[fmt]}.`];
  const withDefinition = options.definition !== false;
  if (withDefinition && (fmt === 'akd' || fmt === 'akcd')) parts.push(FORMAT_DEFINITION);
  else if (withDefinition && fmt === 'toon') parts.push(TOON_DEFINITION);
  parts.push(`<data>\n${payload}\n</data>`);
  parts.push(`Question: ${question}`);
  if (options.answer) parts.push(answerInstruction(fmt, options.answer));
  return `${parts.join('\n\n')}\n`;
}
