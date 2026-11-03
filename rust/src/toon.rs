//! TOON (Token-Oriented Object Notation) encoder, for comparing formats in
//! prompts. Follows the reference Python package (`toon-format`): tabular
//! arrays, keyed tables, nested field groups, the same quoting rules.

use serde_json::{Map, Number, Value};

/// A field list: each field is a leaf (`None`) or a nested field group.
struct Shape(Vec<(String, Option<Shape>)>);

/// Encodes a JSON value as TOON (indent 2, comma delimiter).
pub fn encode(value: &Value) -> String {
    let mut e = Toon { lines: Vec::new() };
    e.root(value);
    e.lines.join("\n")
}

const UNIT: &str = "  ";

struct Toon {
    lines: Vec<String>,
}

fn is_primitive(v: &Value) -> bool {
    !matches!(v, Value::Object(_) | Value::Array(_))
}

fn same_keys(a: &Map<String, Value>, b: &Map<String, Value>) -> bool {
    a.len() == b.len() && a.keys().all(|k| b.contains_key(k))
}

fn shape(objects: &[&Value]) -> Option<Shape> {
    let first = match objects.first() {
        Some(Value::Object(m)) if !m.is_empty() => m,
        _ => return None,
    };
    for obj in objects {
        match obj {
            Value::Object(m) if same_keys(m, first) => {}
            _ => return None,
        }
    }
    let mut fields = Vec::with_capacity(first.len());
    for key in first.keys() {
        let column: Vec<&Value> = objects
            .iter()
            .filter_map(|o| o.as_object().and_then(|m| m.get(key)))
            .collect();
        if column.iter().all(|v| is_primitive(v)) {
            fields.push((key.clone(), None));
        } else {
            fields.push((key.clone(), Some(shape(&column)?)));
        }
    }
    Some(Shape(fields))
}

fn keyed_shape(obj: &Map<String, Value>) -> Option<Shape> {
    if obj.len() < 2 {
        return None;
    }
    let values: Vec<&Value> = obj.values().collect();
    shape(&values)
}

fn leaves<'a>(obj: &'a Value, shape: &Shape, out: &mut Vec<&'a Value>) {
    for (key, nested) in &shape.0 {
        let v = &obj[key.as_str()];
        match nested {
            None => out.push(v),
            Some(n) => leaves(v, n, out),
        }
    }
}

fn is_unquoted_key(key: &str) -> bool {
    let mut chars = key.chars();
    match chars.next() {
        Some(c) if c.is_ascii_alphabetic() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
}

fn quote(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for c in value.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn encode_key(key: &str) -> String {
    if is_unquoted_key(key) {
        key.to_string()
    } else {
        quote(key)
    }
}

/// `[+-]?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?` over the whole string.
fn numeric_like(s: &str) -> bool {
    let b = s.as_bytes();
    let mut i = 0;
    if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
        i += 1;
    }
    let digits = |i: &mut usize| {
        let start = *i;
        while *i < b.len() && b[*i].is_ascii_digit() {
            *i += 1;
        }
        *i > start
    };
    if !digits(&mut i) {
        return false;
    }
    if i < b.len() && b[i] == b'.' {
        i += 1;
        if !digits(&mut i) {
            return false;
        }
    }
    if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
            i += 1;
        }
        if !digits(&mut i) {
            return false;
        }
    }
    i == b.len()
}

fn needs_quotes(value: &str) -> bool {
    let first = value.chars().next();
    let last = value.chars().last();
    value.is_empty()
        || matches!(first, Some(' ' | '\t' | '-' | '#'))
        || matches!(last, Some(' ' | '\t'))
        || matches!(value, "true" | "false" | "null")
        || value.contains(',')
        || value
            .chars()
            .any(|c| matches!(c, ':' | '"' | '\\' | '[' | ']' | '{' | '}') || (c as u32) < 0x20)
        || numeric_like(value)
}

fn encode_string(value: &str) -> String {
    if needs_quotes(value) {
        quote(value)
    } else {
        value.to_string()
    }
}

/// Canonical number form: plain decimals in [1e-6, 1e21), else `1.5e-7`.
pub(crate) fn format_float(f: f64) -> String {
    if f.fract() == 0.0 && f.abs() < 1e21 {
        return if f == 0.0 {
            "0".to_string()
        } else {
            format!("{f:.0}")
        };
    }
    let m = f.abs();
    if (1e-6..1e21).contains(&m) {
        return format!("{f}");
    }
    let e = format!("{f:e}");
    match e.split_once('e') {
        Some((mantissa, exp)) if !exp.starts_with('-') => format!("{mantissa}e+{exp}"),
        _ => e,
    }
}

