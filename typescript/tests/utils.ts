import { expect } from 'vitest';
import { Node } from '../src/models/Node';
// Zakładam, że masz te funkcje wyeksportowane z index.ts (szczegóły niżej)
import { parseDataToNode } from '../src/core/Parser';
import { decode, encode } from '../src/index';

/**
 * Validates encoding consistency (Round-Trip):
 * 1. If source is text -> decode it to a Node.
 * 2. Encode Node -> check if it matches expectedOutput.
 * 3. Decode the result (encoded_txt) -> check if it remains a valid Node.
 * 4. Re-encode -> check if the result is stable (idempotent).
 * * Returns the Node so that further logical assertions (field checking) can be performed.
 */
export function assertRoundtrip(
  source: string | Node | unknown,
  expectedOutput: string,
  debug: boolean = false,
): Node {
  let node: Node;

  // 1. Prepare Node (if input is raw text)
  if (typeof source === 'string') {
    // Przekazujemy debug do decodera
    const res = decode(source, { debug });

    if (res.errors.length > 0) {
      console.error('Input decoding errors:', res.errors);
    }
    expect(res.errors, `Input decoding errors: ${res.errors.join(', ')}`).toHaveLength(0);
    node = res.node;
  } else if (!(source instanceof Node)) {
    node = parseDataToNode(source);
  } else {
    node = source;
  }

  // 2. First Encoding
  // Wymuszamy compact: true zgodnie z pythonowym oryginałem
  const encoded1 = encode(node, { compact: true });

  // Debug print to visualize differences in case of failure
  // (Vitest zrobi to automatycznie przy .toBe, ale zachowujemy logikę z Python)
  if (encoded1 !== expectedOutput) {
    console.log(`\n[ROUNDTRIP] Mismatch Pass 1:`);
    console.log(`EXPECTED: "${expectedOutput}"`);
    console.log(`ACTUAL:   "${encoded1}"`);
  }

  expect(encoded1).toBe(expectedOutput);

  // 3. Round Trip (Decode the result of the encoding)
  const res2 = decode(encoded1, { debug });

  if (res2.errors.length > 0) {
    console.error('Re-decoding errors:', res2.errors);
  }
  expect(res2.errors, `Re-decoding errors: ${res2.errors.join(', ')}`).toHaveLength(0);

  // 4. Second Encoding (Idempotency Check)
  const encoded2 = encode(res2.node, { compact: true });

  if (encoded2 !== expectedOutput) {
    console.log(`\n[ROUNDTRIP] Mismatch Pass 2 (Consistency):`);
    console.log(`EXPECTED: "${expectedOutput}"`);
    console.log(`ACTUAL:   "${encoded2}"`);
  }

  expect(encoded2).toBe(expectedOutput);

  return node;
}
