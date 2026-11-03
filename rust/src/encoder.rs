//! JSON value → AK-DATA text.
//!
//! A line-by-line port of the TypeScript / Python encoders, so all three
//! implementations write the same text: one header with field names, then
//! positional records; values that the header cannot describe are written
//! self-describing (`{key: value}`) or carry an inline `<type>` tag, so
//! decoding always returns the original JSON.

use std::collections::HashMap;
use std::rc::Rc;

use serde_json::Value;

/// How [`encode`](crate::encode) writes AK-DATA.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EncodeOptions {
    /// Single-line form without optional spaces (best for prompts).
    pub compact: bool,
    /// Indentation of the readable form (default 2).
    pub indent: usize,
    /// Write `\n`, `\r`, `\t` inside strings as escapes (on in compact form).
    pub escape_new_lines: bool,
    /// Primitive types in headers (`id:number`); off gives `id`.
    pub include_types: bool,
    /// Structural template for model output instead of the data.
    pub prompt_output: bool,
    /// ANSI colours for terminals.
    pub colorize: bool,
    /// Write the header (`<id:number,…>`); off gives only the values / template.
    pub include_schema: bool,
    /// `Some(min)`: write the number of elements of every list with at least
    /// `min` elements as metadata, `[//$size=3// 1,2,3]` — decoders ignore it,
    /// models do not have to count. `None` (default): no sizes.
    pub array_sizes: Option<usize>,
}

impl Default for EncodeOptions {
    fn default() -> Self {
        Self::pretty()
    }
}

impl EncodeOptions {
    /// The compact single-line form (`ak-data-compact`).
    pub fn compact() -> Self {
        EncodeOptions {
            compact: true,
            indent: 2,
            escape_new_lines: true,
            include_types: true,
            prompt_output: false,
            colorize: false,
            include_schema: true,
            array_sizes: None,
        }
    }

    /// The readable form (`ak-data`).
    pub fn pretty() -> Self {
        EncodeOptions {
            compact: false,
            indent: 2,
            escape_new_lines: false,
            include_types: true,
            prompt_output: false,
            colorize: false,
            include_schema: true,
            array_sizes: None,
        }
    }
}

// ---------------------------------------------------------------------------
// Schema and node model built from JSON
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub(crate) enum Sch {
    /// "string", "number", "bool", "null" or "any".
    Prim(&'static str),
    Record(Vec<(String, Rc<Sch>)>),
    List(Rc<Sch>),
}

impl Sch {
    fn is_record(&self) -> bool {
        matches!(self, Sch::Record(_))
    }
    fn is_list(&self) -> bool {
        matches!(self, Sch::List(_))
    }
    fn is_prim(&self) -> bool {
        matches!(self, Sch::Prim(_))
    }
    fn same_kind(&self, other: &Sch) -> bool {
        std::mem::discriminant(self) == std::mem::discriminant(other)
    }
}

struct ENode<'a> {
    schema: Rc<Sch>,
    kind: Kind<'a>,
}

enum Kind<'a> {
    Prim(&'a Value),
    Record {
        fields: Vec<(&'a str, ENode<'a>)>,
        index: HashMap<&'a str, usize>,
    },
    List(Vec<ENode<'a>>),
}

impl<'a> ENode<'a> {
    fn field(&self, name: &str) -> Option<&ENode<'a>> {
        match &self.kind {
            Kind::Record { fields, index } => index.get(name).map(|&i| &fields[i].1),
            _ => None,
        }
    }
    fn has_field(&self, name: &str) -> bool {
        self.field(name).is_some()
    }
    fn key_count(&self) -> usize {
        match &self.kind {
            Kind::Record { fields, .. } => fields.len(),
            _ => 0,
        }
    }
}

/// Numbers as the Python package writes them (`repr` for floats: 199.0, 1e-07).
pub(crate) fn number(n: &serde_json::Number) -> String {
    match n.as_f64() {
        Some(f) if !(n.is_i64() || n.is_u64()) => py_float(f),
        _ => n.to_string(),
    }
}

