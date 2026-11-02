/**
 * Token estimate without a tokenizer download.
 *
 * Pre-tokenizer style heuristic, mean error ~5% against o200k_base on JSON,
 * TOON and AK-Data text: a word with its leading space is one token plus one
 * per 7 further letters, digits come in groups of three, punctuation runs
 * cost one token per 4 characters, each whitespace run one token.
 * Same rules as the Python fallback (arkadia.data.tokens).
 */
const PIECE = / ?\p{L}+| ?\p{N}{1,3}| ?[^\s\p{L}\p{N}_]+[\r\n]*|\s+/gu;

export function estimateTokens(text: string): number {
  let total = 0;
  for (const match of text.matchAll(PIECE)) {
    const core = match[0].replace(/^ +/, '');
    if (!core || /^\s/.test(core) || /^\p{N}/u.test(core)) total += 1;
    else if (/^\p{L}/u.test(core)) total += 1 + Math.floor((core.length - 1) / 7);
    else total += Math.ceil(core.length / 4);
  }
  return total;
}
