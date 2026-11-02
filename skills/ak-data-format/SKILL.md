---
name: ak-data-format
description: Read and write AK-DATA (Arkadia Data Format) correctly — the schema-first, positional, lossless JSON format for LLM context. Use whenever input contains AK-DATA (a `<field:type,...>` header followed by `(...)` records, `<[...]>[...]` lists, `@Type`, `<any> {...}`), when asked to answer "in AK-DATA" or to fill a given header, when converting JSON to AK-DATA or back by hand, when checking or fixing AK-DATA text, or when a compact, typed, structured output is wanted instead of JSON. Needs no installation.
---

# AK-DATA: read and write it exactly

AK-DATA carries exactly the information of JSON. A **header** `<…>` names
every field once, with its type; the **data** after it lists only values, by
position. Decoding always gives back the original JSON, so every character
matters: a value in the wrong position is a value in the wrong field.

```akd
<users:<[id:number,name:string,active:bool]>>([(1,"Ada",true),(2,"Alan",false)])
```
```json
{"users":[{"id":1,"name":"Ada","active":true},{"id":2,"name":"Alan","active":false}]}
```

`<users:…>` — the root is a record with one field `users`; `<[…]>` — that
field is a list whose every element is a record `(id, name, active)`.

Full reference with every rule decoded: [reference/spec.md](reference/spec.md).
Fourteen worked examples (AK-DATA ↔ JSON, with questions and answers):
[reference/examples.md](reference/examples.md).

## 1. Syntax

| Write | Meaning |
|---|---|
| `<a:type,b:type>` | header of a record: field `a` is position 0, `b` position 1 |
| `(v1,v2)` | positional record — values in header order |
| `<[a:type,…]>` | header of a list whose every element is that record |
| `[v1,v2]` | list |
| `{key:value,…}` | named record (keys written out; no header needed) |
| `f:<x:number,y:number>` | field holding a nested record |
| `f:<[sku:string,qty:number]>` | field holding a list of records |
| `f:[string]` / `f:[[number]]` | list of values / list of lists |
| `f` (no type) | field of type `any` |
| `<type> value` | value whose type differs from its header: `<string> "12"` |
| `<any> {…}` / `<any> […]` | value whose shape differs from its header |
| `<null> null` | absent nested record (plain `null` also works) |
| `` `user id` `` | name that is not an identifier (spaces, symbols, leading digit) |
| `@User<id:number>` then `lead:@User`, `[@User]`, `@User(1)` | named type: declared once, reused |
| `/* … */` `$key=value` `$required` `#tag` `// … //` | metadata for the reader — skipped by the decoder |
| `[//$size=90// (…),(…)…]` | metadata: the list has 90 items (no need to count) |

Types: `string`, `number` (aliases `int`, `float`), `bool`, `null`, `any`,
`binary` (a string). Values: strings always in double quotes with `\"` `\\`
`\n` `\t` `\r` escapes; numbers as in JSON (`-2.5e-3`, `199.0` stays a
float); `true`, `false`, `null`. Whitespace between tokens means nothing.

A document: `[metadata] [@Type<…> declarations] [<root header>] value`.

## 2. Reading — the procedure

1. **Skip metadata**: `/* … */` (nestable), `// … //` blocks, `$attr=value`,
   `$required`, `#tag` are not data.
2. **Collect named types**: `@Name<…>` declares a header; later `@Name` means
   that header.
3. **Read the root header** `<…>`; it describes the value right after it.
4. **Map positions to names at every level**: inside `( … )` the n-th value
   belongs to the n-th field of the header that applies here. For a field
   `f:<…>` the value is a nested `( … )`; for `f:<[…]>` it is `[ ( … ), … ]`
   and every element uses the same inner header.
5. **Overrides win**: `<type> v` gives `v` that type; `<any> {k:v}` is a
   record with its own keys (it does not use the header); an inline header
   `<a:number>(1)` describes just that value.
6. **Edge cases**: fewer values than fields → the missing trailing fields are
   absent (not null) — encoders use this for optional fields: under
   `<[id,name,email]>` the record `(2,"Alan")` has no `email`; more values →
   extra fields `_1`, `_2`…; a record with
   no header → fields `_0`, `_1`…; a `{key:value}` record after a header
   matches keys by name; an unquoted word in data is read as a string.