/// Python's shortest float repr.
pub(crate) fn py_float(f: f64) -> String {
    if !f.is_finite() {
        return "null".to_string();
    }
    if f.fract() == 0.0 && f.abs() < 1e16 {
        return format!("{f:.1}");
    }
    let sci = format!("{:e}", f.abs());
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let sign = if f < 0.0 { "-" } else { "" };
    if (-4..16).contains(&exp) {
        let body = if exp >= 0 {
            let int_len = exp as usize + 1;
            let padded = format!("{digits:0<int_len$}");
            let (int, frac) = padded.split_at(int_len);
            format!("{int}.{}", if frac.is_empty() { "0" } else { frac })
        } else {
            format!("0.{}{digits}", "0".repeat((-exp - 1) as usize))
        };
        return format!("{sign}{body}");
    }
    let (first, rest) = digits.split_at(1);
    let m = if rest.is_empty() {
        first.to_string()
    } else {
        format!("{first}.{rest}")
    };
    let esign = if exp < 0 { '-' } else { '+' };
    format!("{sign}{m}e{esign}{:02}", exp.abs())
}

fn prim_type(v: &Value) -> &'static str {
    match v {
        Value::String(_) => "string",
        Value::Bool(_) => "bool",
        Value::Number(_) => "number",
        _ => "null",
    }
}

/// True when a key can be written in a header (backticks cannot be escaped).
fn header_safe(key: &str) -> bool {
    !key.contains('`')
}

/// Name of the n-th field: an empty key gets its position (as in the other
/// implementations), which makes such records self-describing.
fn field_name(key: &str, position: usize) -> String {
    if key.is_empty() {
        position.to_string()
    } else {
        key.to_string()
    }
}

fn parse(value: &Value) -> ENode<'_> {
    match value {
        Value::Array(items) => {
            if items.is_empty() {
                return ENode {
                    schema: Rc::new(Sch::List(Rc::new(Sch::Prim("any")))),
                    kind: Kind::List(Vec::new()),
                };
            }
            let nodes: Vec<ENode> = items.iter().map(parse).collect();
            let element = element_schema(&nodes);
            ENode {
                schema: Rc::new(Sch::List(element)),
                kind: Kind::List(nodes),
            }
        }
        Value::Object(map) => {
            let mut fields = Vec::with_capacity(map.len());
            let mut index = HashMap::with_capacity(map.len());
            let mut schema_fields = Vec::with_capacity(map.len());
            for (i, (key, raw)) in map.iter().enumerate() {
                let child = parse(raw);
                schema_fields.push((field_name(key, i), child.schema.clone()));
                index.insert(key.as_str(), i);
                fields.push((key.as_str(), child));
            }
            if map.keys().any(|k| !header_safe(k)) {
                // A key a header cannot spell: the record is written by name.
                schema_fields.clear();
            }
            ENode {
                schema: Rc::new(Sch::Record(schema_fields)),
                kind: Kind::Record { fields, index },
            }
        }
        other => ENode {
            schema: Rc::new(Sch::Prim(prim_type(other))),
            kind: Kind::Prim(other),
        },
    }
}

/// The most frequent non-null primitive type (first seen wins ties).
fn common_type<'s>(schemas: impl Iterator<Item = &'s Sch>) -> Option<&'static str> {
    let mut counts: Vec<(&'static str, usize)> = Vec::new();
    for s in schemas {
        if let Sch::Prim(t) = s {
            if *t != "null" {
                match counts.iter_mut().find(|(k, _)| k == t) {
                    Some(entry) => entry.1 += 1,
                    None => counts.push((t, 1)),
                }
            }
        }
    }
    let mut best = None;
    let mut n = 0;
    for (t, c) in counts {
        if c > n {
            best = Some(t);
            n = c;
        }
    }
    best
}

fn headerable(node: &ENode) -> bool {
    match &node.kind {
        Kind::Record { fields, .. } => fields.iter().all(|(k, _)| header_safe(k)),
        _ => true,
    }
}

