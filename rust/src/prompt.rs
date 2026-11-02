//! Copy-paste prompts: intro, format definition, data, question and answer
//! format — the same text as the Python and TypeScript packages.

use std::fmt;
use std::str::FromStr;

use serde_json::Value;

use crate::encoder::{encode, EncodeOptions};
use crate::Error;

/// One-line description of AK-DATA for system prompts (~95 tokens).
pub const HINT: &str = "Data is in AK-Data format: <field:type,...> is a header; (v1,v2) is a record whose values follow the header order; {key:value} is a named record; [..] is a list; <[...]> describes every record in the list; <type> before a value overrides its type; a record with fewer values has only the first fields; //$size=N// is the number of items in a list.";

/// The full format definition (~150 tokens) to paste with the data.
pub const FORMAT_DEFINITION: &str = "AK-DATA (Arkadia Data Format): <a:type,b:type> is a header; (v1,v2) is a record whose values follow the header order.\n<[a:type,...]>[(...),(...)] is a list of records sharing that header; headers nest, e.g. items:<[sku:string,qty:number]>.\n{key:value} is a record with names; <type> or <any> before a value overrides the header type.\nStrings are quoted; numbers, true, false, null as in JSON; /*...*/, $attr, #tag are metadata, not data.\nA record with fewer values than its header has only the first fields; //$size=N// before list items is their count.";

/// How to read TOON, for TOON prompts.
pub const TOON_DEFINITION: &str = "TOON (Token-Oriented Object Notation) — how to read it:\n- Indentation shows nesting; \"key: value\" is a field.\n- key[N]{f1,f2,...}: is followed by N rows of comma-separated values in field order.\n- key[N]: a,b,c is a list of N values; \"- \" starts an item of a list of objects.";

/// Text formats for data in prompts.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Format {
    /// JSON, indented by 2.
    Json,
    /// JSON on one line.
    JsonMin,
    /// TOON.
    Toon,
    /// AK-DATA, readable form.
    AkData,
    /// AK-DATA, compact single-line form.
    AkDataCompact,
}

impl Format {
    /// Every format, in the order used by `--all-formats`.
    pub const PROMPT_FORMATS: [Format; 4] = [
        Format::Json,
        Format::Toon,
        Format::AkData,
        Format::AkDataCompact,
    ];

    /// Display name: JSON, TOON, AK-DATA, AK-DATA COMPACT.
    pub fn label(self) -> &'static str {
        match self {
            Format::Json => "JSON",
            Format::JsonMin => "JSON (minified)",
            Format::Toon => "TOON",
            Format::AkData => "AK-DATA",
            Format::AkDataCompact => "AK-DATA COMPACT",
        }
    }

    /// Short key: json, json-min, toon, akd, akcd.
    pub fn key(self) -> &'static str {
        match self {
            Format::Json => "json",
            Format::JsonMin => "json-min",
            Format::Toon => "toon",
            Format::AkData => "akd",
            Format::AkDataCompact => "akcd",
        }
    }

    pub fn is_ak_data(self) -> bool {
        matches!(self, Format::AkData | Format::AkDataCompact)
    }
}

impl fmt::Display for Format {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.label())
    }
}

impl FromStr for Format {
    type Err = Error;

    /// Accepts json, json-min, toon, ak-data, ak-data-compact, akd, akcd
    /// (any case; spaces and underscores count as dashes).
    fn from_str(name: &str) -> Result<Self, Error> {
        let mut key = String::new();
        let mut dash = false;
        for c in name.trim().to_lowercase().chars() {
            if c == '_' || c.is_whitespace() {
                if !dash {
                    key.push('-');
                }
                dash = true;
            } else {
                key.push(c);
                dash = false;
            }
        }
        Ok(match key.as_str() {
            "json" => Format::Json,
            "json-min" => Format::JsonMin,
            "toon" => Format::Toon,
            "akd" | "ak-data" | "akdata" => Format::AkData,
            "akcd" | "ak-data-compact" | "compact" => Format::AkDataCompact,
            _ => {
                return Err(Error::Format(format!(
                    "Unknown format '{name}'. Use one of: json, toon, ak-data, ak-data-compact"
                )))
            }
        })
    }
}

/// The value written in `format`.
pub fn encode_as(value: &Value, format: Format) -> String {
    match format {
        Format::Json => serde_json::to_string_pretty(value).unwrap_or_default(),
        Format::JsonMin => serde_json::to_string(value).unwrap_or_default(),
        Format::Toon => crate::toon::encode(value),
        Format::AkData => encode(value, &EncodeOptions::pretty()),
        Format::AkDataCompact => encode(value, &EncodeOptions::compact()),
    }
}