Nested example — read it field by field:

```akd
<orders:<[id:string,customer:<id:number,name:string>,items:<[sku:string,qty:number]>,total:number]>>([("A1",(7,"Ada"),[("KB-01",2),("MS-02",1)],178.0),("A2",(9,"Alan"),[],0)])
```
```json
{"orders":[{"id":"A1","customer":{"id":7,"name":"Ada"},"items":[{"sku":"KB-01","qty":2},{"sku":"MS-02","qty":1}],"total":178.0},{"id":"A2","customer":{"id":9,"name":"Alan"},"items":[],"total":0}]}
```

When answering a question about AK-DATA data, count records and look up
values by position carefully; when unsure which field a value is, count the
commas at that nesting level against the header. A list that starts with
`//$size=N//` has exactly N items — use that number instead of counting.

## 3. Writing — the procedure

**Step 1. Fix the header before any value.**
- A header was given ("with exactly this header") → copy it character for
  character, including the answer name and field order.
- Otherwise build it from the data you will write:
  - list of objects → `<name:<[f1:type,f2:type,…]>>` (root list: `<[…]>`)
  - one object → `<f1:type,f2:type,…>`
  - nested object field → `f:<…>`; list of objects → `f:<[…]>`;
    list of values → `f:[type]`; list of lists → `f:[[type]]`
  - type per field from its values: text `string`, numbers `number`,
    `true/false` `bool`; a field that is only ever `null` → `null`
    (or `any`); mixed or unknown → `any`
  - names that are not identifiers → backticks: `` `e-mail`:string ``

**Step 2. One record per item, values in header order.**
`[(…),(…)]` for lists, `(…)` for one record; nested records `( … )` and
lists `[ … ]` exactly where the header has them.

**Step 3. Values.**
- Quote every string (`"Kraków"`); escape `"` and `\`; newline as `\n`.
- Numbers bare and plain: `1234.5` — never `"1 234,5 zł"`, `1,234`, `12%`,
  `$5`. Units go into the field name (`price_eur`), not the value.
- Unknown or missing value → `null` in its position (keeps the positions).
- Empty list → `[]`; empty string → `""`.

**Step 4. Irregular items** (only when needed — they cost tokens):
- one value of another type → `<type> value`, e.g. `<string> "n/a"` in a
  number column;
- an item with other fields → `<any> {key:value,…}` inside the list;
- truly heterogeneous list → `<[any]>[{…},{…}]` (named records).

**Step 5. Metadata where the meaning is not obvious** (optional). Decoders
ignore comments and attributes, models read them. When a value cannot be
understood from the data alone — a status code, a unit, a test record —
add it: `st:number /* 1 new, 2 paid, 4 refunded */`, `amt:number $unit="EUR cents"`,
`(…) #test`. For a long list another model will read, `//$size=N//` right
after `[` saves it counting (`ak-data read data.json -c --sizes=10`). Do not add metadata
when you were given a header to fill exactly.

**Step 6. Check before sending** (see §5).

### Output form

- "AK-DATA only" / "no prose" → output the AK-DATA text alone: no
  introduction, no explanation, no code fence.
- Otherwise put it in a fenced block tagged `akd`.
- Compact (one line, `,` without spaces) when tokens matter — the default for
  answers; readable (spaces, one record per line) when a person reads it.
  Both decode identically.
- Never switch to JSON halfway, never add keys inside positional records,
  never wrap the answer in an extra object the header does not declare.

## 4. Worked answers

Question: *"Top 2 departments by average salary"* with the header
`<result:<[department:string,employees:number,avg_salary:number]>>`:

```akd
<result:<[department:string,employees:number,avg_salary:number]>>([("Research",4,132500),("Engineering",6,118250)])
```

A single object:

```akd
<service:string,status:string,errors:number,healthy:bool>("billing","degraded",7,false)
```

Nested record and list, with an unknown value:

```akd
<customer:<id:number,name:string,email:string>,orders:<[id:string,items:[string],total:number]>>((7,"Ada",null),[("A1",["Keyboard","Mouse"],128.5),("A2",[],0)])
```

An item that does not fit (extra field) — named record with `<any>`:

