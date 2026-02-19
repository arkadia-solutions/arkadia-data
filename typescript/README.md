# @arkadia/data

```text
                                   ; i  :J
                               U, .j..fraaM.  nl
                            b h.obWMkkWWMMWMCdkvz,k
                         ! .mQWM:o hiMoMW v.uaXMdohbi
                        hI,MMmaIao.Wo .IMkoh FCMwqoXa
                      ,.c.aWdM. d,aToW  .    Mb!. MopfQ.L
                       jhj.xoM :k    aCu F: w MpmqMvMMI,I
                      bzMhz:W    .Mw . o lYh ai M iMa pM.j
                     hzqWWM;    M;o.WMWWMkMX f.a aa bModpo.
                     ;tMbbv   xp oJMMWWWWMMMM iv  dLMXakM:T
                       mdh        MMWWWWWWWbQLCzurjktvMor
                      ,QFw ;M,b .MWWWWWWWMWMWd  xz   M,kd X
                      qjMIo IMTW.WWWWWMWWWM.o.I   rpULaMdi.
                       .mMM  uoWWWMWWWWWWp qM,,M l M;mMbrI
                        f nm  MMW MWWjMuMj  I  o   LbMac
                              WWdMWWWW Mv a.b..aauMhMwQf
                              MoWWW,WWtjonJMWtoMdoaoMI
                              MMMM Mi    xd:Mm tMwo Cr,
                             xMMc .otqokWMMMao:oio.
                             MW    .   C..MkTIo
                            WW
                           QWM
                           WW
                          uMW
                          WW
                          MW
```

````

> **The High-Density, Token-Efficient Data Protocol for Large Language Models.**

**Arkadia Data Format (AKD)** is a schema-first protocol designed specifically to optimize communication with LLMs. By stripping away redundant syntax (like repeated JSON keys) and enforcing strict typing, AKD offers **up to 30% token savings**, faster parsing, and a metadata layer invisible to your application logic but fully accessible to AI models.

---

## ✨ Key Features

- **📉 Token Efficiency:** Reduces context window usage by replacing verbose JSON objects with dense Positional Records (Tuples).
- **🛡️ Type Safety:** Enforces types (`int`, `float`, `bool`, `string`) explicitly in the schema before data reaches the LLM.
- **🧠 Metadata Injection:** Use `#tags` and `$attributes` to pass context (e.g., source confidence, deprecation warnings) to the LLM without polluting your data structure.
- **⚡ High Performance:** Zero-dependency, lightweight parser built for high-throughput Node.js/Edge environments.

---

## 📦 Installation

```bash
npm install @arkadia/data
# or
yarn add @arkadia/data
# or
pnpm add @arkadia/data

```

---

## 🚀 Quick Start

### Basic Usage

```typescript
import { encode, decode } from '@arkadia/data';

// 1. Encode: JavaScript Object -> AKD String
const data = { id: 1, name: 'Alice', active: true };

// Default encoding (compact)
const encoded = encode(data);
console.log(encoded);
// Output: <id:number,name:string,active:bool>(1,"Alice",true)

// 2. Decode: AKD String -> JavaScript Object
const input = '<score:number>(98.5)';
const result = decode(input);

if (result.errors.length === 0) {
  console.log(result.node.value); // 98.5
} else {
  console.error('Parse errors:', result.errors);
}
```

---

## 🛠 API Reference

### `encode(data: unknown, config?: EncodeConfig): string`

Serializes a JavaScript value into an AKD string.

- `data`: The input string, number, boolean, array, or object.
- `config`:
- `compact` (boolean): Removes whitespace. Default: `true`.
- `colorize` (boolean): Adds ANSI colors for terminal output. Default: `false`.
- `escapeNewLines` (boolean): Escapes `\n` in strings. Default: `false`.

### `decode(text: string, config?: DecodeConfig): DecodeResult`

Parses an AKD string into a structured node tree.

- `text`: The raw AKD string.
- `config`:
- `debug` (boolean): Enables internal logging.

- **Returns** `DecodeResult`:
- `node`: The Root Node (contains `.value`, `.dict()`, `.json()`).
- `errors`: Array of parsing errors.

---

## ⚡ Benchmarks

Why switch? Because every token counts. **AKCD** (Arkadia Compressed Data) consistently outperforms standard formats.

```text
BENCHMARK SUMMARY:

   JSON  █████████████████████░░░░     6921 tok     0.15 ms
   AKCD  ████████████████░░░░░░░░░     5416 tok     4.40 ms
   AKD   ███████████████████░░░░░░     6488 tok     4.29 ms
   TOON  █████████████████████████     8198 tok     2.36 ms

   FORMAT     TOKENS       VS JSON
   ---------------------------------
   AKCD       5416         -21.7%
   AKD        6488         -6.3%
   JSON       6921         +0.0%
   TOON       8198         +18.5%

CONCLUSION: Switching to AKCD saves 1505 tokens (21.7%) compared to JSON.

```

---

## 📖 Syntax Specification

AKD separates structure (Schema) from content (Data).

### 1. Primitives

Primitive values are automatically typed. Strings are quoted, numbers and booleans are bare.

| Type        | Input     | Encoded Output    |
| ----------- | --------- | ----------------- |
| **Integer** | `123`     | `<number>123`     |
| **String**  | `"hello"` | `<string>"hello"` |
| **Boolean** | `true`    | `<bool>true`      |
| **Null**    | `null`    | `<null>null`      |

### 2. Schema Definition (`@Type`)

Define the structure once to avoid repeating keys.

```akd
/* Define a User type */
@User <
  id: number,
  name: string,
  role: string
>

```

### 3. Data Structures

#### Positional Records (Tuples)

The most efficient way to represent objects. Values must match the schema order.

```akd
/* Schema: <x:number, y:number> */
(10, 20)

```

#### Named Records (Objects)

Flexible key-value pairs, similar to JSON, used when schema is loose or data is sparse.

```akd
{
  id: 1,
  name: "Admin"
}

```

#### Lists

Dense arrays. Can be homogenous (list of strings) or mixed.

```akd
[ "active", "pending", "closed" ]

```

### 4. Metadata System

AKD allows you to inject metadata that is **visible to the LLM** but **ignored by the parser** when decoding back to your application.

#### Attributes (`$key=value`) & Tags (`#flag`)

```akd
@Product <
  $version="2.0"
  sku: string,

  /* Tagging a field as deprecated */
  #deprecated
  legacy_id: int
>

```

---

## 📄 License

This project is licensed under the [MIT License]().

<div align="center">
<sub>Built by <strong>Arkadia Solutions</strong>. Engineering the kernel of distributed intelligence.</sub>
</div>
````
