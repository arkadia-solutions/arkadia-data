//! `ak-data info` — the complete AK-DATA definition, coloured, with every
//! example decoded live (so the shown JSON is what the decoder returns).

use akd::layout;
use arkadia_data as akd;

use crate::ui;

const WIDTH: usize = 76;

/// Sections: id, title.
pub const SECTIONS: &[(&str, &str)] = &[
    ("overview", "What AK-DATA is"),
    ("document", "Document structure"),
    ("values", "Primitive values"),
    ("header", "Headers and types"),
    ("records", "Records: positional ( ) and named { }"),
    ("lists", "Lists"),
    ("overrides", "Type and shape overrides"),
    ("named", "Named types @Type"),
    ("metadata", "Comments, attributes, tags"),
    ("encoder", "What encoders write (canonical form)"),
    ("json", "JSON ↔ AK-DATA mapping"),
    ("grammar", "Grammar (EBNF)"),
    ("writing", "Writing AK-DATA (for people and models)"),
    ("tools", "Tools and libraries"),
];

struct Doc {
    out: String,
    errors: usize,
    /// The last thing written was an indented block (example, table …).
    after_block: bool,
}

/// Splits `text` into units: words, and ``code`` spans kept whole.
fn units(text: &str) -> Vec<(bool, String)> {
    let mut out = vec![];
    for (i, part) in text.split("``").enumerate() {
        if i % 2 == 1 {
            out.push((true, part.to_string()));
        } else {
            for w in part.split_whitespace() {
                out.push((false, w.to_string()));
            }
        }
    }
    out
}

fn code(text: &str) -> String {
    if ui::enabled() {
        layout::highlight(text)
    } else {
        text.to_string()
    }
}

impl Doc {
    fn line(&mut self, s: &str) {
        self.out.push_str(s);
        self.out.push('\n');
    }

    /// A blank line before text that follows an example or a table.
    fn gap(&mut self) {
        if std::mem::take(&mut self.after_block) {
            self.line("");
        }
    }

    fn section(&mut self, n: usize, id: &str, title: &str) {
        self.line("");
        self.line(&format!(
            "{} {}  {}",
            ui::paint(&format!("{}{}", ui::BOLD, ui::GREEN), &format!("{n:>2}."),),
            ui::paint(&format!("{}{}", ui::BOLD, ui::WHITE), &title.to_uppercase()),
            ui::paint(ui::DIM, &format!("ak-data info {id}"))
        ));
        self.line(&format!(
            "    {}",
            ui::paint(ui::DIM, &"─".repeat(WIDTH - 4))
        ));
    }

    fn sub(&mut self, title: &str) {
        self.after_block = false;
        self.line("");
        self.line(&format!("    {}", ui::paint(ui::YELLOW, title)));
    }

    /// A wrapped paragraph; ``code`` spans are highlighted.
    fn p(&mut self, text: &str) {
        self.gap();
        let mut line: Vec<(bool, String)> = vec![];
        let mut len = 0;
        let mut lines = vec![];
        for u in units(text) {
            let w = u.1.chars().count();
            if !line.is_empty() && len + 1 + w > WIDTH - 4 {
                lines.push(std::mem::take(&mut line));
                len = 0;
            }
            len += w + usize::from(!line.is_empty());
            line.push(u);
        }
        if !line.is_empty() {
            lines.push(line);
        }
        for l in lines {
            let mut shown = String::new();
            for (i, (is_code, s)) in l.iter().enumerate() {
                // No space before punctuation, none after an opening bracket.
                let tight = i == 0
                    || (!is_code && s.starts_with([',', '.', ';', ':', ')']))
                    || (!l[i - 1].0 && l[i - 1].1.ends_with('('));
                if !tight {
                    shown.push(' ');
                }
                shown.push_str(&if *is_code {
                    code(s)
                } else {
                    ui::paint(ui::WHITE, s)
                });
            }
            self.line(&format!("    {shown}"));
        }
    }

