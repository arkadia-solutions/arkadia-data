# ARKADIA AI.DATA-FORMAT

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
> Stop wasting context window on JSON braces. `AI.DATA` is a unified, schema-first data format designed specifically for AI understanding. It offers up to **25% token savings**, faster parsing, and human-readable structure that LLMs love.

---

## 📦 Installation

Get started immediately with pip:

```bash
pip install arkadia-ai-data-format
```

## 🚀 Fast Example

**Encoding to AI.DATA:**

```bash
echo '{ "data": 2}' | aid enc - -c
# Output: <data:number>(2)

```

**Decoding back to JSON:**

```bash
echo '<data:number>(2)' | aid dec - -f json
# Output: { "data": 2 }

```

---

## ⚡ Performance & Token Savings

Why switch? Because every token counts. `AICD` (Arkadia Compressed Data) consistently outperforms standard formats in both token efficiency.

```text
BENCHMARK SUMMARY:


   JSON  █████████████████████░░░░     6921 tok   ░░░░░░░░░░░░░░░░░░░░░░░░░     0.15 ms
   AICD  ████████████████░░░░░░░░░     5416 tok   █████████████████████████     4.40 ms
   AID   ███████████████████░░░░░░     6488 tok   ████████████████████████░     4.29 ms
   TOON  █████████████████████████     8198 tok   █████████████░░░░░░░░░░░░     2.36 ms


   FORMAT     TOKENS       TIME (Total)    AVG TIME/FILE   VS JSON
   ----------------------------------------------------------------------
   AICD       5416             4.40 ms        0.37 ms    -21.7%
   AID        6488             4.29 ms        0.36 ms    -6.3%
   JSON       6921             0.15 ms        0.01 ms    +0.0%
   TOON       8198             2.36 ms        0.20 ms    +18.5%


CONCLUSION: Switching to AICD saves 1505 tokens (21.7%) compared to JSON.
```

---

## 🛠 CLI Usage

The package comes with a powerful CLI tool `aid` for encoding, decoding, and benchmarking.

```text
   Arkadia AI DATA TOOL
   --------------------------------------------------
   Unified interface for AI Data Format operations.

USAGE:
   aid <command> [flags]

COMMANDS:
   enc             [ENCODE] Convert JSON/YAML/TOON to AI.Data format
   dec             [DECODE] Parse AI.Data format back to JSON
   benchmark       [BENCHMARK] Run performance and token usage tests
   ai-benchmark    [AI] Run AI understanding tests (not implemented yet)

GLOBAL OPTIONS:
   -h, --help       Show this help message
   -v, --version    Show version info

```

---

## 📖 Syntax Specification (Current Version)

This section describes the **actual, currently implemented** syntax of AI.DATA-FORMAT.

### 1. Type Definition

A type defines a name and an ordered list of fields. Comments are allowed within the definition to assist the LLM.

```aid
User</comment/ ={(23,"A",3) #tag1 #tag2} %[{ id: 4, b: "a", c: 43}]: id:number,
b: string , c:number, >
@Users
<
 @list 
 a: number,
 b: string
>
[
  @size=5
  /example list of values/

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
* Comments (`/ ... /`) are **allowed** in the header.

### 2. Data Structures

The format supports compact positional records and explicit named records.

| Structure | Syntax | Description |
| --- | --- | --- |
| **Positional Record** | `(a,b,c)` | Must follow the exact order of fields in the type header. |
| **Named Record** | `{key:value}` | Keys must match field names. No spaces allowed in keys/values. |
| **List** | `[ ... ]` | Contains positional or named records. |
| **Multiline Text** | ``text`` | Ends with a line containing only a backtick. |

### 3. Comments

```aid
/ this is a comment /

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

```aid
@User<id:number name:string desc:string>

value:@User(2,"Alice","Hello")
value2:@User(3,"Bob","World")

```

### 6. Nested Types

Currently, nested types are allowed as structural definitions:

```aid
@User<
  id:string
  name:string
  profile: < level:number, score:number >
>
[
  ("u1","Aga",{level:5,score:82})
  ("u2","Marek",{level:7,score:91})
]

```

---

## 🔮 Futures / Roadmap

The following features are planned for future releases and are **not yet implemented**.

* **Modifiers:**
* `!required` - field must be included.
* `?empty` - field must not be empty.
* `=value` - default value.
* `N..M` - numeric range validation.


* **Binary Data Types:**
* Hex: `~[hex]1A0F4F~`
* Base64: `~[b64]ADFKDXKZK...~`


* **Pointers/References:**
* Reference existing objects by ID: `(1, "Alex", *User[2])`


## 📄 License

This project is licensed under the [MIT License].

---

<div align="center">
<sub>Built by <strong>Arkadia AI</strong>. Engineering the kernel of distributed intelligence.</sub>
</div>