fn sorted_keys(node: &ENode) -> Vec<String> {
    let mut keys: Vec<String> = match &node.kind {
        Kind::Record { fields, .. } => fields.iter().map(|(k, _)| k.to_string()).collect(),
        _ => Vec::new(),
    };
    keys.sort();
    keys
}

/// The header schema of a list (majority layout for lists of records).
fn element_schema(items: &[ENode]) -> Rc<Sch> {
    let first = &items[0].schema;
    match first.as_ref() {
        Sch::Prim(t) => {
            if let Some(common) = common_type(items.iter().map(|i| i.schema.as_ref())) {
                if common != *t {
                    return Rc::new(Sch::Prim(common));
                }
            }
            first.clone()
        }
        Sch::List(_) => first.clone(),
        Sch::Record(_) => {
            let mut counts: Vec<(Vec<String>, usize, usize)> = Vec::new(); // keys, count, first index
            for (i, item) in items.iter().enumerate() {
                if !item.schema.is_record() || !headerable(item) {
                    continue;
                }
                let keys = sorted_keys(item);
                match counts.iter_mut().find(|(k, _, _)| *k == keys) {
                    Some(entry) => entry.1 += 1,
                    None => counts.push((keys, 1, i)),
                }
            }
            let mut best: Option<&(Vec<String>, usize, usize)> = None;
            for entry in &counts {
                if best.map_or(true, |b| entry.1 > b.1) {
                    best = Some(entry);
                }
            }
            let (best_keys, best_count, layout_at) = match best {
                Some(b) => (b.0.clone(), b.1, b.2),
                None => return Rc::new(Sch::Prim("any")),
            };
            let exact = (best_count >= 2 || items.len() == 1) && best_count * 2 >= items.len();
            if let Some((schema, fitting)) = union_schema(items) {
                if fitting > if exact { best_count } else { 0 } {
                    return schema;
                }
            }
            if exact {
                let fitting: Vec<&ENode> = items
                    .iter()
                    .filter(|i| {
                        i.schema.is_record() && headerable(i) && sorted_keys(i) == best_keys
                    })
                    .collect();
                let layout = match items[layout_at].schema.as_ref() {
                    Sch::Record(f) => f,
                    _ => unreachable!(),
                };
                let mut fields = Vec::with_capacity(layout.len());
                for (name, field) in layout {
                    let mut field = field.clone();
                    if let Sch::Prim(t) = field.as_ref() {
                        let common = common_type(
                            fitting
                                .iter()
                                .filter_map(|i| i.field(name))
                                .map(|n| n.schema.as_ref()),
                        );
                        if let Some(common) = common {
                            if common != *t {
                                field = Rc::new(Sch::Prim(common));
                            }
                        }
                    }
                    fields.push((name.clone(), field));
                }
                Rc::new(Sch::Record(fields))
            } else {
                Rc::new(Sch::Prim("any"))
            }
        }
    }
}

/// The record's keys are exactly the first k names of a header (k >= 1).
fn prefix_fits(item: &ENode, names: &[String]) -> bool {
    let k = item.key_count();
    k >= 1 && k <= names.len() && names[..k].iter().all(|n| item.has_field(n))
}