    /// Bullet points.
    fn bullets(&mut self, items: &[&str]) {
        self.gap();
        for item in items {
            let before = self.out.len();
            self.p(item);
            // "    text" → "  • text" on the first line, indent the rest.
            let added = self.out.split_off(before);
            for (i, l) in added.lines().enumerate() {
                let rest = l.strip_prefix("    ").unwrap_or(l);
                if i == 0 {
                    self.line(&format!("    {} {rest}", ui::paint(ui::GREEN, "•")));
                } else {
                    self.line(&format!("      {rest}"));
                }
            }
        }
    }

    /// An AK-DATA example and the JSON it decodes to.
    fn ex(&mut self, text: &str, note: &str) {
        self.after_block = true;
        self.line("");
        if !note.is_empty() {
            self.line(&format!(
                "      {}",
                ui::paint(ui::DIM, &format!("# {note}"))
            ));
        }
        for l in text.lines() {
            self.line(&format!("      {}", code(l)));
        }
        match akd::decode(text) {
            Ok(v) => {
                let json = serde_json::to_string(&v).unwrap_or_default();
                self.line(&format!(
                    "      {} {}",
                    ui::paint(ui::GREEN, "→"),
                    ui::paint(ui::DIM, &json)
                ));
            }
            Err(e) => {
                self.errors += 1;
                self.line(&format!("      {} {e}", ui::paint(ui::RED, "✗")));
            }
        }
    }

    /// Wrong and right, with the reason.
    fn pair(&mut self, wrong: &str, right: &str, why: &str) {
        self.after_block = true;
        self.line("");
        self.line(&format!(
            "      {} {}",
            ui::paint(ui::RED, "✗"),
            code(wrong)
        ));
        self.line(&format!(
            "      {} {}",
            ui::paint(ui::GREEN, "✓"),
            code(right)
        ));
        if akd::decode(right).is_err() {
            self.errors += 1;
        }
        self.line(&format!("        {}", ui::paint(ui::DIM, why)));
    }

    /// Two columns: syntax (highlighted) and meaning.
    fn table(&mut self, rows: &[(&str, &str)]) {
        self.after_block = true;
        let col = rows
            .iter()
            .map(|(a, _)| a.chars().count())
            .max()
            .unwrap_or(0)
            + 3;
        self.line("");
        for (a, b) in rows {
            let pad = " ".repeat(col - a.chars().count());
            self.line(&format!(
                "      {}{pad}{}",
                code(a),
                ui::paint(ui::WHITE, b)
            ));
        }
    }

    /// Plain two-column table (left side not AK-DATA).
    fn table_plain(&mut self, head: (&str, &str), rows: &[(&str, &str)]) {
        self.after_block = true;
        let col = rows
            .iter()
            .map(|(a, _)| a.chars().count())
            .chain([head.0.chars().count()])
            .max()
            .unwrap_or(0)
            + 3;
        self.line("");
        let pad = " ".repeat(col - head.0.chars().count());
        self.line(&format!(
            "      {}{pad}{}",
            ui::paint(ui::DIM, head.0),
            ui::paint(ui::DIM, head.1)
        ));
        for (a, b) in rows {
            let pad = " ".repeat(col - a.chars().count());
            self.line(&format!("      {}{pad}{}", ui::paint(ui::CYAN, a), code(b)));
        }
    }

    /// Lines of a code block (not decoded: grammar, shell).
    fn block(&mut self, text: &str, color: &str) {
        self.after_block = true;
        self.line("");
        for l in text.lines() {
            self.line(&format!("      {}", ui::paint(color, l)));
        }
    }
}