fn format_number(n: &Number) -> String {
    if n.is_i64() || n.is_u64() {
        n.to_string()
    } else {
        format_float(n.as_f64().unwrap_or(0.0))
    }
}

impl Toon {
    fn emit(&mut self, depth: usize, text: &str) {
        self.lines.push(UNIT.repeat(depth) + text);
    }

    fn root(&mut self, value: &Value) {
        match value {
            Value::Object(m) => match keyed_shape(m) {
                Some(s) => self.keyed("", m, &s, 0),
                None => self.fields(m, 0),
            },
            Value::Array(a) => {
                if a.is_empty() {
                    self.emit(0, "[]");
                } else {
                    self.array("", a, 0, true);
                }
            }
            Value::String(s) if s.starts_with('\u{feff}') => {
                let q = quote(s);
                self.emit(0, &q);
            }
            other => {
                let p = primitive(other);
                self.emit(0, &p);
            }
        }
    }

    fn fields(&mut self, obj: &Map<String, Value>, depth: usize) {
        for (key, value) in obj {
            self.field(&encode_key(key), value, depth);
        }
    }

    fn field(&mut self, key: &str, value: &Value, depth: usize) {
        match value {
            Value::Object(m) => match keyed_shape(m) {
                Some(s) => self.keyed(key, m, &s, depth),
                None => {
                    self.emit(depth, &format!("{key}:"));
                    self.fields(m, depth + 1);
                }
            },
            Value::Array(a) => {
                if a.is_empty() {
                    self.emit(depth, &format!("{key}: []"));
                } else {
                    self.array(key, a, depth, true);
                }
            }
            other => {
                let p = primitive(other);
                self.emit(depth, &format!("{key}: {p}"));
            }
        }
    }

    fn array(&mut self, prefix: &str, array: &[Value], depth: usize, tabular: bool) {
        let head = format!("{prefix}[{}]", array.len());
        if array.iter().all(is_primitive) {
            let row = join(array.iter());
            self.emit(depth, &format!("{head}: {row}"));
            return;
        }
        let refs: Vec<&Value> = array.iter().collect();
        let s = if tabular { shape(&refs) } else { None };
        if let Some(s) = s {
            self.emit(depth, &format!("{head}{}:", field_list(&s)));
            for element in array {
                let mut out = Vec::new();
                leaves(element, &s, &mut out);
                let row = join(out.into_iter());
                self.emit(depth + 1, &row);
            }
            return;
        }
        self.emit(depth, &format!("{head}:"));
        for element in array {
            self.item(element, depth + 1);
        }
    }

    fn keyed(&mut self, key: &str, obj: &Map<String, Value>, s: &Shape, depth: usize) {
        self.emit(depth, &format!("{key}[{}:]{}:", obj.len(), field_list(s)));
        for (entry, value) in obj {
            let mut out = Vec::new();
            leaves(value, s, &mut out);
            let row = join(out.into_iter());
            self.emit(depth + 1, &format!("{}: {row}", encode_key(entry)));
        }
    }

    fn item(&mut self, value: &Value, depth: usize) {
        match value {
            Value::Object(m) => {
                if m.is_empty() {
                    self.emit(depth, "-");
                    return;
                }
                let first = self.lines.len();
                self.fields(m, depth + 1);
                let indent = UNIT.repeat(depth);
                let cut = indent.len() + UNIT.len();
                let rest = self.lines[first][cut..].to_string();
                self.lines[first] = format!("{indent}- {rest}");
            }
            Value::Array(a) => {
                if a.is_empty() {
                    self.emit(depth, "- [0]:");
                } else {
                    self.array("- ", a, depth, false);
                }
            }
            other => {
                let p = primitive(other);
                self.emit(depth, &format!("- {p}"));
            }
        }
    }
}

fn primitive(v: &Value) -> String {
    match v {
        Value::Null => "null".to_string(),
        Value::Bool(true) => "true".to_string(),
        Value::Bool(false) => "false".to_string(),
        Value::Number(n) => format_number(n),
        Value::String(s) => encode_string(s),
        _ => String::new(),
    }
}

fn join<'a>(values: impl Iterator<Item = &'a Value>) -> String {
    values.map(primitive).collect::<Vec<_>>().join(",")
}

fn field_list(s: &Shape) -> String {
    let entries: Vec<String> =
        s.0.iter()
            .map(|(key, nested)| {
                let mut e = encode_key(key);
                if let Some(n) = nested {
                    e.push_str(&field_list(n));
                }
                e
            })
            .collect();
    format!("{{{}}}", entries.join(","))
}