/// A header with every field of the records — the most frequent first — under
/// which a record whose keys are its first k fields is written positionally
/// with k values (the decoder leaves the missing trailing fields out). `None`
/// when fewer than two records, or fewer than half of the list, fit.
fn union_schema(items: &[ENode]) -> Option<(Rc<Sch>, usize)> {
    // Records whose every key a header can spell (an empty key cannot be).
    let records: Vec<&ENode> = items
        .iter()
        .filter(|i| {
            i.schema.is_record()
                && headerable(i)
                && match &i.kind {
                    Kind::Record { fields, .. } => fields.iter().all(|(k, _)| !k.is_empty()),
                    _ => false,
                }
        })
        .collect();
    if records.len() < 2 {
        return None;
    }
    // name, frequency, first-seen schema (in order of first appearance)
    let mut seen: Vec<(String, usize, Rc<Sch>)> = Vec::new();
    for r in &records {
        if let Kind::Record { fields, .. } = &r.kind {
            for (name, child) in fields {
                match seen.iter_mut().find(|(n, _, _)| n == name) {
                    Some(entry) => entry.1 += 1,
                    None => seen.push((name.to_string(), 1, child.schema.clone())),
                }
            }
        }
    }
    let mut order: Vec<usize> = (0..seen.len()).collect();
    order.sort_by(|&a, &b| seen[b].1.cmp(&seen[a].1).then(a.cmp(&b)));
    let names: Vec<String> = order.iter().map(|&i| seen[i].0.clone()).collect();
    let fitting = records.iter().filter(|r| prefix_fits(r, &names)).count();
    if fitting < 2 || fitting * 2 < items.len() {
        return None;
    }
    let mut fields = Vec::with_capacity(names.len());
    for &i in &order {
        let (name, _, schema) = &seen[i];
        let mut field = schema.clone();
        if let Sch::Prim(t) = field.as_ref() {
            let common = common_type(
                records
                    .iter()
                    .filter_map(|r| r.field(name))
                    .map(|n| n.schema.as_ref()),
            );
            if let Some(common) = common {
                if common != *t {
                    field = Rc::new(Sch::Prim(common));
                }
            }
        }
        fields.push((name.clone(), field));
    }
    Some((Rc::new(Sch::Record(fields)), fitting))
}

// ---------------------------------------------------------------------------
// Encoder
// ---------------------------------------------------------------------------

const RESET: &str = "\x1b[0m";
const C_STRING: &str = "\x1b[92m";
const C_NUMBER: &str = "\x1b[94m";
const C_BOOL: &str = "\x1b[95m";
const C_NULL: &str = "\x1b[90m";
const C_TYPE: &str = "\x1b[96m";
const C_KEY: &str = "\x1b[93m";
const C_SCHEMA: &str = "\x1b[91m";

pub(crate) struct Encoder<'o> {
    o: &'o EncodeOptions,
}

/// Encodes a JSON value as AK-DATA.
pub fn encode(value: &Value, options: &EncodeOptions) -> String {
    let node = parse(value);
    Encoder { o: options }.root(&node)
}

fn is_open(expected: Option<&Sch>) -> bool {
    match expected {
        None => true,
        Some(Sch::Record(f)) => f.is_empty(),
        Some(Sch::Prim(t)) => *t == "any",
        Some(Sch::List(_)) => false,
    }
}

fn compatible(node: &Sch, expected: Option<&Sch>) -> bool {
    if is_open(expected) {
        return true;
    }
    let expected = expected.unwrap();
    if let (Sch::Prim("null"), Sch::Prim(_)) = (node, expected) {
        return true;
    }
    if !node.same_kind(expected) {
        return false;
    }
    match (node, expected) {
        (Sch::Prim(a), Sch::Prim(b)) => a == b,
        _ => true,
    }
}