fn overview(d: &mut Doc) {
    d.p("AK-DATA (Arkadia Data Format) is a text format for JSON data that is read by language models. A ``<header>`` names every field once, with its type; the data that follows lists only values, by position. It carries exactly the same information as JSON — decoding always returns the original — in roughly half the tokens.");
    d.ex(
        "<users:<[id:number,name:string,active:bool]>>([(1,\"Ada\",true),(2,\"Alan\",false)])",
        "compact form (one line, for prompts)",
    );
    d.ex(
        "<users:<[id:number, name:string, active:bool]>>\n([\n  (1, \"Ada\", true),\n  (2, \"Alan\", false)\n])",
        "readable form: the same text with whitespace (insignificant)",
    );
    d.p("Read it like this: ``<users:…>`` says the root is a record with one field ``users``; ``<[…]>`` says that field is a list whose every element is a record ``(id, name, active)``. In the data, ``( )`` is a record and ``[ ]`` a list. Only the header has names; the data is positional.");
    d.sub("Design rules");
    d.bullets(&[
        "Lossless: every JSON value has exactly one meaning in AK-DATA and decodes back to it (key order kept, ``199.0`` stays a float).",
        "Schema first: structure is declared once, before the data, so a reader (or a model) knows the shape before the values.",
        "Positional data: repeated keys disappear; nested records and lists stay positional at every level.",
        "Irregular data is allowed: a value that does not fit its header carries its own type or keys (``<string> \"12\"``, ``<any> {…}``).",
        "Metadata is not data: comments, ``$attr=…`` and ``#tags`` help the reader and are ignored when decoding.",
    ]);
}

fn document(d: &mut Doc) {
    d.p("A document is: optional metadata, optional named type declarations, an optional root header, then exactly one value.");
    d.block(
        "document  =  meta*  ( '@' Name header  meta* )*  header?  meta*  value  meta*",
        ui::CYAN,
    );
    d.ex(
        "/* optional comment */\n@Point<x:number,y:number>\n<start:@Point,end:@Point>\n((0,0),(3,4))",
        "all four parts",
    );
    d.bullets(&[
        "The value can be anything: a record ``( )`` or ``{ }``, a list ``[ ]``, or a primitive. Without a header it is read as plain data.",
        "Whitespace and line breaks are allowed between any two tokens and mean nothing (except inside strings).",
        "Compact form: one line, no optional spaces, newlines in strings written as ``\\n`` — the form for prompts. Readable form: the same tokens with spaces and indentation.",
        "Text is UTF-8; any character is allowed inside strings. Usual file extensions: ``.akd``, ``.ak-data``. In chat, put it in a ```akd fence or between ``<data>…</data>``.",
        "ANSI colour codes (from a terminal) are stripped before decoding, so coloured output can be pasted back.",
    ]);
}

fn values(d: &mut Doc) {
    d.table(&[
        ("\"Ada\"", "string — always in double quotes"),
        (
            "\"a \\\"b\\\" \\\\ \\n\"",
            "escapes: \\\" \\\\ \\n \\t \\r; any other \\x is x",
        ),
        ("42  -7  0", "number (integer)"),
        ("199.0  3.14  -2.5e-3", "number (float; 199.0 stays 199.0)"),
        ("true  false", "bool"),
        ("null", "null — fits every type"),
    ]);
    d.ex(
        "(\"Zoë\",\"line 1\\nline 2\",-0.5,1e3,true,null)",
        "a record without a header: fields are named _0, _1 …",
    );
    d.bullets(&[
        "Numbers are written as in JSON: no ``+``, no thousands separators, no units, no ``NaN``/``Infinity``. ``1e3`` is a float.",
        "Lenient reading: an unquoted word in data is read as a string (``(Ada)`` → ``\"Ada\"``). Writers must still quote every string — ``true``, ``false``, ``null`` and numbers are the only bare values.",
    ]);
}

