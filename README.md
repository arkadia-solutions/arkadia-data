# ARKADIA DATA FORMAT

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

---

> **The High-Density, Token-Efficient Data Protocol for Large Language Models.**
> Stop wasting context window on JSON braces. `AK-Data` is a unified, schema-first data format designed specifically for AI understanding. It offers up to **25% token savings**, faster parsing, and human-readable structure that LLMs love.

---

## 📦 Installation

Get started immediately with pip:

```bash
pip install arkadia-data
```

## 🚀 Fast Example

**Encoding to AK-DATA:**

```bash
echo '{ "data": 2}' | akd enc - -c
# Output: <data:number>(2)

```

**Decoding back to JSON:**

```bash
echo '<data:number>(2)' | akd dec - -f json
# Output: { "data": 2 }

```

---

## ⚡ Performance & Token Savings

Why switch? Because every token counts. `AKCD` (Arkadia Compressed Data) consistently outperforms standard formats in both token efficiency.

```text
BENCHMARK SUMMARY:


   JSON  █████████████████████░░░░     6921 tok   ░░░░░░░░░░░░░░░░░░░░░░░░░     0.15 ms
   AKCD  ████████████████░░░░░░░░░     5416 tok   █████████████████████████     4.40 ms
   AKD   ███████████████████░░░░░░     6488 tok   ████████████████████████░     4.29 ms
   TOON  █████████████████████████     8198 tok   █████████████░░░░░░░░░░░░     2.36 ms


   FORMAT     TOKENS       TIME (Total)    AVG TIME/FILE   VS JSON
   ----------------------------------------------------------------------
   AKCD       5416             4.40 ms        0.37 ms    -21.7%
   AKD        6488             4.29 ms        0.36 ms    -6.3%
   JSON       6921             0.15 ms        0.01 ms    +0.0%
   TOON       8198             2.36 ms        0.20 ms    +18.5%


CONCLUSION: Switching to AKCD saves 1505 tokens (21.7%) compared to JSON.
```

---

## 🛠 CLI Usage

The package comes with a powerful CLI tool `akd` for encoding, decoding, and benchmarking.

```text
   Arkadia DATA TOOL
   --------------------------------------------------
   Unified interface for AK Data Format operations.

USAGE:
   ak-data / akd <command> [flags]

COMMANDS:
   enc             [ENCODE] Convert JSON/YAML/TOON to AK Data format
   dec             [DECODE] Parse AK Data format back to JSON
   benchmark       [BENCHMARK] Run performance and token usage tests
   ai-benchmark    [AI] Run AI understanding tests (not implemented yet)

GLOBAL OPTIONS:
   -h, --help       Show this help message
   -v, --version    Show version info

```

---

## 📖 Syntax Specification (Current Version)

This section describes the **actual, currently implemented** syntax of AK-DATA.

### 1. Type Definition

A type defines a name and an ordered list of fields. Comments are allowed within the definition to assist the LLM.

```akd
@Users
<
[ 
  a: number,
  b: string
]>
[
  // $size=5 /* example list of values */ //

  (1,`text`,5)
  (2,`Text can be

multiline
`,5)
  {
    id:3,
    b: "text"
  }
]

```

**Key Rules:**

* The type name (`@Name`) is optional but recommended.
* The header `<...>` defines field names and their order.
* Comments (`/* ... */`) are **allowed** in the header.

### 2. Data Structures

The format supports compact positional records and explicit named records.

| Structure | Syntax | Description |
| --- | --- | --- |
| **Positional Record** | `(a,b,c)` | Must follow the exact order of fields in the type header. |
| **Named Record** | `{key:value}` | Keys must match field names. No spaces allowed in keys/values. |
| **List** | `[ ... ]` | Contains positional or named records. |
| **Multiline Text** | ``text`` | Ends with a line containing only a backtick. |

### 3. Comments

```akd
/* this is a comment */

```

* Allowed **only** inside type definitions.
* Forbidden in raw data blocks to save space.

### 4. General Rules

1. **Data must contain NO spaces.** (Compactness is priority).
2. Schema/Type definitions **may** contain spaces and comments.
3. Named fields always use `key:value` without spaces.
4. Positional order must exactly match the declared order.

### 5. Inline Type Usage

You can declare a type and immediately use it:

```akd
@User<id:number name:string desc:string>

value:@User(2,"Alice","Hello")
value2:@User(3,"Bob","World")

```

### 6. Nested Types

Currently, nested types are allowed as structural definitions:

```akd
@User<
  $required id:string
  name:string
  profile: < level:number, score:number >
>
[
  ("u1","Aga",{level:5,score:82})
  ("u2","Marek",{level:7,score:91})
]

```


### 7. Escaped Identifiers (Backticks)

AK-Data allows the use of spaces, symbols, and special characters in names by wrapping them in backticks (```). This applies to schema names, field keys, and metadata attributes.

```akd
@`System User+` <
  // $`last-sync`="2024-05-10" //
  `Full Name`: string,
  `is-active?`: bool,
  $`Special ID*` id: number
>
{
  `Full Name`: "John Doe", 
  `is-active?`: true, 
  id: 101
}
```

**Rules for Backticks:**

* **Mandatory** for identifiers containing spaces, mathematical operators (`+`, `-`, `*`), or starting with digits.
* **No Escaping:** The first closing backtick strictly ends the name (no ``` support).
* **Automatic:** The encoder uses "naked" identifiers by default and only applies backticks when necessary to maintain token efficiency.

### 8. Prompt Output Mode (`--prompt-output`)

This mode is specifically designed for Large Language Models (LLMs). It transforms AK-Data into a **Structural Blueprint**, providing a perfect template for the AI to follow. Instead of raw data values, it renders a recursive, human-readable schema structure.

**Key Features:**

* **Full Structural Expansion:** Anonymous nested types are fully expanded into braces `{}`.
* **Semantic Hinting:** Field-level comments from the schema are injected directly into the template.
* **Representative Sampling:** Lists show a single blueprint element followed by a continuation hint (`...`), saving tokens while maintaining clarity.

**Example Usage:**

```bash
# Generate a structural template for an LLM
echo '<[ /* id */ id: number, name: string, val: <id: string, num: number> ]>' | akd dec -f akd --prompt-output -

```

**Output:**

```akd
[
  {
    id: number /* id */,
    name: string,
    val: {
      id: string,
      num: number
    }
  },
  ... /* repeat pattern for additional items */
]
```

**Why use it?**

1. **Reduce Hallucination:** The LLM sees exactly what types and formats are expected for every field.
2. **Context Efficiency:** By showing only one example in a list, you define the logic without wasting the context window on repetitive data.
3. **Implicit Instruction:** The transition from positional `()` to named `{}` in prompt mode helps the AI differentiate between the "Instructions" and the final "Compact Output".

## 📄 License

This project is licensed under the [MIT License].

---

<div align="center">
<sub>Built by <strong>Arkadia Solutions</strong>. Engineering the kernel of distributed intelligence.</sub>
</div>
