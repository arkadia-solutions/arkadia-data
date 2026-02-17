# Arkadia Data Format (AKD)

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

> **The High-Density, Token-Efficient Data Protocol for Large Language Models.**

**Arkadia Data Format (AKD)** is a schema-first protocol designed specifically to optimize communication with LLMs. By stripping away redundant syntax (like repeated JSON keys) and enforcing strict typing, AKD offers **up to 30% token savings**, faster parsing, and a metadata layer invisible to your application logic but fully accessible to AI models.

**This Python package includes the full core library and the `akd` CLI tool.**

---

## ✨ Key Features

* **📉 Token Efficiency:** Reduces context window usage by replacing verbose JSON objects with dense Positional Records (Tuples).
* **🛡️ Type Safety:** Enforces types (`int`, `float`, `bool`, `string`) explicitly in the schema before data reaches the LLM.
* **🧠 Metadata Injection:** Use `#tags` and `$attributes` to pass context (e.g., source confidence, deprecation warnings) to the LLM without polluting your data structure.
* **🖥️ Powerful CLI:** Includes the `akd` terminal tool for encoding, decoding, and benchmarking files or streams.
* **⚡ Zero Dependencies:** Pure Python implementation, lightweight and fast.

---

## 📦 Installation

Install directly from PyPI:

```bash
pip install arkadia-data

```

---

## 🚀 Quick Start (Library)

### Basic Usage

```python
import arkadia.data as akd

# 1. Encode: Python Dict -> AKD String
data = { "id": 1, "name": "Alice", "active": True }
encoded = akd.encode(data)

print(encoded)
# Output: <id:number,name:string,active:bool>(1,"Alice",true)


# 2. Decode: AKD String -> Python Dict
input_str = '<score:number>(98.5)'
result = akd.decode(input_str)

if not result.errors:
    print(result.node.value) # 98.5
else:
    print("Errors:", result.errors)

```

---

## 🛠 CLI Usage

The Python package installs the `akd` (alias: `ak-data`) command globally.

```text
USAGE:
   akd / ak-data <command> [flags]

COMMANDS:
   enc             [ENCODE] Convert JSON/YAML to AK Data format
   dec             [DECODE] Parse AK Data format back to JSON
   benchmark       [BENCHMARK] Run performance and token usage tests

```

### Examples

**1. Pipe JSON to AKD (Compact Mode):**

```bash
echo '{ "data": 2}' | akd enc - -c
# Output: <data:number>(2)

```

**2. Decode AKD file to JSON:**

```bash
akd dec payload.akd -f json

```

**3. Run Benchmarks on a directory:**

```bash
akd benchmark ./data_samples

```

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

| Type | Input | Encoded Output |
| --- | --- | --- |
| **Integer** | `123` | `<number>123` |
| **String** | `"hello"` | `<string>"hello"` |
| **Boolean** | `true` | `<bool>true` |
| **Null** | `null` | `<null>null` |

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

## 🔮 Roadmap

* **Binary Types:** Hex (`~[hex]1A...~`) and Base64 (`~[b64]...~`) support.
* **Pointers:** Reference existing objects by ID (`*User[1]`).
* **Ranges:** Numeric range validation in schema (`score: 0..100`).

---

## 📄 License

This project is licensed under the [MIT License]().

<div align="center">
<sub>Built by <strong>Arkadia Solutions</strong>. Engineering the kernel of distributed intelligence.</sub>
</div>