fn header(d: &mut Doc) {
    d.p("A header ``<…>`` declares the shape of the value after it: a record with fields in order, a list, or a primitive type. Field order is the position of the value in the record.");
    d.table(&[
        (
            "<a:type,b:type>",
            "record with fields a, b (positions 0, 1)",
        ),
        (
            "<[a:type,b:type]>",
            "list whose every element is that record",
        ),
        ("<[string]>", "list of strings (any element type)"),
        ("<number>", "a single primitive"),
        ("f:<x:number,y:number>", "field holding a nested record"),
        (
            "f:<[sku:string,qty:number]>",
            "field holding a list of records",
        ),
        ("f:[string]", "field holding a list of strings"),
        ("f:[[number]]", "list of lists (matrix)"),
        ("f:[<a:number>]", "same as f:<[a:number]>"),
        ("f:@User", "field of a named type (see: named)"),
        ("f", "field without a type = any"),
    ]);
    d.sub("Types");
    d.table_plain(
        ("type", "values"),
        &[
            ("string", "\"…\""),
            (
                "number",
                "42, 3.5, -1e-3   (int and float are accepted aliases)",
            ),
            ("bool", "true, false"),
            ("null", "null"),
            ("any", "anything; the value decides"),
            ("binary", "a string (e.g. base64); kept as is"),
        ],
    );
    d.sub("Field names");
    d.p("A name is an identifier — letters, digits and ``_``, not starting with a digit. Anything else goes in backticks: ``<`user id`:number,`e-mail`:string,`2fa`:bool>``. In headers only backticks are allowed for names (not double quotes).");
    d.ex(
        "<`user id`:number,`e-mail`:string>(17,\"ada@example.com\")",
        "",
    );
    d.ex(
        "<id,name>(1,\"Ada\")",
        "header without types (--no-types): every field is any",
    );
}

fn records(d: &mut Doc) {
    d.sub("Positional record ( )");
    d.p("Values follow the header order: the n-th value belongs to the n-th field, at every nesting level.");
    d.ex(
        "<id:string,customer:<id:number,name:string>,items:<[sku:string,qty:number]>,total:number>\n(\"A1\",(7,\"Ada\"),[(\"KB-01\",2),(\"MS-02\",1)],178.0)",
        "nested record and nested list stay positional",
    );
    d.ex(
        "<a:number,b:number,c:number>(1,2)",
        "fewer values: the missing fields are absent (not null)",
    );
    d.ex(
        "<a:number>(1,2,3)",
        "more values: extra fields are named _1, _2 …",
    );
    d.ex("(1,\"x\")", "no header: fields are named _0, _1 …");
    d.sub("Named record { }");
    d.p("Keys written next to the values — for a record without a header or one that does not fit it. Keys are identifiers, backticks or double-quoted strings.");
    d.ex(
        "{id:1,name:\"Ada\",`e-mail`:\"ada@example.com\",\"\":0}",
        "",
    );
    d.ex(
        "<[name:string,tools:[string]]>[(\"planner\",[\"search\"]),<any> {name:\"writer\",temperature:0.4}]",
        "inside a list with a header, a named record keeps its own keys",
    );
    d.ex(
        "<a:number,b:string>{b:\"x\",a:1}",
        "a named record may also follow a header (keys matched by name)",
    );
}

fn lists(d: &mut Doc) {
    d.ex("[1,2,3]", "list of values");
    d.ex("<[number]>[1,2,3]", "with an element type");
    d.ex("<tags:[string]>([\"a\",\"b\"])", "list field");
    d.ex("<tags:[string]>([])", "empty list");
    d.ex(
        "<[id:number,tags:[string]]>[(1,[\"a\"]),(2,[])]",
        "list of records sharing one header",
    );
    d.ex("<km:[[number]]>([[0,293],[293,0]])", "list of lists");
    d.ex(
        "<[number]>[1,<string> \"two\",null]",
        "mixed list: values of another type carry it",
    );
    d.ex(
        "<[id:number,name:string,email:string]>[(1,\"Ada\",\"a@x.io\"),(2,\"Alan\")]",
        "optional last field: the second record has only id and name",
    );
    d.ex(
        "<rows:<[d:string,v:number]>>([//$size=3// (\"mon\",4),(\"tue\",7),(\"wed\",2)])",
        "$size=N: the number of items, for the reader (enc --sizes)",
    );
}

