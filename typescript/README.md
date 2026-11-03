# @arkadia/data — AK-DATA (Arkadia Data Format) for TypeScript / JavaScript

**Lossless, schema-first data for LLMs and agents.** AK-DATA writes JSON
data with a header that names each field once and records that follow it by
position — about **55% fewer tokens than JSON** and **14% fewer than TOON**
on typical agent payloads, decoding back to the exact original. Same output
as the Python package `arkadia-data`; zero dependencies; Node, Deno, Bun,
edge and browsers.

```bash
npm install @arkadia/data
```

This package is a library. The `ak-data` command line tool is the Rust
crate `arkadia-data` (`brew install arkadia-solutions/tap/ak-data` or
`cargo install arkadia-data`) and writes exactly the same text.

## Library

```ts
import { encode, decode } from '@arkadia/data';

const data = {
  users: [
    { id: 1, name: 'Ada' },
    { id: 2, name: 'Alan' },
  ],
};

const text = encode(data, { compact: true }); // <users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])
const { node, errors } = decode(text);
node.dict(); // deep-equals data

encode(data); // readable form
encode(data, { promptOutput: true }); // structural template for model output
```

Shortcuts and prompt helpers:

````ts
import {
  dumps,
  loads,
  loadsAny,
  toPrompt,
  buildPrompt,
  estimateTokens,
  FORMAT_DEFINITION,
} from '@arkadia/data';

dumps(data); // compact; dumps(data, { indent: 2 }) readable
loads(text); // throws AKDataError on invalid input
loadsAny(modelReply); // JSON or AK-DATA, with or without ``` fences
toPrompt(data); // one-line hint + <data>…</data>
buildPrompt(data, 'Which user is newest?', 'ak-data-compact', {
  answer: {
    name: 'result',
    fields: [
      ['id', 'number'],
      ['name', 'string'],
    ],
  },
}); // full copy-paste prompt with the format definition
estimateTokens(text); // o200k-style estimate, no download
````

### MCP tool results

```ts
return {
  structuredContent: result, // JSON for programs
  content: [{ type: 'text', text: encode(result, { compact: true }) }], // what the model reads
};
```

## Changes and history

```ts
import { diff } from '@arkadia/data';

const changes = diff.diff(before, after); // [{ op: 'change', path: 'users[id=2].name', old: 'Alan', new: 'Alan T.' }]
diff.apply(before, changes); // deep-equals after; throws ConflictError when a change does not fit
const text = diff.commit(oldText, after, { title: 'Rename Alan', author: 'Ada' }); // data + history
diff.history(text); // [{ id, date, author, title, description, changes }]
```

The history is metadata: `loads(text)` still returns exactly the data.

MIT © Arkadia Solutions · https://arkadia.solutions/akdata · [changelog](https://github.com/arkadia-solutions/arkadia-data/blob/main/CHANGELOG.md)
