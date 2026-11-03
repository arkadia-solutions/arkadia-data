//! Where `ak-data` reads from: a file, `-` / nothing (stdin), or the text
//! itself as an argument — also in ``` fences:
//!
//!   ak-data data.json
//!   echo '{"a":1}' | ak-data
//!   ak-data '{"a":1}'
//!   ak-data '```<a:number>(1)```'
//!   ak-data diff '{"a":1}' '{"a":2}'
//!   echo '{"a":1} {"a":2}' | ak-data diff

use std::io::Read;

use arkadia_data as akd;
use serde_json::Value;

use crate::Result;

/// How to read the input (`-i`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    /// JSON when it parses as JSON, AK-DATA otherwise.
    Auto,
    Json,
    Akd,
}

impl Kind {
    pub fn parse(name: Option<&str>) -> Result<Kind> {
        match name.map(str::to_ascii_lowercase).as_deref() {
            None | Some("auto") => Ok(Kind::Auto),
            Some("json") => Ok(Kind::Json),
            Some("akd" | "ak-data" | "akdata" | "akcd" | "ak") => Ok(Kind::Akd),
            Some(other) => Err(format!(
                "unknown input type '{other}': -i json, akd or auto"
            )),
        }
    }
}

/// Is the argument data rather than a path?
fn looks_like_data(arg: &str) -> bool {
    let t = arg.trim_start();
    t.starts_with("```")
        || t.starts_with(['{', '[', '<', '(', '"', '@', '`', '$', '#'])
        || t.starts_with("//")
        || t.starts_with("/*")
        || matches!(t.trim(), "true" | "false" | "null")
        || (t.parse::<f64>().is_ok() && !t.contains('/'))
}

fn stdin() -> Result<String> {
    let mut s = String::new();
    std::io::stdin()
        .read_to_string(&mut s)
        .map_err(|e| format!("cannot read stdin: {e}"))?;
    Ok(s)
}

/// The text of one source and a name for messages.
pub fn source(arg: Option<&str>) -> Result<(String, String)> {
    let (name, raw) = match arg {
        None | Some("-") => ("stdin".to_string(), stdin()?),
        Some(a) if std::path::Path::new(a).is_file() => (
            a.to_string(),
            std::fs::read_to_string(a).map_err(|e| format!("cannot read {a}: {e}"))?,
        ),
        Some(a) if looks_like_data(a) => ("text".to_string(), a.to_string()),
        Some(a) => {
            return Err(format!(
                "cannot read {a}: no such file (text works too: ak-data '{{\"a\":1}}')"
            ))
        }
    };
    Ok((name, raw.trim_start_matches('\u{feff}').to_string()))
}

/// The contents of ``` fenced blocks (a language tag on the first line is
/// dropped), or `None` when the text is not fenced.
pub fn fenced(text: &str) -> Option<Vec<String>> {
    if !text.trim_start().starts_with("```") {
        return None;
    }
    let parts: Vec<&str> = text.split("```").collect();
    if parts.len() < 3 || parts.len() % 2 == 0 {
        return None;
    }
    let mut out = Vec::new();
    for (i, part) in parts.iter().enumerate() {
        if i % 2 == 0 {
            if !part.trim().is_empty() {
                return None; // text between blocks: not only fences
            }
            continue;
        }
        let body = match part.split_once('\n') {
            Some((tag, rest))
                if !tag.trim().is_empty()
                    && tag
                        .trim()
                        .chars()
                        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_') =>
            {
                rest
            }
            _ => part,
        };
        out.push(body.trim().to_string());
    }
    Some(out)
}

/// One document: fences removed.
pub fn unfence(text: &str) -> String {
    match fenced(text) {
        Some(blocks) if blocks.len() == 1 => blocks.into_iter().next().unwrap_or_default(),
        _ => text.trim().to_string(),
    }
}

/// Several documents in one text: fenced blocks, or documents one after
/// another.
pub fn documents(text: &str) -> Vec<String> {
    fenced(text).unwrap_or_else(|| akd::diff::split_documents(text))
}

/// A parsed document.
pub struct Parsed {
    pub value: Value,
    pub json: bool,
    /// Decode problems (AK-DATA read leniently).
    pub errors: Vec<String>,
}

/// Reads `text` as JSON or AK-DATA (`kind`).
pub fn parse(text: &str, kind: Kind) -> Result<Parsed> {
    let json_ok = || serde_json::from_str::<Value>(text);
    match kind {
        Kind::Json => json_ok()
            .map(|value| Parsed {
                value,
                json: true,
                errors: vec![],
            })
            .map_err(|e| format!("not valid JSON: {e}")),
        Kind::Auto if json_ok().is_ok() => Ok(Parsed {
            value: json_ok().unwrap_or(Value::Null),
            json: true,
            errors: vec![],
        }),
        _ => {
            let d = akd::decode_lenient(text);
            Ok(Parsed {
                value: d.value,
                json: false,
                errors: d.errors.iter().map(ToString::to_string).collect(),
            })
        }
    }
}

/// The two documents of `diff` / `merge` / `apply`: two arguments, or one
/// argument (or stdin) holding two documents.
pub fn two(positional: &[String], cmd: &str, a: &str, b: &str) -> Result<[(String, String); 2]> {
    let usage = format!(
        "{cmd} needs two documents: ak-data {cmd} {a} {b} — files, text, or two documents on stdin"
    );
    match positional {
        [x, y, ..] => {
            if x == "-" && y == "-" {
                return Err("only one of the two can be stdin (-)".to_string());
            }
            let (nx, tx) = source(Some(x))?;
            let (ny, ty) = source(Some(y))?;
            let name = |n: String, alt: &str| if n == "text" { alt.to_string() } else { n };
            Ok([(name(nx, a), unfence(&tx)), (name(ny, b), unfence(&ty))])
        }
        [x] if x != "-" && std::path::Path::new(x).is_file() => Err(usage),
        rest => {
            let (_, text) = source(rest.first().map(String::as_str))?;
            let docs = documents(&text);
            match <[String; 2]>::try_from(docs) {
                Ok([x, y]) => Ok([(a.to_string(), x), (b.to_string(), y)]),
                Err(docs) => Err(format!("{usage} (found {})", docs.len())),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fences() {
        assert_eq!(unfence("```\n<a:number>(1)\n```"), "<a:number>(1)");
        assert_eq!(unfence("```akd\n<a:number>(1)\n```"), "<a:number>(1)");
        assert_eq!(unfence("```{\"a\":1}```"), "{\"a\":1}");
        assert_eq!(
            documents("```\n{\"a\":1}\n``` ```\n{\"a\":2}\n```"),
            vec!["{\"a\":1}", "{\"a\":2}"]
        );
        assert_eq!(documents("{\"a\":1}\n{\"a\":2}").len(), 2);
        assert!(
            looks_like_data("{\"a\":1}") && looks_like_data("```x```") && looks_like_data("42")
        );
        assert!(!looks_like_data("data.json") && !looks_like_data("/tmp/x.json"));
    }

    #[test]
    fn kinds() {
        assert!(parse("{\"a\":1}", Kind::Auto).unwrap().json);
        assert!(!parse("{\"a\":1}", Kind::Akd).unwrap().json);
        assert!(parse("<a:number>(1)", Kind::Json).is_err());
    }
}
