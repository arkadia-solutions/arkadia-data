# @arkadia/ai-data-format

```
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


[![npm version](https://img.shields.io/npm/v/@arkadia/ai-data-format.svg)](https://www.npmjs.com/package/@arkadia/ai-data-format)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Official Parser and Stringifier for the Arkadia AI Data Format (AID).**

AID is a schema-first, high-density data protocol designed specifically for **LLM context optimization**. It significantly reduces token usage compared to JSON by eliminating redundant syntax characters and enforcing strict typing via schemas.

## ✨ Features

- **Token Efficient:** Reduces context window usage by 15-30% compared to standard JSON.
- **Type Safe:** Enforces types (int, float, bool, string) explicitly in the schema.
- **Dual Mode:** Supports both **Named Records** (Map-like) and **Positional Records** (Tuple-like).
- **Zero-Dependency:** Lightweight and fast, built for high-performance pipelines.

## 📦 Installation

```bash
npm install @arkadia/ai-data-format

```

## 🚀 Usage

### Importing

```typescript
import { encode, decode } from '@arkadia/ai-data-format';

```

### Encoding (JavaScript Object → AID String)

Converts standard JavaScript objects into the token-optimized AID string format.

```typescript
const data = {
  id: 1,
  name: "Alice",
  active: true
};

// Compact encoding (default)
const aidString = encode(data);

console.log(aidString);
// Output: <id:number,name:string,active:bool>(1,"Alice",true)

```

### Decoding (AID String → AST / Value)

Parses an AID string back into a usable node structure.

```typescript
const input = '<score:number>(98.5)';

const result = decode(input);

if (result.errors.length === 0) {
  console.log(result.node.value); 
  // Output: 98.5
  
  console.log(result.node.isRecord); 
  // Output: true
} else {
  console.error("Parsing errors:", result.errors);
}

```

## 📖 Syntax Guide

The AID format uses a distinct syntax to separate schema definition from data values.

### Primitives

Primitive values are explicitly typed using angle brackets `<type>`.

| Type | Input Example | Encoded Output |
| --- | --- | --- |
| Integer | `123` | `<number>123` |
| Float | `12.34` | `<number>12.34` |
| String | `"hello"` | `<string>"hello"` |
| Boolean | `true` | `<bool>true` |
| Null | `null` | `<null>null` |

### Named Records

Similar to JSON objects, but the keys are lifted into a schema definition.

**Input:**

```json
{ "id": 1, "name": "Test" }

```

**Encoded (AID):**

```text
<id:number,name:string>(1,"Test")

```

### Positional Records (Tuples)

Data without keys, where position determines meaning.

**Input:**

```javascript
// (10, "Alice") - conceptually

```

**Encoded (AID):**

```text
<_0:number,_1:string>(10,"Alice")

```

## 🛠️ API Reference

### `encode(input: any, options?: EncodeOptions): string`

Serializes a JavaScript value into an AID string.

* `input`: The data to encode.
* `options`:
* `compact`: (boolean) Remove whitespace. Default: `true`.
* `colorize`: (boolean) Add ANSI colors for terminal output. Default: `false`.



### `decode(text: string, options?: DecodeOptions): ParseResult`

Parses an AID string.

* `text`: The AID string to parse.
* `options`:
* `debug`: (boolean) Enable detailed logging.


* **Returns** `ParseResult`:
* `node`: The parsed AST node containing value and metadata.
* `errors`: Array of parsing errors, if any.



## 📄 License

This project is licensed under the [MIT License].

---

<div align="center">
<sub>Built by <strong>Arkadia AI</strong>. Engineering the kernel of distributed intelligence.</sub>
</div>