/// Expected answer: a list `name` of records with `(field, type)` columns.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Answer {
    pub name: String,
    pub fields: Vec<(String, String)>,
}

impl Answer {
    /// Parses `"name:string,total:number"` (type defaults to string).
    pub fn parse(spec: &str, name: Option<&str>) -> Option<Answer> {
        if spec.trim().is_empty() {
            return None;
        }
        let fields = spec
            .split(',')
            .map(|part| {
                let mut it = part.trim().split(':');
                let f = it.next().unwrap_or("").trim().to_string();
                let t = it.next().unwrap_or("").trim();
                (
                    f,
                    if t.is_empty() {
                        "string".to_string()
                    } else {
                        t.to_string()
                    },
                )
            })
            .collect();
        Some(Answer {
            name: name
                .filter(|n| !n.is_empty())
                .unwrap_or("result")
                .to_string(),
            fields,
        })
    }

    /// The answer instruction for `format`.
    pub fn instruction(&self, format: Format) -> String {
        match format {
            Format::AkData | Format::AkDataCompact => {
                let cols: Vec<String> = self
                    .fields
                    .iter()
                    .map(|(f, t)| format!("{f}:{t}"))
                    .collect();
                format!(
                    "Answer in AK-DATA only (no prose, no code fences), with exactly this header and one record per item:\n<{}:<[{}]>>",
                    self.name,
                    cols.join(",")
                )
            }
            Format::Toon => {
                let cols: Vec<&str> = self.fields.iter().map(|(f, _)| f.as_str()).collect();
                format!(
                    "Answer in TOON only (no prose, no code fences): {}[N]{{{}}}: followed by one row per item.",
                    self.name,
                    cols.join(",")
                )
            }
            Format::Json | Format::JsonMin => {
                let shape: Vec<String> = self
                    .fields
                    .iter()
                    .map(|(f, t)| format!("\"{f}\": <{t}>"))
                    .collect();
                format!(
                    "Answer with JSON only (no prose): {{\"{}\": [{{{}}}, ...]}}",
                    self.name,
                    shape.join(", ")
                )
            }
        }
    }
}

/// Width of the readable AK-DATA in prompts (same in Python and TypeScript).
pub const PROMPT_WIDTH: usize = 80;

/// The data as it goes into a prompt: readable AK-DATA is laid out to
/// [`PROMPT_WIDTH`] columns, the other formats are written as usual.
pub fn prompt_payload(data: &Value, format: Format) -> String {
    match format {
        Format::AkData => {
            crate::layout::pretty(&encode(data, &EncodeOptions::compact()), PROMPT_WIDTH)
        }
        other => encode_as(data, other).trim_end_matches('\n').to_string(),
    }
}

/// Intro, format definition, notes (optional), `<data>…</data>`, question
/// and answer format.
pub fn assemble_prompt(
    format: Format,
    data_text: &str,
    question: &str,
    answer: Option<&Answer>,
    definition: bool,
    notes: &str,
) -> String {
    let intro = match format {
        Format::AkData => "AK-DATA",
        Format::AkDataCompact => "AK-DATA (compact, single-line form)",
        other => other.label(),
    };
    let mut parts = vec![format!("The data below is in {intro}.")];
    if definition && format.is_ak_data() {
        parts.push(FORMAT_DEFINITION.to_string());
    } else if definition && format == Format::Toon {
        parts.push(TOON_DEFINITION.to_string());
    }
    if !notes.is_empty() {
        parts.push(notes.to_string());
    }
    parts.push(format!("<data>\n{data_text}\n</data>"));
    parts.push(format!("Question: {question}"));
    if let Some(a) = answer {
        parts.push(a.instruction(format));
    }
    parts.join("\n\n") + "\n"
}

/// The full prompt: intro, format definition, `<data>…</data>`, question and
/// (optionally) the answer format.
pub fn build_prompt(
    data: &Value,
    question: &str,
    format: Format,
    answer: Option<&Answer>,
    definition: bool,
) -> String {
    assemble_prompt(
        format,
        &prompt_payload(data, format),
        question,
        answer,
        definition,
        "",
    )
}

/// A ready-to-paste block for a system prompt or a tool result:
/// the one-line hint (optional) and `<label>…</label>` with compact AK-DATA.
pub fn to_prompt(data: &Value, hint: bool, label: &str) -> String {
    let body = encode(data, &EncodeOptions::compact());
    let block = format!("<{label}>\n{body}\n</{label}>");
    if hint {
        format!("{HINT}\n{block}")
    } else {
        block
    }
}
