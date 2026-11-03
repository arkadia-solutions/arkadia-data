//! The bundled copy-paste examples (same as `examples/prompts/` in the
//! repository): data, question, answer shape, the expected answer and —
//! for most of them — metadata: the same facts as `$attributes`/`#tags` and
//! as `/* comments */` (for JSON and TOON: notes before the data).

use serde_json::Value;

use crate::layout;
use crate::prompt::{assemble_prompt, prompt_payload, Answer, Format, PROMPT_WIDTH};

static EXAMPLES_JSON: &str = include_str!("../data/examples.json");

/// One bundled example.
#[derive(Debug, Clone)]
pub struct Example {
    pub id: u64,
    pub slug: String,
    pub title: String,
    pub description: String,
    pub question: String,
    pub answer: Answer,
    pub expected: Value,
    pub data: Value,
    /// "metadata", "needs metadata".
    pub tags: Vec<String>,
    /// Compact AK-DATA with every attribute and comment (None: no metadata).
    pub akd_meta: Option<String>,
    /// The same facts as notes: comments and attributes.
    pub notes_comments: Vec<String>,
    pub notes_attributes: Vec<String>,
    /// Hand-written AK-DATA (feature examples: named types, metadata …).
    pub akd: Option<String>,
}

impl Example {
    /// The prompt of this example in `format`, without metadata.
    pub fn prompt(&self, format: Format, definition: bool) -> String {
        self.prompt_with(format, definition, false, false)
    }

    /// True when the example has metadata to add.
    pub fn has_meta(&self) -> bool {
        self.akd_meta.is_some()
    }

    /// The data in `format` with the chosen metadata (inline in AK-DATA).
    pub fn data_text(&self, format: Format, comments: bool, attributes: bool) -> String {
        match (
            &self.akd_meta,
            format.is_ak_data() && (comments || attributes),
        ) {
            (Some(meta), true) => {
                let text = if comments && attributes {
                    layout::compact(meta)
                } else {
                    layout::strip_meta(meta, comments, attributes)
                };
                if format == Format::AkData {
                    layout::pretty(&text, PROMPT_WIDTH)
                } else {
                    text
                }
            }
            _ => match (&self.akd, format.is_ak_data()) {
                (Some(source), true) => {
                    let text = layout::strip_meta(source, false, false);
                    if format == Format::AkData {
                        layout::pretty(&text, PROMPT_WIDTH)
                    } else {
                        text
                    }
                }
                _ => prompt_payload(&self.data, format),
            },
        }
    }

    /// True for the examples that show one part of the format.
    pub fn is_feature(&self) -> bool {
        self.tags.iter().any(|t| t == "feature")
    }

    /// Notes before the data for formats without comments (JSON, TOON).
    pub fn notes_text(&self, format: Format, comments: bool, attributes: bool) -> String {
        if format.is_ak_data() {
            return String::new();
        }
        let mut parts = vec![];
        if comments && !self.notes_comments.is_empty() {
            parts.push(block("Notes about the data:", &self.notes_comments));
        }
        if attributes && !self.notes_attributes.is_empty() {
            parts.push(block("Attributes of the data:", &self.notes_attributes));
        }
        parts.join("\n\n")
    }

    /// The prompt with the chosen metadata.
    pub fn prompt_with(
        &self,
        format: Format,
        definition: bool,
        comments: bool,
        attributes: bool,
    ) -> String {
        assemble_prompt(
            format,
            &self.data_text(format, comments, attributes),
            &self.question,
            Some(&self.answer),
            definition,
            &self.notes_text(format, comments, attributes),
        )
    }
}

fn block(title: &str, lines: &[String]) -> String {
    let items: Vec<String> = lines.iter().map(|l| format!("- {l}")).collect();
    format!("{title}\n{}", items.join("\n"))
}

fn strings(v: Option<&Value>) -> Vec<String> {
    v.and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn text(v: &Value, key: &str) -> String {
    v.get(key).and_then(Value::as_str).unwrap_or("").to_string()
}

/// All bundled examples, by id (parsed once).
pub fn all() -> Vec<Example> {
    static CACHE: std::sync::OnceLock<Vec<Example>> = std::sync::OnceLock::new();
    CACHE.get_or_init(parse_all).clone()
}

fn parse_all() -> Vec<Example> {
    let list: Vec<Value> = serde_json::from_str(EXAMPLES_JSON).unwrap_or_default();
    let mut out: Vec<Example> = list
        .iter()
        .map(|v| {
            let a = v.get("answer").cloned().unwrap_or(Value::Null);
            let fields = a
                .get("fields")
                .and_then(Value::as_array)
                .map(|fs| {
                    fs.iter()
                        .map(|f| {
                            let s = |i: usize| {
                                f.get(i).and_then(Value::as_str).unwrap_or("").to_string()
                            };
                            (s(0), s(1))
                        })
                        .collect()
                })
                .unwrap_or_default();
            Example {
                id: v.get("id").and_then(Value::as_u64).unwrap_or(0),
                slug: text(v, "slug"),
                title: text(v, "title"),
                description: text(v, "description"),
                question: text(v, "question"),
                answer: Answer {
                    name: a
                        .get("name")
                        .and_then(Value::as_str)
                        .unwrap_or("result")
                        .to_string(),
                    fields,
                },
                expected: v.get("expected").cloned().unwrap_or(Value::Null),
                data: v.get("data").cloned().unwrap_or(Value::Null),
                tags: strings(v.get("tags")),
                akd_meta: v
                    .get("akd_meta")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                notes_comments: strings(v.get("notes").and_then(|n| n.get("comments"))),
                notes_attributes: strings(v.get("notes").and_then(|n| n.get("attributes"))),
                akd: v.get("akd").and_then(Value::as_str).map(str::to_string),
            }
        })
        .collect();
    out.sort_by_key(|e| e.id);
    out
}

/// An example by id (`3`) or slug (`logs-incidents`).
pub fn get(key: &str) -> Option<Example> {
    all()
        .into_iter()
        .find(|e| e.id.to_string() == key || e.slug == key)
}
