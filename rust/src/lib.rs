//! # arkadia-data — AK-DATA (Arkadia Data Format) for Rust
//!
//! Lossless, token-efficient text for JSON data in LLM prompts, tool results
//! and agent memory: one header with the field names, then positional
//! records. Decoding always returns the original JSON. The output is the same
//! as the Python (`arkadia-data`) and npm (`@arkadia/data`) packages.
//!
//! ```
//! use arkadia_data as akd;
//! use serde_json::json;
//!
//! let data = json!({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]});
//! let text = akd::encode(&data);                       // compact, for prompts
//! assert_eq!(text, r#"<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])"#);
//! assert_eq!(akd::decode(&text).unwrap(), data);       // lossless
//!
//! // Both directions from text, e.g. in a daemon:
//! let akd_text = akd::json_to_akd(r#"{"a":[1,2]}"#, true).unwrap();
//! let json_text = akd::akd_to_json(&akd_text, false).unwrap();
//! assert_eq!(json_text, r#"{"a":[1,2]}"#);
//! ```
//!
//! The `ak-data` command line tool is built from the same crate
//! (`cargo install arkadia-data` or `make install`).

use std::fmt;

use serde_json::Value;

mod decoder;
pub mod diff;
mod encoder;
pub mod examples;
pub mod gallery;
pub mod layout;
pub mod prompt;
mod tokens;
pub mod toon;

pub use decoder::{DecodeError, Decoded};
pub use encoder::EncodeOptions;
pub use prompt::{
    assemble_prompt, build_prompt, encode_as, prompt_payload, to_prompt, Answer, Format,
    FORMAT_DEFINITION, HINT, PROMPT_WIDTH, TOON_DEFINITION,
};
pub use tokens::estimate_tokens;

/// Version of this crate.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Errors of the text-level API.
#[derive(Debug)]
pub enum Error {
    /// The input is not valid JSON.
    Json(serde_json::Error),
    /// The input is not valid AK-DATA (every error found, with positions).
    Decode(Vec<DecodeError>),
    /// Unknown format name or unsupported conversion.
    Format(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Json(e) => write!(f, "invalid JSON: {e}"),
            Error::Decode(errors) => write!(
                f,
                "invalid AK-DATA ({} error(s)): {}",
                errors.len(),
                errors
                    .first()
                    .map_or("unknown error".to_string(), |e| e.to_string())
            ),
            Error::Format(msg) => f.write_str(msg),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Json(e) => Some(e),
            _ => None,
        }
    }
}

impl From<serde_json::Error> for Error {
    fn from(e: serde_json::Error) -> Self {
        Error::Json(e)
    }
}

/// Compact single-line AK-DATA (best for prompts and tool results).
pub fn encode(value: &Value) -> String {
    encoder::encode(value, &EncodeOptions::compact())
}

/// Readable AK-DATA (header on its own line).
pub fn encode_pretty(value: &Value) -> String {
    encoder::encode(value, &EncodeOptions::pretty())
}

/// AK-DATA with explicit options.
pub fn encode_with(value: &Value, options: &EncodeOptions) -> String {
    encoder::encode(value, options)
}

/// Decodes AK-DATA; any decode error is returned as [`Error::Decode`].
pub fn decode(text: &str) -> Result<Value, Error> {
    let d = decoder::decode(text);
    if d.errors.is_empty() {
        Ok(d.value)
    } else {
        Err(Error::Decode(d.errors))
    }
}

/// Decodes AK-DATA, recovering from errors: the value plus the error list.
pub fn decode_lenient(text: &str) -> Decoded {
    decoder::decode(text)
}

fn strip_fences(text: &str) -> &str {
    let body = text.trim();
    if let Some(rest) = body.strip_prefix("```") {
        let rest = rest.split_once('\n').map_or("", |(_, r)| r);
        return rest.rsplit_once("```").map_or(rest, |(r, _)| r).trim();
    }
    body
}

/// Reads model output that may be JSON or AK-DATA (code fences allowed).
pub fn loads_any(text: &str) -> Result<Value, Error> {
    let body = strip_fences(text);
    match serde_json::from_str(body) {
        Ok(v) => Ok(v),
        Err(_) => decode(body),
    }
}

/// True when `text` (after optional code fences) parses as JSON.
pub fn is_json(text: &str) -> bool {
    serde_json::from_str::<Value>(strip_fences(text)).is_ok()
}

/// JSON text → AK-DATA text (`compact`: single line).
pub fn json_to_akd(json: &str, compact: bool) -> Result<String, Error> {
    let value: Value = serde_json::from_str(json)?;
    Ok(if compact {
        encode(&value)
    } else {
        encode_pretty(&value)
    })
}

/// AK-DATA text → JSON text (`pretty`: indented by 2).
pub fn akd_to_json(akd: &str, pretty: bool) -> Result<String, Error> {
    let value = decode(akd)?;
    Ok(if pretty {
        serde_json::to_string_pretty(&value)?
    } else {
        serde_json::to_string(&value)?
    })
}

/// Converts JSON or AK-DATA text (detected) into `to`: JSON, minified JSON,
/// TOON, AK-DATA or AK-DATA compact.
pub fn convert(text: &str, to: Format) -> Result<String, Error> {
    let value = loads_any(text)?;
    Ok(encode_as(&value, to))
}
