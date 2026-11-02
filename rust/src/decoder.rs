//! AK-DATA text → JSON value.
//!
//! A port of the TypeScript / Python decoders (same grammar, same recovery
//! rules). Metadata — `/* comments */`, `$attr=…`, `#tags`, `// … //` blocks
//! — is read and skipped: it is not data.

use std::cell::RefCell;
use std::fmt;
use std::rc::Rc;

use serde_json::{Map, Number, Value};

/// One problem found while decoding; decoding continues after it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodeError {
    pub message: String,
    /// Character offset in the input.
    pub position: usize,
}

impl fmt::Display for DecodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} (at pos {})", self.message, self.position)
    }
}

/// The decoded value and every error met on the way (empty when valid).
#[derive(Debug, Clone, PartialEq)]
pub struct Decoded {
    pub value: Value,
    pub errors: Vec<DecodeError>,
}

const MAX_ERRORS: usize = 50;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum K {
    Prim,
    Record,
    List,
    Any,
}

#[derive(Debug)]
struct DSchema {
    kind: K,
    type_name: String,
    name: String,
    element: Option<SRef>,
    fields: Vec<SRef>,
}

type SRef = Rc<RefCell<DSchema>>;

fn schema(kind: K, type_name: &str) -> SRef {
    Rc::new(RefCell::new(DSchema {
        kind,
        type_name: if type_name.is_empty() {
            "any".to_string()
        } else {
            type_name.to_string()
        },
        name: String::new(),
        element: None,
        fields: Vec::new(),
    }))
}

fn add_field(s: &SRef, field: SRef) {
    let mut b = s.borrow_mut();
    if b.kind != K::Record {
        b.kind = K::Record;
    }
    let len = b.fields.len();
    {
        let mut f = field.borrow_mut();
        if f.name.is_empty() {
            f.name = len.to_string();
        }
    }
    b.fields.push(field);
}

fn get_field(s: &SRef, name: &str) -> Option<SRef> {
    s.borrow()
        .fields
        .iter()
        .find(|f| f.borrow().name == name)
        .cloned()
}

fn replace_field(s: &SRef, field: SRef) {
    let name = field.borrow().name.clone();
    let pos = s
        .borrow()
        .fields
        .iter()
        .position(|f| f.borrow().name == name);
    match pos {
        Some(i) => s.borrow_mut().fields[i] = field,
        None => add_field(s, field),
    }
}

fn is_any(s: &SRef) -> bool {
    let b = s.borrow();
    b.kind == K::Any || (b.type_name == "any" && matches!(b.kind, K::Prim | K::Record))
}

fn is_bare_any(s: &SRef) -> bool {
    let b = s.borrow();
    if b.kind != K::Record || b.fields.len() != 1 {
        return false;
    }
    let f = b.fields[0].borrow();
    f.name == "any" && f.kind == K::Prim && f.type_name == "any"
}

/// A copy of a schema for one value (fields and element are shared).
fn fork(s: &SRef) -> SRef {
    let b = s.borrow();
    let own = Rc::new(RefCell::new(DSchema {
        kind: b.kind,
        type_name: b.type_name.clone(),
        name: b.name.clone(),
        element: b.element.clone(),
        fields: Vec::new(),
    }));
    for f in &b.fields {
        // As addField in the other implementations: fields make it a record.
        own.borrow_mut().kind = K::Record;
        let len = own.borrow().fields.len();
        if f.borrow().name.is_empty() {
            f.borrow_mut().name = len.to_string();
        }
        own.borrow_mut().fields.push(f.clone());
    }
    own
}

fn primitive_type(name: &str) -> Option<&'static str> {
    Some(match name {
        "string" => "string",
        "bool" => "bool",
        "number" | "int" | "float" => "number",
        "null" => "null",
        "binary" => "binary",
        _ => return None,
    })
}

struct DNode {
    schema: SRef,
    value: Value,
    fields: Vec<(String, DNode)>,
    elements: Vec<DNode>,
}

impl DNode {
    fn set_field(&mut self, name: String, node: DNode) {
        match self.fields.iter_mut().find(|(k, _)| *k == name) {
            Some(slot) => slot.1 = node,
            None => self.fields.push((name, node)),
        }
    }