fn overrides(d: &mut Doc) {
    d.p("A value whose type or shape is different from its header says so itself, so mixed and irregular data stays lossless.");
    d.table(&[
        (
            "<string> \"12\"",
            "type override: a string where the header says number",
        ),
        ("<number> 3001", "a number in a string column"),
        ("<any> {k:v}", "a record with its own keys (shape differs)"),
        ("<any> [ … ]", "a list where the header says something else"),
        (
            "<null> null",
            "an absent nested record (null alone also works)",
        ),
        ("<a:number>(1)", "any value may carry its own inline header"),
    ]);
    d.ex(
        "<[sku:string,price:number,stock:number]>[(\"KB-01\",89.0,14),(<number> 3001,null,120),(\"HD-10\",129.9,<string> \"on order\")]",
        "a number SKU and a text stock in typed columns",
    );
    d.ex(
        "<[id:number,addr:<city:string,zip:string>]>[(1,(\"Kraków\",\"30-001\")),(2,<null> null)]",
        "missing nested record",
    );
}

fn named(d: &mut Doc) {
    d.p("``@Name<…>`` declares a header once under a name; ``@Name`` uses it in other headers; ``@Name(…)`` gives a value that type. Declarations come before the root value; a later declaration with the same name replaces the earlier one. Encoders write inline headers — named types are for hand-written data and long schemas.");
    d.ex(
        "@User<id:number,name:string>\n<team:string,lead:@User,members:[@User]>\n(\"core\",(1,\"Ada\"),[(2,\"Alan\"),(3,\"Grace\")])",
        "",
    );
    d.ex(
        "@Point<x:number,y:number>\n@Point(3,4)",
        "a root value of a named type",
    );
}

fn metadata(d: &mut Doc) {
    d.p("Notes for the reader. They may appear between any tokens (before or after a value, between fields) and are skipped when decoding: the JSON is the same with or without them.");
    d.table(&[
        ("/* text */", "comment (may nest: /* a /* b */ c */)"),
        (
            "$key=value",
            "attribute: $unit=\"EUR\" $max=5, or any value: $range=[1,5]",
        ),
        (
            "$required",
            "flag on a header field: the field must be present",
        ),
        ("#tag", "tag: #draft #pk"),
        (
            "// $source=\"db\" #v2 //",
            "meta block: a group of attributes and tags",
        ),
        (
            "[//$size=90// …]",
            "number of items of a list (enc --sizes): models need not count",
        ),
        (
            "// $changes=<[…]>[(…)] //",
            "history of the document (ak-data merge / apply / history)",
        ),
    ]);
    d.ex(
        "// $source=\"crm\" #snapshot //\n<customers:<[id:number /* pk */,plan:string $values=\"free|pro\",mrr:number]>>\n([(1,\"pro\",99) #trial,(2,\"free\",0)])",
        "",
    );
    d.p("An attribute value can be structured — a list or a record with its own header. It is still metadata: the history ``$changes`` written by ``ak-data merge`` and ``ak-data apply`` sits after the data and never changes what the document decodes to.");
    d.ex(
        "<n:number>(3)\n// $changes=<[id:string,title:string,changes:<[op:string,path:string,old:number,new:number]>]>[(\"9f3c2a1b7e\",\"Bump\",[(\"change\",\"n\",2,3)])] //",
        "data with its history",
    );
}