fn is_ident(name: &str) -> bool {
    let mut chars = name.chars();
    match chars.next() {
        Some(c) if c.is_ascii_alphabetic() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// A record key as a quoted string, for keys a backtick name cannot hold.
fn quoted_key(key: &str) -> String {
    let mut out = String::from("\"");
    for ch in key.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn escape_ident(name: &str) -> String {
    if name.is_empty() {
        "\"\"".to_string()
    } else if is_ident(name) {
        name.to_string()
    } else {
        format!("`{name}`")
    }
}

impl Encoder<'_> {
    fn c(&self, text: &str, color: &str) -> String {
        if self.o.colorize {
            format!("{color}{text}{RESET}")
        } else {
            text.to_string()
        }
    }

    fn pad(&self) -> &'static str {
        if self.o.compact {
            ""
        } else {
            " "
        }
    }

    fn sep(&self) -> &'static str {
        if self.o.compact {
            ","
        } else {
            ", "
        }
    }

    fn root(&self, node: &ENode) -> String {
        let mut prefix = String::new();
        let mut s = if self.o.include_schema {
            self.schema(&node.schema).trim().to_string()
        } else {
            String::new()
        };
        if !s.is_empty() && !s.starts_with('<') && !s.starts_with('@') {
            s = format!("<{s}>");
        }
        if !s.is_empty() {
            prefix = if self.o.compact { s } else { s + "\n" };
        }
        let headerless =
            matches!(node.schema.as_ref(), Sch::Record(f) if f.is_empty()) && node.key_count() > 0;
        if node.schema.is_record()
            && !self.o.prompt_output
            && (headerless || !self.fits(node, Some(&node.schema)))
        {
            return self.named(node);
        }
        let data = match &node.kind {
            Kind::List(_) => self.list(node, 0),
            Kind::Prim(v) => self.primitive(v),
            Kind::Record { .. } => self.record(node, 0, None),
        };
        prefix + &data
    }

    // --- headers ---------------------------------------------------------

    fn schema(&self, schema: &Sch) -> String {
        let pad = self.pad();
        match schema {
            Sch::Prim(t) => self.c(&escape_ident(t), C_TYPE),
            Sch::List(element) => {
                if let Sch::Record(fields) = element.as_ref() {
                    format!("<{pad}[{}{pad}]{pad}>", self.schema_fields(fields))
                } else {
                    let inner = self.schema(element).trim().to_string();
                    format!("[{}]", self.c(&inner, C_TYPE))
                }
            }
            Sch::Record(fields) => {
                if fields.is_empty() {
                    String::new()
                } else {
                    format!("<{pad}{}{pad}>", self.schema_fields(fields))
                }
            }
        }
    }

    fn schema_fields(&self, fields: &[(String, Rc<Sch>)]) -> String {
        let pad = self.pad();
        let parts: Vec<String> = fields
            .iter()
            .map(|(name, field)| {
                let mut s = self.c(&escape_ident(name), C_KEY);
                let field_type = self.schema(field).trim().to_string();
                let structure = !field.is_prim();
                let explicit = self.o.include_types && !matches!(field.as_ref(), Sch::Prim("any"));
                if !field_type.is_empty() && (structure || explicit) {
                    s.push(':');
                    s.push_str(&self.c(&field_type, C_TYPE));
                }
                s
            })
            .collect();
        parts.join(&format!(",{pad}"))
    }

    fn type_label(schema: &Sch) -> String {
        match schema {
            Sch::Prim(t) => escape_ident(t),
            Sch::List(el) => format!("[{}]", Self::type_label(el)),
            Sch::Record(_) => "any".to_string(),
        }
    }

    // --- values ----------------------------------------------------------

    fn primitive(&self, v: &Value) -> String {
        match v {
            Value::String(s) => self.string(s),
            Value::Bool(true) => self.c("true", C_BOOL),
            Value::Bool(false) => self.c("false", C_BOOL),
            Value::Number(n) => self.c(&number(n), C_NUMBER),
            _ => self.c("null", C_NULL),
        }
    }

    fn string(&self, v: &str) -> String {
        let mut out = String::with_capacity(v.len() + 2);
        out.push('"');
        for ch in v.chars() {
            match ch {
                '\\' => out.push_str("\\\\"),
                '"' => out.push_str("\\\""),
                '\n' if self.o.escape_new_lines => out.push_str("\\n"),
                '\r' if self.o.escape_new_lines => out.push_str("\\r"),
                '\t' if self.o.escape_new_lines => out.push_str("\\t"),
                c => out.push(c),
            }
        }
        out.push('"');
        self.c(&out, C_STRING)
    }

    fn fits(&self, node: &ENode, expected: Option<&Sch>) -> bool {
        if is_open(expected) {
            return true;
        }
        let expected = expected.unwrap();
        match &node.kind {
            Kind::Record { .. } => match expected {
                Sch::Record(fields) => {
                    // Same names as the header, or as its first k fields (the
                    // decoder leaves the missing trailing fields out).
                    let k = node.key_count();
                    k >= 1
                        && k <= fields.len()
                        && fields[..k].iter().all(|(n, _)| node.has_field(n))
                        && fields
                            .iter()
                            .enumerate()
                            .all(|(i, (n, _))| fields[..i].iter().all(|(m, _)| m != n))
                }
                _ => false,
            },
            Kind::List(_) => expected.is_list(),
            Kind::Prim(_) => true,
        }
    }

    fn tagged(&self, label: &str, value: String) -> String {
        format!("{} {value}", self.c(&format!("<{label}>"), C_SCHEMA))
    }

    fn element_value(&self, el: &ENode, expected: Option<&Sch>) -> String {
        match &el.kind {
            Kind::Prim(v) => {
                let val = self.primitive(v).trim().to_string();
                if compatible(&el.schema, expected) {
                    val
                } else {
                    self.tagged(&Self::type_label(&el.schema), val)
                }
            }
            _ => self.value(el, expected),
        }
    }

    fn named(&self, node: &ENode) -> String {
        let fields = match &node.kind {
            Kind::Record { fields, .. } => fields,
            _ => unreachable!(),
        };
        let colon = if self.o.compact { ":" } else { ": " };
        let items: Vec<String> = fields
            .iter()
            .map(|(key, child)| {
                let k = if header_safe(key) {
                    escape_ident(key)
                } else {
                    quoted_key(key)
                };
                format!("{}{colon}{}", self.c(&k, C_KEY), self.value(child, None))
            })
            .collect();
        format!("{{{}}}", items.join(self.sep()))
    }

    /// `$size=N` metadata of a list (with `array_sizes`), as the Python
    /// encoder wraps it: `//$size=N// ` compact, `// $size=N //` readable.
    fn size_meta(&self, len: usize) -> String {
        match self.o.array_sizes {
            Some(min) if len >= min => {
                if self.o.compact {
                    format!("{} ", self.c(&format!("//$size={len}//"), C_SCHEMA))
                } else {
                    self.c(&format!("// $size={len} //"), C_SCHEMA)
                }
            }
            _ => String::new(),
        }
    }

    fn list_values(&self, node: &ENode, element: Option<&Sch>) -> String {
        let elements = match &node.kind {
            Kind::List(e) => e,
            _ => unreachable!(),
        };
        let items: Vec<String> = elements
            .iter()
            .map(|el| self.element_value(el, element))
            .collect();
        format!(
            "[{}{}]",
            self.size_meta(elements.len()),
            items.join(self.sep())
        )
    }

    fn value(&self, node: &ENode, expected: Option<&Sch>) -> String {
        let open = is_open(expected);
        let any_tag = self.c("<any>", C_SCHEMA) + " ";
        match &node.kind {
            Kind::Record { .. } => {
                if !open && self.fits(node, expected) {
                    return self.record(node, 0, expected);
                }
                let named = self.named(node);
                if open {
                    named
                } else {
                    any_tag + &named
                }
            }
            Kind::List(elements) => {
                if !open {
                    if let Some(Sch::List(el)) = expected {
                        return self.list_values(node, Some(el));
                    }
                }
                if let Sch::List(element) = node.schema.as_ref() {
                    let element = element.as_ref();
                    if !is_open(Some(element))
                        && elements.iter().all(|e| self.fits(e, Some(element)))
                        && (element.is_record() || !open)
                        && !(element.is_record() && elements.len() < 2)
                    {
                        let mut tag = self.schema(&node.schema).trim().to_string();
                        if !tag.starts_with('<') {
                            tag = format!("<{tag}>");
                        }
                        return format!(
                            "{} {}",
                            self.c(&tag, C_SCHEMA),
                            self.list_values(node, Some(element))
                        );
                    }
                }
                let body = self.list_values(node, None);
                if open {
                    body
                } else {
                    any_tag + &body
                }
            }
            Kind::Prim(v) => {
                let val = self.primitive(v).trim().to_string();
                if compatible(&node.schema, expected) {
                    val
                } else {
                    self.tagged(&Self::type_label(&node.schema), val)
                }
            }
        }
    }

    // --- root list and records ---------------------------------------------

    fn list(&self, node: &ENode, indent: usize) -> String {
        let ind = " ".repeat(indent);
        let child = indent + self.o.indent;
        let element = match node.schema.as_ref() {
            Sch::List(el) => el.clone(),
            _ => unreachable!(),
        };
        if self.o.prompt_output {
            return self.list_prompt(&element, indent);
        }
        let elements = match &node.kind {
            Kind::List(e) => e,
            _ => unreachable!(),
        };
        let meta = self.size_meta(elements.len());
        if self.o.compact {
            let items: Vec<String> = elements
                .iter()
                .map(|el| self.element_value(el, Some(&element)))
                .collect();
            return format!("{ind}[{meta}{}]", items.join(","));
        }
        let mut res = format!("{ind}[\n");
        if !meta.is_empty() {
            res.push_str(&" ".repeat(child));
            res.push_str(&meta);
            res.push('\n');
        }
        let lines: Vec<String> = elements
            .iter()
            .map(|el| " ".repeat(child) + &self.element_value(el, Some(&element)))
            .collect();
        if !lines.is_empty() {
            res.push_str(&lines.join(",\n"));
            res.push('\n');
        }
        res.push_str(&ind);
        res.push(']');
        res
    }

    fn record(&self, node: &ENode, indent: usize, expected: Option<&Sch>) -> String {
        let layout: &Sch = match expected {
            Some(e @ Sch::Record(_)) => e,
            _ => &node.schema,
        };
        let fields = match layout {
            Sch::Record(f) => f,
            _ => unreachable!(),
        };
        if self.o.prompt_output {
            return self.record_prompt(fields, indent);
        }
        // A record that has only the first k fields of the header is written
        // with k values (missing trailing fields stay absent).
        let fields = match fields.iter().rposition(|(name, _)| node.has_field(name)) {
            Some(last) => &fields[..=last],
            None => &fields[..],
        };
        let parts: Vec<String> = if !fields.is_empty() {
            fields
                .iter()
                .map(|(name, def)| match node.field(name) {
                    Some(child) => self.value(child, Some(def)),
                    None => self.c("null", C_NULL),
                })
                .collect()
        } else if node.key_count() == 0 {
            return "{}".to_string();
        } else {
            vec![self.c("null", C_NULL)]
        };
        format!("({})", parts.join(self.sep()))
    }

    // --- prompt-output templates -----------------------------------------------

    fn prompt_value(&self, schema: &Sch, indent: usize) -> String {
        match schema {
            Sch::List(el) => self.list_prompt(el, indent),
            Sch::Record(fields) => self.record_prompt(fields, indent),
            Sch::Prim(_) => self.c("null", C_NULL),
        }
    }

    fn list_prompt(&self, element: &Sch, indent: usize) -> String {
        let ind = " ".repeat(indent);
        let child = indent + self.o.indent;
        let pad = " ".repeat(child);
        let blueprint = self.prompt_value(element, child).trim().to_string();
        format!(
            "{ind}[\n{pad}{blueprint},\n{pad}... /* repeat pattern for additional items */\n{ind}]"
        )
    }

    fn record_prompt(&self, fields: &[(String, Rc<Sch>)], indent: usize) -> String {
        let base = " ".repeat(indent);
        let child_indent = indent + self.o.indent;
        let child = " ".repeat(child_indent);
        let parts: Vec<String> = if fields.is_empty() {
            vec![self.c("null", C_NULL)]
        } else {
            fields
                .iter()
                .map(|(name, def)| {
                    let structure = if def.is_prim() {
                        self.c(&Self::type_label(def), C_TYPE)
                    } else {
                        self.prompt_value(def, child_indent).trim().to_string()
                    };
                    format!("{}: {structure}", self.c(&escape_ident(name), C_KEY))
                })
                .collect()
        };
        format!(
            "{{\n{child}{}\n{base}}}",
            parts.join(&format!(",\n{child}"))
        )
    }
}