    fn into_value(self) -> Value {
        let kind = self.schema.borrow().kind;
        match kind {
            K::Prim | K::Any => self.value,
            K::List => Value::Array(self.elements.into_iter().map(DNode::into_value).collect()),
            K::Record => {
                let mut map = Map::new();
                for (k, v) in self.fields {
                    map.insert(k, v.into_value());
                }
                Value::Object(map)
            }
        }
    }
}

pub(crate) struct Decoder {
    text: Vec<char>,
    i: usize,
    schemas: Vec<SRef>,
    errors: Vec<DecodeError>,
    named: Vec<(String, SRef)>,
}

/// Removes ANSI colour codes (`ESC [ … m`).
pub(crate) fn strip_ansi(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '\x1b' && chars.get(i + 1) == Some(&'[') {
            let mut j = i + 2;
            while j < chars.len() && (chars[j].is_ascii_digit() || chars[j] == ';') {
                j += 1;
            }
            if chars.get(j) == Some(&'m') {
                i = j + 1;
                continue;
            }
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

/// Decodes AK-DATA text; errors are collected, never thrown.
pub fn decode(text: &str) -> Decoded {
    let clean = strip_ansi(text);
    let mut d = Decoder {
        text: clean.chars().collect(),
        i: 0,
        schemas: Vec::new(),
        errors: Vec::new(),
        named: Vec::new(),
    };
    let value = d.run();
    Decoded {
        value,
        errors: d.errors,
    }
}

impl Decoder {
    // --- cursor ----------------------------------------------------------

    fn eof(&self) -> bool {
        self.i >= self.text.len()
    }
    fn peek(&self) -> Option<char> {
        self.text.get(self.i).copied()
    }
    fn peek_next(&self) -> Option<char> {
        self.text.get(self.i + 1).copied()
    }
    fn advance(&mut self, n: usize) {
        self.i = (self.i + n).min(self.text.len());
    }
    fn skip_ws(&mut self) {
        while let Some(c) = self.peek() {
            if c.is_whitespace() {
                self.i += 1;
            } else {
                break;
            }
        }
    }
    fn expect(&mut self, ch: char) -> bool {
        if self.peek() != Some(ch) {
            let got = self.peek().map_or("null".to_string(), |c| c.to_string());
            self.error(format!("Expected '{ch}', got '{got}'"));
            return false;
        }
        self.advance(1);
        true
    }
    fn error(&mut self, message: String) {
        if self.errors.len() < MAX_ERRORS {
            self.errors.push(DecodeError {
                message,
                position: self.i,
            });
        }
    }

    // --- schema stack ------------------------------------------------------

    fn current(&self) -> Option<SRef> {
        self.schemas.last().cloned()
    }
    fn push(&mut self, s: SRef) {
        self.schemas.push(s);
    }
    fn pop(&mut self) {
        self.schemas.pop();
    }
    fn create_schema(&mut self, kind: K, type_name: &str) -> SRef {
        let s = schema(kind, type_name);
        self.push(s.clone());
        s
    }
    fn named_schema(&self, name: &str) -> Option<SRef> {
        self.named
            .iter()
            .find(|(n, _)| n == name)
            .map(|(_, s)| s.clone())
    }
    fn set_named(&mut self, name: String, s: SRef) {
        match self.named.iter_mut().find(|(n, _)| *n == name) {
            Some(slot) => slot.1 = s,
            None => self.named.push((name, s)),
        }
    }

    // --- entry -----------------------------------------------------------

    fn run(&mut self) -> Value {
        self.parse_meta();
        let mut root_schema: Option<SRef> = None;
        while !self.eof() {
            match self.peek() {
                Some('<') => {
                    root_schema = Some(self.parse_schema_body(""));
                    self.parse_meta();
                    if matches!(self.peek(), Some('(' | '{' | '[')) {
                        break;
                    }
                }
                Some('@') => {
                    let s = self.parse_schema_at_ref();
                    self.parse_meta();
                    if matches!(self.peek(), Some('@' | '<')) {
                        continue;
                    }
                    root_schema = Some(s);
                    break;
                }
                _ => break,
            }
        }
        if let Some(s) = &root_schema {
            self.push(s.clone());
        }
        let mut root = if self.eof() {
            self.create_node(None)
        } else {
            self.parse_node()
        };
        if let Some(s) = root_schema {
            self.pop();
            if is_any(&root.schema) {
                root.schema = s;
            }
        }
        self.parse_meta();
        root.into_value()
    }

    // --- schemas -----------------------------------------------------------

    fn parse_schema_at_ref(&mut self) -> SRef {
        self.advance(1); // @
        let type_name = self.parse_ident();
        self.skip_ws();
        if self.peek() == Some('<') {
            let s = self.parse_schema_body(&type_name);
            if is_any(&s) {
                s.borrow_mut().kind = K::Record;
            }
            self.set_named(type_name, s.clone());
            return s;
        }
        if let Some(s) = self.named_schema(&type_name) {
            return s;
        }
        schema(K::Record, &type_name)
    }

    fn parse_schema_body(&mut self, type_name: &str) -> SRef {
        if !self.expect('<') {
            let s = self.create_schema(K::Any, type_name);
            self.pop();
            return s;
        }
        let s = self.create_schema(K::Record, type_name);
        self.parse_schema_content(&s, '>');
        self.pop();
        s
    }

    fn parse_schema_content(&mut self, s: &SRef, end: char) {
        while !self.eof() {
            self.parse_meta();
            let ch = match self.peek() {
                Some(c) => c,
                None => {
                    self.error("Expected identifier".to_string());
                    break;
                }
            };
            if ch == end {
                self.advance(1);
                break;
            }
            if ch == '[' {
                self.advance(1);
                {
                    let mut b = s.borrow_mut();
                    b.kind = K::List;
                    b.fields.clear();
                }
                let element = schema(K::Any, "");
                self.parse_schema_content(&element, ']');
                s.borrow_mut().element = Some(element);
                self.parse_meta();
                if self.peek() == Some(end) {
                    self.advance(1);
                }
                return;
            }
            if ch == '<' && end == ']' {
                let inner = self.parse_schema_body("");
                let (kind, type_name, element, fields) = {
                    let b = inner.borrow();
                    (
                        b.kind,
                        b.type_name.clone(),
                        b.element.clone(),
                        b.fields.clone(),
                    )
                };
                {
                    let mut b = s.borrow_mut();
                    b.kind = kind;
                    b.type_name = type_name;
                    b.element = element;
                    b.fields.clear();
                }
                for f in fields {
                    add_field(s, f);
                }
                continue;
            }
            if ch == ',' {
                self.advance(1);
                continue;
            }
            let name = self.parse_ident();
            if name.is_empty() {
                self.error("Expected identifier".to_string());
                self.advance(1);
                continue;
            }
            self.skip_ws();
            if let Some(t) = primitive_type(&name) {
                if self.peek() != Some(':') {
                    let mut b = s.borrow_mut();
                    b.kind = K::Prim;
                    b.type_name = t.to_string();
                    continue;
                }
            }
            if name == "any" && end == ']' && self.peek() != Some(':') {
                let mut b = s.borrow_mut();
                b.kind = K::Prim;
                b.type_name = "any".to_string();
                continue;
            }
            let mut field = if self.peek() == Some(':') {
                self.advance(1);
                self.parse_schema_type()
            } else {
                schema(K::Prim, "any")
            };
            // A named type (@User) is shared: each field using it gets its own
            // copy, so naming this field does not rename the others.
            if self.named.iter().any(|(_, s)| Rc::ptr_eq(s, &field)) {
                field = fork(&field);
            }
            field.borrow_mut().name = name;
            self.parse_meta();
            add_field(s, field);
        }
    }

    fn parse_schema_type(&mut self) -> SRef {
        self.parse_meta();
        match self.peek() {
            Some('[') => {
                self.advance(1);
                let list = schema(K::List, "");
                let element = self.parse_schema_type();
                list.borrow_mut().element = Some(element);
                self.expect(']');
                list
            }
            Some('@') => {
                self.advance(1);
                let name = self.parse_ident();
                self.parse_meta();
                if self.peek() == Some('<') {
                    let s = self.parse_schema_body(&name);
                    if is_any(&s) {
                        s.borrow_mut().kind = K::Record;
                    }
                    self.set_named(name, s.clone());
                    return s;
                }
                self.named_schema(&name)
                    .unwrap_or_else(|| schema(K::Record, &name))
            }
            Some('<') => self.parse_schema_body(""),
            _ => {
                let name = self.parse_ident();
                if let Some(t) = primitive_type(&name) {
                    return schema(K::Prim, t);
                }
                if name == "any" {
                    return schema(K::Prim, "any");
                }
                if let Some(s) = self.named_schema(&name) {
                    return s;
                }
                if name.is_empty() {
                    return schema(K::Any, "");
                }
                schema(K::Record, &name)
            }
        }
    }

    // --- nodes -------------------------------------------------------------

    fn create_node(&mut self, value: Option<Value>) -> DNode {
        let current = match self.current() {
            Some(s) => s,
            None => {
                let s = schema(K::Any, "");
                self.push(s.clone());
                s
            }
        };
        let final_schema = match &value {
            Some(v) => {
                let inferred = match v {
                    Value::Bool(_) => "bool",
                    Value::Number(_) => "number",
                    _ => "string",
                };
                let (kind, type_name) = {
                    let b = current.borrow();
                    (b.kind, b.type_name.clone())
                };
                if kind != K::Any && type_name == inferred {
                    current.clone()
                } else {
                    schema(K::Prim, inferred)
                }
            }
            None => {
                let kind = current.borrow().kind;
                if matches!(kind, K::Record | K::List) {
                    current.clone()
                } else {
                    schema(K::Prim, "null")
                }
            }
        };
        DNode {
            schema: final_schema,
            value: value.unwrap_or(Value::Null),
            fields: Vec::new(),
            elements: Vec::new(),
        }
    }

    fn parse_node(&mut self) -> DNode {
        self.parse_meta();
        let ch = match self.peek() {
            Some(c) => c,
            None => {
                self.error("Unexpected EOF while expecting a node".to_string());
                return self.create_node(None);
            }
        };
        match ch {
            '@' => self.parse_node_with_ref(),
            '<' => self.parse_node_with_inline_schema(),
            '[' => self.parse_list(),
            '(' => self.parse_positional_record(),
            '{' => self.parse_named_record(),
            '"' => {
                let s = self.read_quoted_string();
                self.create_node(Some(Value::String(s)))
            }
            c if c.is_ascii_digit() || c == '-' => {
                let n = self.read_number();
                self.create_node(Some(n))
            }
            c if c.is_ascii_alphabetic() || c == '_' => {
                let raw = self.parse_ident();
                match raw.as_str() {
                    "true" => self.create_node(Some(Value::Bool(true))),
                    "false" => self.create_node(Some(Value::Bool(false))),
                    "null" => self.create_node(None),
                    _ => self.create_node(Some(Value::String(raw))),
                }
            }
            c => {
                self.error(format!("Unexpected character '{c}'"));
                self.advance(1);
                self.create_node(None)
            }
        }
    }

    fn parse_node_with_ref(&mut self) -> DNode {
        let s = self.parse_schema_at_ref();
        self.push(s.clone());
        let mut node = self.parse_node();
        self.pop();
        node.schema = s;
        node
    }

    fn parse_node_with_inline_schema(&mut self) -> DNode {
        let s = self.parse_schema_body("");
        if is_bare_any(&s) {
            self.skip_ws();
            if matches!(self.peek(), Some('{' | '[')) {
                self.push(schema(K::Any, ""));
                let node = self.parse_node();
                self.pop();
                return node;
            }
        }
        self.push(s.clone());
        let mut node = self.parse_node();
        self.pop();
        node.schema = s;
        node
    }

    fn parse_list(&mut self) -> DNode {
        self.advance(1); // [
        let mut node = self.create_node(None);
        {
            let mut b = node.schema.borrow_mut();
            if b.kind != K::List {
                b.kind = K::List;
                b.type_name = "list".to_string();
                b.element = Some(schema(K::Any, ""));
            }
        }
        let parent = node.schema.clone();
        let child_schema = parent
            .borrow()
            .element
            .clone()
            .unwrap_or_else(|| schema(K::Any, ""));
        loop {
            self.parse_meta();
            self.push(fork(&child_schema));
            if self.eof() {
                self.error("Unexpected EOF: List not closed".to_string());
                break;
            }
            match self.peek() {
                Some(']') => {
                    self.advance(1);
                    break;
                }
                Some(',') => {
                    self.advance(1);
                    continue;
                }
                _ => {}
            }
            let child = self.parse_node();
            let replace = parent.borrow().element.as_ref().is_some_and(is_any);
            if replace {
                parent.borrow_mut().element = Some(child.schema.clone());
            }
            node.elements.push(child);
            self.pop();
        }
        self.pop();
        node
    }

    fn parse_positional_record(&mut self) -> DNode {
        self.advance(1); // (
        let mut node = self.create_node(None);
        {
            let mut b = node.schema.borrow_mut();
            if b.kind != K::Record {
                b.kind = K::Record;
                b.type_name = "any".to_string();
            }
        }
        let predefined: Vec<SRef> = node.schema.borrow().fields.clone();
        let mut index = 0;
        let mut closed = false;
        while !self.eof() {
            self.parse_meta();
            match self.peek() {
                Some(')') => {
                    self.advance(1);
                    closed = true;
                    break;
                }
                Some(',') => {
                    self.advance(1);
                    continue;
                }
                _ => {}
            }
            let field_schema = predefined
                .get(index)
                .cloned()
                .unwrap_or_else(|| schema(K::Any, ""));
            let pushed = fork(&field_schema);
            self.push(pushed.clone());
            let val = self.parse_node();
            if let Some(def) = predefined.get(index) {
                let name = def.borrow().name.clone();
                if Rc::ptr_eq(&val.schema, &pushed) {
                    replace_field(&node.schema, pushed.clone());
                }
                node.set_field(name, val);
            } else {
                let name = format!("_{index}");
                let (kind, type_name) = {
                    let b = val.schema.borrow();
                    (b.kind, b.type_name.clone())
                };
                let inferred = schema(kind, &type_name);
                inferred.borrow_mut().name = name.clone();
                add_field(&node.schema, inferred);
                node.set_field(name, val);
            }
            self.pop();
            index += 1;
        }
        if !closed {
            self.error("Unexpected EOF: Record not closed, expected ')'".to_string());
        }
        node
    }

    fn parse_named_record(&mut self) -> DNode {
        self.advance(1); // {
        let mut node = self.create_node(None);
        {
            let mut b = node.schema.borrow_mut();
            if b.kind != K::Record {
                b.kind = K::Record;
                b.type_name = "any".to_string();
            }
        }
        let current = node.schema.clone();
        let mut closed = false;
        while !self.eof() {
            self.parse_meta();
            match self.peek() {
                Some('}') => {
                    self.advance(1);
                    closed = true;
                    break;
                }
                Some(',') => {
                    self.advance(1);
                    continue;
                }
                _ => {}
            }
            let mut key = self.parse_ident();
            if key.is_empty() {
                if self.peek() == Some('"') {
                    key = self.read_quoted_string();
                } else {
                    self.error("Expected key in record".to_string());
                    self.advance(1);
                    continue;
                }
            }
            self.skip_ws();
            self.expect(':');
            // An empty key has no header field (headers name every field).
            let is_record = current.borrow().kind == K::Record && !key.is_empty();
            let field_schema = if is_record {
                get_field(&current, &key)
            } else {
                None
            }
            .unwrap_or_else(|| schema(K::Any, ""));
            let pushed = fork(&field_schema);
            self.push(pushed.clone());
            let val = self.parse_node();
            if is_record && Rc::ptr_eq(&val.schema, &pushed) && get_field(&current, &key).is_some()
            {
                replace_field(&current, pushed.clone());
            }
            if is_record {
                match get_field(&current, &key) {
                    Some(existing) => {
                        if is_any(&existing) && !is_any(&val.schema) {
                            val.schema.borrow_mut().name = key.clone();
                            replace_field(&current, val.schema.clone());
                        }
                    }
                    None => {
                        let (kind, type_name) = {
                            let b = val.schema.borrow();
                            (b.kind, b.type_name.clone())
                        };
                        let inferred = schema(kind, &type_name);
                        inferred.borrow_mut().name = key.clone();
                        add_field(&node.schema, inferred);
                    }
                }
            }
            node.set_field(key, val);
            self.pop();
        }
        if !closed {
            self.error("Unexpected EOF: Record not closed, expected '}'".to_string());
        }
        node
    }

    // --- metadata (skipped) ----------------------------------------------

    fn parse_meta(&mut self) {
        while !self.eof() {
            self.skip_ws();
            match (self.peek(), self.peek_next()) {
                (Some('/'), Some('*')) => self.parse_comment(),
                (Some('/'), Some('/')) => self.parse_meta_block(),
                (Some('$'), _) => self.parse_attribute(),
                (Some('#'), _) => {
                    self.advance(1);
                    self.parse_ident();
                }
                (Some('!'), _) => self.advance(1),
                _ => break,
            }
        }
    }

    fn parse_comment(&mut self) {
        self.advance(2);
        let mut nesting = 1;
        while !self.eof() && nesting > 0 {
            match (self.peek(), self.peek_next()) {
                (Some('\\'), _) => self.advance(2),
                (Some('/'), Some('*')) => {
                    nesting += 1;
                    self.advance(2);
                }
                (Some('*'), Some('/')) => {
                    nesting -= 1;
                    self.advance(2);
                }
                _ => self.advance(1),
            }
        }
        if nesting > 0 {
            self.error("Unterminated comment".to_string());
        }
    }

    fn parse_attribute(&mut self) {
        self.advance(1); // $
        self.parse_ident();
        self.skip_ws();
        if self.peek() == Some('=') {
            self.advance(1);
            self.skip_ws();
            if matches!(self.peek(), Some('<' | '[' | '(' | '{' | '@')) {
                // A structured value (`$changes=[…]`): metadata, not data.
                self.skip_value();
            } else {
                self.parse_primitive_value();
            }
        }
    }

    /// Skips one value — `<header> value`, `@Type value`, a bracketed group or
    /// a primitive — without building it (structured attribute values).
    fn skip_value(&mut self) {
        self.skip_ws();
        match self.peek() {
            Some('<') => {
                self.skip_group();
                self.skip_value();
            }
            Some('@') => {
                self.advance(1);
                self.parse_ident();
                self.skip_ws();
                if self.peek() == Some('<') {
                    self.skip_group();
                }
                self.skip_value();
            }
            Some('[' | '(' | '{') => self.skip_group(),
            _ => {
                self.parse_primitive_value();
            }
        }
    }

    /// Skips a balanced `<…>` / `[…]` / `(…)` / `{…}` group (strings, names in
    /// backticks and comments inside are skipped as a whole).
    fn skip_group(&mut self) {
        let mut depth = 0usize;
        while let Some(c) = self.peek() {
            match c {
                '"' => {
                    self.read_quoted_string();
                    continue;
                }
                '`' => {
                    self.parse_ident();
                    continue;
                }
                '/' if self.peek_next() == Some('*') => {
                    self.parse_comment();
                    continue;
                }
                '<' | '[' | '(' | '{' => depth += 1,
                '>' | ']' | ')' | '}' => {
                    depth = depth.saturating_sub(1);
                    if depth == 0 {
                        self.advance(1);
                        return;
                    }
                }
                _ => {}
            }
            self.advance(1);
        }
        self.error("Unterminated attribute value".to_string());
    }

    fn parse_meta_block(&mut self) {
        self.advance(2); // //
        while !self.eof() {
            self.skip_ws();
            match (self.peek(), self.peek_next()) {
                (Some('/'), Some('*')) => self.parse_comment(),
                (Some('/'), Some('/')) => {
                    self.advance(2);
                    break;
                }
                (Some('$'), _) => self.parse_attribute(),
                (Some('#'), _) => {
                    self.advance(1);
                    self.parse_ident();
                }
                (Some(c), _) if c.is_ascii_alphanumeric() || c == '_' || c == '`' => {
                    let start = self.i;
                    self.parse_ident();
                    if self.i == start {
                        self.advance(1);
                    }
                    self.skip_ws();
                    if self.peek() == Some('=') {
                        self.advance(1);
                        self.parse_primitive_value();
                    }
                }
                (Some(c), _) => {
                    self.error(format!("Unexpected token in meta block: {c}"));
                    self.advance(1);
                }
                (None, _) => break,
            }
        }
    }

    // --- tokens ------------------------------------------------------------

    fn parse_ident(&mut self) -> String {
        self.skip_ws();
        if self.eof() {
            return String::new();
        }
        if self.peek() == Some('`') {
            self.advance(1);
            let start = self.i;
            while !self.eof() {
                if self.peek() == Some('`') {
                    let ident: String = self.text[start..self.i].iter().collect();
                    self.advance(1);
                    return ident;
                }
                self.advance(1);
            }
            return self.text[start..self.i].iter().collect();
        }
        let start = self.i;
        match self.peek() {
            Some(c) if c.is_ascii_alphabetic() || c == '_' => self.advance(1),
            _ => return String::new(),
        }
        while let Some(c) = self.peek() {
            if c.is_ascii_alphanumeric() || c == '_' {
                self.advance(1);
            } else {
                break;
            }
        }
        self.text[start..self.i].iter().collect()
    }

    fn parse_primitive_value(&mut self) -> Value {
        match self.peek() {
            None => Value::Null,
            Some('"') => Value::String(self.read_quoted_string()),
            Some(c) if c.is_ascii_digit() || c == '-' => self.read_number(),
            _ => {
                let raw = self.parse_ident();
                match raw.as_str() {
                    "true" => Value::Bool(true),
                    "false" => Value::Bool(false),
                    "null" => Value::Null,
                    _ => Value::String(raw),
                }
            }
        }
    }

    fn read_quoted_string(&mut self) -> String {
        self.expect('"');
        let mut out = String::new();
        while let Some(ch) = self.peek() {
            if ch == '"' {
                break;
            }
            if ch == '\\' {
                self.advance(1);
                let esc = match self.peek() {
                    Some(e) => e,
                    None => {
                        self.error("Unexpected EOF inside string escape".to_string());
                        break;
                    }
                };
                out.push(match esc {
                    'n' => '\n',
                    't' => '\t',
                    'r' => '\r',
                    other => other,
                });
                self.advance(1);
                continue;
            }
            out.push(ch);
            self.advance(1);
        }
        self.expect('"');
        out
    }

    fn read_number(&mut self) -> Value {
        let start = self.i;
        if self.peek() == Some('-') {
            self.advance(1);
        }
        let digits = |d: &mut Self| {
            while d.peek().is_some_and(|c| c.is_ascii_digit()) {
                d.advance(1);
            }
        };
        digits(self);
        let mut float = false;
        if self.peek() == Some('.') {
            float = true;
            self.advance(1);
            digits(self);
        }
        if matches!(self.peek(), Some('e' | 'E')) {
            float = true;
            self.advance(1);
            if matches!(self.peek(), Some('+' | '-')) {
                self.advance(1);
            }
            digits(self);
        }
        let raw: String = self.text[start..self.i].iter().collect();
        if !float {
            if let Ok(n) = raw.parse::<i64>() {
                return Value::Number(n.into());
            }
            if let Ok(n) = raw.parse::<u64>() {
                return Value::Number(n.into());
            }
        }
        // Like parseFloat: the longest valid prefix ("1e" → 1).
        let mut text = raw.as_str();
        loop {
            if let Ok(f) = text.parse::<f64>() {
                if let Some(n) = Number::from_f64(f) {
                    return Value::Number(n);
                }
                break;
            }
            if text.is_empty() {
                break;
            }
            text = &text[..text.len() - 1];
        }
        self.error(format!("Invalid number format: {raw}"));
        Value::Number(0.into())
    }
}