fn encoder(d: &mut Doc) {
    d.p("All encoders (Python, npm, Rust) write the same text for the same JSON. Knowing the rules helps to read real output:");
    d.bullets(&[
        "Object → record with a header ``<…>`` and positional values ``( )``. Only an object with a key a header cannot spell (the empty key ``\"\"``, a name containing a backtick) is written as a named record ``{ }``.",
        "List of objects with the same keys → ``<[…]>`` header taken from the first element, one ``( )`` per element. Key order in the header follows the first element; later elements are matched by name (the most common set of keys wins).",
        "Records with optional fields → one header with every field, the most frequent first; a record that has only the first k fields is written with k values (``(1,\"Ada\")`` under ``<[id,name,email]>``). Used when it lets more records be positional than the most common exact layout.",
        "An element that fits neither (other or extra keys) → ``<any> {key:value}`` in the list.",
        "``--sizes[=n]`` (Python ``dumps(sizes=n)``, npm ``dumps(data, {sizes: n})``) adds ``//$size=N//`` to every list of n+ items.",
        "A value of another type than its column → ``<type> value``; ``null`` fits every type and needs no override.",
        "Empty list → ``[]``; its element type comes from other records or is any.",
        "Numbers: integers as integers, floats keep a fraction (``199.0``), very small/large floats in plain or exponent form as JSON.",
        "Compact form escapes newlines in strings (``\\n``); the readable form (``ak-data read`` without ``-c``) adds spaces and line breaks.",
        "``--no-types`` writes names only (``<id,name>``), ``--no-schema`` leaves out the header.",
    ]);
    d.ex("<a:number,b:[number],n:<[a:number,t:string]>>(1,[1,2,<string> \"x\"],[(1,\"x\"),(<string> \"2\",\"y\"),(3,<any> {z:1})])", "what the encoder writes for irregular input");
}

fn json(d: &mut Doc) {
    d.table_plain(
        ("JSON", "AK-DATA"),
        &[
            ("{\"a\": 1, \"b\": \"x\"}", "<a:number,b:string>(1,\"x\")"),
            ("[{\"a\": 1}, {\"a\": 2}]", "<[a:number]>[(1),(2)]"),
            ("[1, 2, 3]", "<[number]>[1,2,3]"),
            ("{\"t\": [\"x\", \"y\"]}", "<t:[string]>([\"x\",\"y\"])"),
            ("{\"o\": {\"k\": true}}", "<o:<k:bool>>((true))"),
            ("{\"user id\": 5}", "<`user id`:number>(5)"),
            ("{\"a\": null}", "<a:null>(null)"),
            ("[{\"a\": 1}, {\"b\": 2}]", "<[any]>[{a:1},{b:2}]"),
            ("\"text\"", "<string>\"text\""),
            ("{}", "{}"),
            ("[]", "<[any]>[]"),
        ],
    );
    d.p("Every row decodes to the JSON on its left; ``ak-data read file.json`` and ``ak-data read file.akd -t json`` convert both ways.");
}