```akd
<[name:string,tools:[string]]>[("planner",["search","files"]),<any> {name:"writer",tools:["files"],temperature:0.4}]
```

Type override in a typed column:

```akd
<[sku:string,stock:number]>[("KB-01",14),("HD-10",<string> "on order"),(<number> 3001,120)]
```

Names with spaces, empty result:

```akd
<no_2fa:<[`user id`:number,`e-mail`:string]>>([])
```

Readable form of the same kind of data (line breaks are free):

```akd
<users:<[id:number, name:string, active:bool]>>
([
  (1, "Ada", true),
  (2, "Alan", false)
])
```

## 5. Checklist and common mistakes

Before sending, check every point:

1. The header comes first and is exactly the requested one (name, fields,
   order, types).
2. Every `( … )` has exactly as many values as its header has fields — count
   them in each record, at each nesting level.
3. Brackets balance: `<` `>` only in headers and overrides; `( )` records;
   `[ ]` lists; `{ }` named records.
4. Every string is in double quotes; numbers have no quotes, units or
   separators; booleans are `true`/`false`; missing is `null`.
5. Nothing outside the AK-DATA when "only" was asked.

| ✗ wrong | ✓ right | why |
|---|---|---|
| `<result:[a:string]>` | `<result:<[a:string]>>` | a list of records is `<[…]>` inside the field |
| `<[a:string,n:number]>[(Ada,3)]` | `[("Ada",3)]` | strings are quoted |
| `("Ada","1 234 zł")` | `("Ada",1234)` | plain numbers |
| `[(1),(2,"Alan")]` for `<[id,name]>` | `[(1,null),(2,"Alan")]` | keep positions with `null` |
| `[{name:"Ada",total:3}]` after a header | `[("Ada",3)]` | with a header, records are positional |
| `<"user id":number>` | `` <`user id`:number> `` | names use backticks, not quotes |
| `{"result":[…]}` | `<result:<[…]>>([…])` | do not fall back to JSON |
| ```` ```json ```` + AK-DATA | AK-DATA alone | no fences when "only" is asked |
| `<result:<[a:number]>>[(1)]` | `<result:<[a:number]>>([(1)])` | the root is a record `( … )` holding the list |

The last one is the most frequent error: with a named root field
(`<result:…>`) the data starts with `(` — the root record — and the list
is its first value: `([ … ])`. With a root list header (`<[…]>`) the data
starts directly with `[`.

## 6. Asking another model for AK-DATA

Put the definition once (system prompt or top of the message), then the data,
the question and the header to fill:

```text
AK-DATA (Arkadia Data Format): <a:type,b:type> is a header; (v1,v2) is a record whose values follow the header order.
<[a:type,...]>[(...),(...)] is a list of records sharing that header; headers nest, e.g. items:<[sku:string,qty:number]>.
{key:value} is a record with names; <type> or <any> before a value overrides the header type.
Strings are quoted; numbers, true, false, null as in JSON; /*...*/, $attr, #tag are metadata, not data.
A record with fewer values than its header has only the first fields; //$size=N// before list items is their count.

<data>
…AK-DATA…
</data>

Question: …

Answer in AK-DATA only (no prose, no code fences), with exactly this header and one record per item:
<result:<[country:string,orders:number,revenue:number]>>
```

Parse the reply with a tolerant reader that accepts AK-DATA or JSON and strips
code fences: `akd.loads_any(reply)` (Python `arkadia.data`), `loadsAny(reply)`
(npm `@arkadia/data`), `arkadia_data::loads_any(&reply)` (Rust). Validate a
file with `ak-data read answer.akd -t json --strict`. Answers in AK-DATA are typically
40–60% fewer output tokens than the same JSON.

## 7. When to use it

- Use for repeated structure (lists of similar objects, tool results, logs,
  tables, nested business records) above a few hundred tokens that a model
  reads.
- Keep JSON for programs and APIs that expect JSON, and for one small
  irregular object (minified JSON is as small).
- Tools, if installed (`ak-data-install` skill): `ak-data read data.json -c`,
  `ak-data read data.akd -t json`, `ak-data diff old.json new.json`,
  `ak-data example --prompt`, `ak-data info`.