fn grammar(d: &mut Doc) {
    d.block(
        r##"document   = meta* { "@" name header meta* } [ header meta* ] value meta*

header     = "<" [ fields | "[" element "]" | type ] ">"
fields     = field { "," field }
field      = meta* name [ ":" type ] meta*
element    = fields | type | header
type       = prim | "any" | "[" type "]" | header | "@" name [ header ]
prim       = "string" | "number" | "int" | "float" | "bool" | "null" | "binary"

value      = meta* ( typed | record | named | list | prim_value )
typed      = header value                       (* override / inline header *)
           | "@" name value
record     = "(" [ value { "," value } ] ")"    (* positional *)
named      = "{" [ key ":" value { "," key ":" value } ] "}"
key        = name | string
list       = "[" [ value { "," value } ] "]"
prim_value = string | number | "true" | "false" | "null" | word

name       = ident | "`" { any char except "`" } "`"
ident      = ( letter | "_" ) { letter | digit | "_" }
string     = '"' { char | "\" escape } '"'      (* \n \t \r, else literal *)
number     = [ "-" ] digits [ "." digits ] [ ( "e" | "E" ) [ "+" | "-" ] digits ]

meta       = comment | block | attribute | tag
comment    = "/*" { any | comment } "*/"
block      = "//" { attribute | tag | name [ "=" prim_value ] | comment } "//"
attribute  = "$" ident [ "=" value ]           (* metadata, also when structured *)
tag        = "#" ident"##,
        ui::CYAN,
    );
    d.p("Whitespace is allowed between all tokens. Decoding is error-tolerant: problems are collected with their positions (``ak-data read --strict`` fails on any of them) and the rest of the document is still read.");
}

fn writing(d: &mut Doc) {
    d.sub("Steps");
    d.bullets(&[
        "Declare the structure first: copy the header you were given exactly, or write one — a list of results is ``<result:<[field:type,…]>>``, one object is ``<field:type,…>``.",
        "Then one record per item, values in header order: ``[(…),(…)]`` for a list.",
        "Quote every string; ``null`` for a missing value; plain numbers (``1234.5``, not ``\"1 234,5 zł\"``).",
        "Nested objects are nested records ``( )``; nested lists ``[ ]``; both declared in the header.",
        "Before sending: every record has as many values as its header has fields; brackets balance; no trailing commas needed.",
    ]);
    d.sub("Common mistakes");
    d.pair(
        "<result:[name:string,total:number]>([(\"Ada\",3)])",
        "<result:<[name:string,total:number]>>([(\"Ada\",3)])",
        "a list of records is <[…]> inside the field: result:<[…]>",
    );
    d.pair(
        "<[name:string,total:number]>[(Ada,3)]",
        "<[name:string,total:number]>[(\"Ada\",3)]",
        "strings are quoted (bare words are tolerated when reading, never write them)",
    );
    d.pair(
        "<[name:string,total:number]>[(\"Ada\",\"1 234 zł\")]",
        "<[name:string,total:number]>[(\"Ada\",1234)]",
        "numbers without units, spaces or separators",
    );
    d.pair(
        "<[id:number,name:string]>[(1),(2,\"Alan\")]",
        "<[id:number,name:string]>[(1,null),(2,\"Alan\")]",
        "keep positions: write null for an unknown value",
    );
    d.pair(
        "<[name:string,total:number]>[{name:\"Ada\",total:3}]",
        "<[name:string,total:number]>[(\"Ada\",3)]",
        "with a header, write positional records — keys again waste the tokens the header saved",
    );
    d.pair(
        "<\"user id\":number>(5)",
        "<`user id`:number>(5)",
        "names with spaces or symbols use backticks",
    );
    d.pair(
        "Sure! Here it is: <a:number>(1)",
        "<a:number>(1)",
        "when asked for \"AK-DATA only\": no prose and no ``` code fences",
    );
    d.sub("Asking a model for AK-DATA");
    d.block(
        "Answer in AK-DATA only (no prose, no code fences), with exactly this header\nand one record per item:\n<result:<[country:string,orders:number,revenue:number]>>",
        ui::WHITE,
    );
    d.p("Give the definition (``FORMAT_DEFINITION`` in the libraries), the data, the question and the header to fill. ``ak-data prompt`` and ``ak-data example --prompt`` build such prompts.");
}

fn tools(d: &mut Doc) {
    d.block(
        "ak-data data.json [-c]            any file or text → AK-DATA (laid out / one line)\nak-data data.akd -t json          → JSON / JSON min / TOON (-i: read as json / akd)\nak-data diff old.json new.json    what changed, with context\nak-data merge data.akd new.json   join + record the change ($changes)\nak-data apply data.akd patch.akd  apply a change, with or without history\nak-data history data.akd          who changed what and when\nak-data prompt data.json -q \"…\"   copy-paste prompt for a chat model\nak-data example [--prompt]        a random example (with a prompt)\nak-data info [section]            this definition",
        ui::GREEN,
    );
    d.block(
        "Python  pip install arkadia-data    import arkadia.data as akd\nnpm     npm install @arkadia/data   import { encode, decode } from '@arkadia/data'\nRust    cargo add arkadia-data      use arkadia_data as akd;",
        ui::CYAN,
    );
    d.p("Skills for agents (SKILL.md): ``ak-data-format`` (read and write the format) and ``ak-data-install`` (install and use the tools).");
}

fn render(d: &mut Doc, id: &str) {
    match id {
        "overview" => overview(d),
        "document" => document(d),
        "values" => values(d),
        "header" => header(d),
        "records" => records(d),
        "lists" => lists(d),
        "overrides" => overrides(d),
        "named" => named(d),
        "metadata" => metadata(d),
        "encoder" => encoder(d),
        "json" => json(d),
        "grammar" => grammar(d),
        "writing" => writing(d),
        _ => tools(d),
    }
}

fn find(key: &str) -> Option<usize> {
    let k = key.to_lowercase();
    SECTIONS
        .iter()
        .position(|(id, _)| *id == k || id.starts_with(&k))
        .or_else(|| {
            k.parse::<usize>()
                .ok()
                .filter(|n| (1..=SECTIONS.len()).contains(n))
                .map(|n| n - 1)
        })
}

fn contents(d: &mut Doc) {
    d.line("");
    d.line(&format!("    {}", ui::paint(ui::YELLOW, "CONTENTS")));
    for (i, (id, title)) in SECTIONS.iter().enumerate() {
        d.line(&format!(
            "     {} {}  {}",
            ui::paint(ui::GREEN, &format!("{:>2}", i + 1)),
            ui::paint(ui::WHITE, &format!("{title:<44}")),
            ui::paint(ui::DIM, &format!("ak-data info {id}"))
        ));
    }
}

/// The definition (all sections, or the one named by `topic`).
pub fn text(topic: Option<&str>) -> Result<(String, usize), String> {
    let mut d = Doc {
        out: String::new(),
        errors: 0,
        after_block: false,
    };
    let chosen = match topic {
        Some(t) => Some(find(t).ok_or_else(|| {
            format!(
                "No section '{t}'. Sections: {}",
                SECTIONS.iter().map(|s| s.0).collect::<Vec<_>>().join(", ")
            )
        })?),
        None => None,
    };
    if chosen.is_none() {
        d.line("");
        d.line(&format!(
            "  {}  {}",
            ui::paint(&format!("{}{}", ui::BOLD, ui::GREEN), "AK-DATA"),
            ui::paint(ui::WHITE, "Arkadia Data Format — the complete definition")
        ));
        d.line(&format!(
            "  {}",
            ui::paint(
                ui::DIM,
                &format!(
                    "v{} · every example below is decoded live; → shows the JSON it means",
                    akd::VERSION
                )
            )
        ));
        contents(&mut d);
    }
    for (i, (id, title)) in SECTIONS.iter().enumerate() {
        if chosen.is_some_and(|c| c != i) {
            continue;
        }
        d.section(i + 1, id, title);
        render(&mut d, id);
    }
    d.line("");
    if chosen.is_none() {
        d.line(&format!(
            "  {}",
            ui::paint(
                ui::DIM,
                "Examples: ak-data example · page through: ak-data info --color | less -R"
            )
        ));
        d.line("");
    }
    Ok((d.out, d.errors))
}

pub fn run(args: &crate::Args) -> crate::Result<()> {
    if args.has("list") {
        let mut d = Doc {
            out: String::new(),
            errors: 0,
            after_block: false,
        };
        contents(&mut d);
        d.line("");
        return crate::emit(&d.out, args);
    }
    let topic = args.positional.get(1).map(String::as_str);
    let (out, _) = text(topic)?;
    crate::emit(&out, args)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_example_decodes() {
        let (out, errors) = text(None).unwrap();
        assert_eq!(errors, 0, "{out}");
        for (id, _) in SECTIONS {
            assert!(out.contains(&format!("ak-data info {id}")));
            assert!(text(Some(id)).is_ok());
        }
        assert!(text(Some("nope")).is_err());
        assert_eq!(find("gram"), Some(11));
        assert_eq!(find("3"), Some(2));
    }
}
