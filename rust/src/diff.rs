//! Differences between documents, merging, applying changes and the change
//! history kept in a document (`ak-data diff | merge | apply | history`).
//!
//! A change is `add`, `remove`, `change` or `order` at a path
//! (`users[id=2].name`, `tags[1]`, `config.debug`) with the old and the new
//! value. Lists of records are matched by a key field (`id`, `key`, `name`,
//! `slug`, `sku`, `code`, `uuid` or the first field) when it is present and
//! unique in both lists, otherwise by position; `order` records a new order
//! of such a list (old / new: the keys in order).
//!
//! The history is a list of change sets (id, date, author, title,
//! description, changes) stored in the document as the attribute
//! `$changes` — metadata, so decoding the document still gives exactly the
//! data:
//!
//! ```
//! use arkadia_data::diff::{self, ChangeSet, Info};
//! use serde_json::json;
//!
//! let old = json!({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]});
//! let new = json!({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan T."}]});
//! let changes = diff::diff(&old, &new);
//! assert_eq!(changes[0].path, "users[id=2].name");
//! assert_eq!(diff::apply(&old, &changes).unwrap(), new);
//!
//! let info = Info { title: Some("Rename Alan".into()), date: Some("2026-11-01T17:00:00Z".into()), ..Info::default() };
//! let set = ChangeSet::new(changes, &info, None);
//! let text = diff::with_history(&new, &[set]);          // data + // $changes=… //
//! assert_eq!(arkadia_data::decode(&text).unwrap(), new); // the data is unchanged
//! assert_eq!(diff::history(&text)[0].title.as_deref(), Some("Rename Alan"));
//! ```

use std::fmt;

use serde_json::{Map, Value};

use crate::encoder::{encode, EncodeOptions};

// ---------------------------------------------------------------------------
// Changes
// ---------------------------------------------------------------------------

/// What happened at a path.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Op {
    Add,
    Remove,
    Change,
    /// A list of records got a new order (old / new: the keys in order).
    Order,
}

impl Op {
    pub fn name(self) -> &'static str {
        match self {
            Op::Add => "add",
            Op::Remove => "remove",
            Op::Change => "change",
            Op::Order => "order",
        }
    }

    pub fn parse(name: &str) -> Option<Op> {
        match name {
            "add" => Some(Op::Add),
            "remove" => Some(Op::Remove),
            "change" => Some(Op::Change),
            "order" => Some(Op::Order),
            _ => None,
        }
    }
}

/// One change of the second document relative to the first.
#[derive(Debug, Clone, PartialEq)]
pub struct Change {
    pub op: Op,
    /// `users[id=2].name`, `tags[1]`, `$` for the whole document.
    pub path: String,
    /// The value in the first document (`None` for `add`).
    pub old: Option<Value>,
    /// The value in the second document (`None` for `remove`).
    pub new: Option<Value>,
}

impl Change {
    fn new(op: Op, path: String, old: Option<Value>, new: Option<Value>) -> Change {
        Change { op, path, old, new }
    }
}

const KEYS: [&str; 7] = ["id", "key", "name", "slug", "sku", "code", "uuid"];

fn scalar(v: &Value) -> bool {
    matches!(
        v,
        Value::String(_) | Value::Number(_) | Value::Bool(_) | Value::Null
    )
}

fn is_ident(s: &str) -> bool {
    s.chars()
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

fn json(v: &Value) -> String {
    serde_json::to_string(v).unwrap_or_default()
}

/// The field that identifies the records of both lists, if there is one.
fn list_key(a: &[Value], b: &[Value]) -> Option<String> {
    let all = || a.iter().chain(b.iter());
    if a.is_empty() && b.is_empty() || !all().all(Value::is_object) {
        return None;
    }
    let first = all()
        .next()
        .and_then(Value::as_object)
        .and_then(|m| m.keys().next().cloned());
    let candidates = KEYS
        .iter()
        .map(|k| k.to_string())
        .chain(first)
        .collect::<Vec<_>>();
    candidates.into_iter().find(|k| {
        let unique = |list: &[Value]| {
            let mut seen = Vec::new();
            for item in list {
                match item.get(k) {
                    Some(v) if scalar(v) && !v.is_null() => {
                        if seen.contains(&v) {
                            return false;
                        }
                        seen.push(v);
                    }
                    _ => return false,
                }
            }
            true
        };
        unique(a) && unique(b)
    })
}

fn child(path: &str, key: &str) -> String {
    let part = if is_ident(key) {
        key.to_string()
    } else {
        format!("[{}]", json(&Value::String(key.to_string())))
    };
    match (path, part.starts_with('[')) {
        ("$", _) => part,
        (_, true) => format!("{path}{part}"),
        (_, false) => format!("{path}.{part}"),
    }
}

fn item(path: &str, label: &str) -> String {
    let base = if path == "$" { "" } else { path };
    format!("{base}[{label}]")
}

fn key_label(key: &str, v: &Value) -> String {
    let name = if is_ident(key) {
        key.to_string()
    } else {
        json(&Value::String(key.to_string()))
    };
    format!("{name}={}", json(v))
}

fn walk(a: &Value, b: &Value, path: &str, out: &mut Vec<Change>) {
    match (a, b) {
        (Value::Object(ma), Value::Object(mb)) => {
            for (k, va) in ma {
                match mb.get(k) {
                    Some(vb) => walk(va, vb, &child(path, k), out),
                    None => out.push(Change::new(
                        Op::Remove,
                        child(path, k),
                        Some(va.clone()),
                        None,
                    )),
                }
            }
            for (k, vb) in mb {
                if !ma.contains_key(k) {
                    out.push(Change::new(Op::Add, child(path, k), None, Some(vb.clone())));
                }
            }
        }
        (Value::Array(la), Value::Array(lb)) => match list_key(la, lb) {
            Some(key) => {
                let mut removed = Vec::new();
                for ia in la {
                    let id = &ia[&key];
                    let p = item(path, &key_label(&key, id));
                    match lb.iter().find(|ib| &ib[&key] == id) {
                        Some(ib) => walk(ia, ib, &p, out),
                        None => removed.push(Change::new(Op::Remove, p, Some(ia.clone()), None)),
                    }
                }
                // Removed records last to first: undone, they come back in order.
                out.extend(removed.into_iter().rev());
                for ib in lb {
                    let id = &ib[&key];
                    if !la.iter().any(|ia| &ia[&key] == id) {
                        out.push(Change::new(
                            Op::Add,
                            item(path, &key_label(&key, id)),
                            None,
                            Some(ib.clone()),
                        ));
                    }
                }
                // Applying keeps records in place and appends new ones; when
                // that does not give the order of `b` (or, undoing, of `a`),
                // record the order.
                let keys =
                    |l: &[Value]| -> Vec<Value> { l.iter().map(|x| x[&key].clone()).collect() };
                let (ka, kb) = (keys(la), keys(lb));
                let naive = |from: &[Value], to: &[Value]| -> Vec<Value> {
                    let mut out: Vec<Value> =
                        from.iter().filter(|k| to.contains(k)).cloned().collect();
                    out.extend(to.iter().filter(|k| !from.contains(k)).cloned());
                    out
                };
                if naive(&ka, &kb) != kb || naive(&kb, &ka) != ka {
                    out.push(Change::new(
                        Op::Order,
                        path.to_string(),
                        Some(Value::Array(ka)),
                        Some(Value::Array(kb)),
                    ));
                }
            }
            None => {
                let common = la.len().min(lb.len());
                for i in 0..common {
                    walk(&la[i], &lb[i], &item(path, &i.to_string()), out);
                }
                // Removed from the end backwards, so the indexes stay valid
                // when the changes are applied one after another.
                for i in (common..la.len()).rev() {
                    out.push(Change::new(
                        Op::Remove,
                        item(path, &i.to_string()),
                        Some(la[i].clone()),
                        None,
                    ));
                }
                for (i, v) in lb.iter().enumerate().skip(common) {
                    out.push(Change::new(
                        Op::Add,
                        item(path, &i.to_string()),
                        None,
                        Some(v.clone()),
                    ));
                }
            }
        },
        _ => {
            if a != b {
                out.push(Change::new(
                    Op::Change,
                    path.to_string(),
                    Some(a.clone()),
                    Some(b.clone()),
                ));
            }
        }
    }
}

/// The changes that turn `a` into `b` (`apply(a, diff(a, b)) == b`).
pub fn diff(a: &Value, b: &Value) -> Vec<Change> {
    let mut out = Vec::new();
    walk(a, b, "$", &mut out);
    out
}

/// `b` merged into `a`: records are merged field by field (values of `b`
/// win, fields only in `a` stay), lists of records by their key field (new
/// records appended), other lists and values are replaced by `b`'s.
pub fn merge(a: &Value, b: &Value) -> Value {
    match (a, b) {
        (Value::Object(ma), Value::Object(mb)) => {
            let mut out = Map::new();
            for (k, va) in ma {
                let v = match mb.get(k) {
                    Some(vb) => merge(va, vb),
                    None => va.clone(),
                };
                out.insert(k.clone(), v);
            }
            for (k, vb) in mb {
                if !ma.contains_key(k) {
                    out.insert(k.clone(), vb.clone());
                }
            }
            Value::Object(out)
        }
        (Value::Array(la), Value::Array(lb)) => match list_key(la, lb) {
            Some(key) => {
                let mut out: Vec<Value> = la
                    .iter()
                    .map(|ia| match lb.iter().find(|ib| ib[&key] == ia[&key]) {
                        Some(ib) => merge(ia, ib),
                        None => ia.clone(),
                    })
                    .collect();
                out.extend(
                    lb.iter()
                        .filter(|ib| !la.iter().any(|ia| ia[&key] == ib[&key]))
                        .cloned(),
                );
                Value::Array(out)
            }
            None => b.clone(),
        },
        _ => b.clone(),
    }
}

/// Counts of added, removed and changed values (`order` is not counted).
pub fn summary(changes: &[Change]) -> (usize, usize, usize) {
    let n = |op: Op| changes.iter().filter(|c| c.op == op).count();
    (n(Op::Add), n(Op::Remove), n(Op::Change))
}

/// The changes that undo `changes` (`apply(b, reverse(diff(a, b))) == a`).
pub fn reverse(changes: &[Change]) -> Vec<Change> {
    let mut out: Vec<Change> = changes
        .iter()
        .rev()
        .map(|c| Change {
            op: match c.op {
                Op::Add => Op::Remove,
                Op::Remove => Op::Add,
                op => op,
            },
            path: c.path.clone(),
            old: c.new.clone(),
            new: c.old.clone(),
        })
        .collect();
    // A new order is applied after the records of its list were added and
    // removed: move each `order` behind the last change inside its list.
    let mut i = 0;
    while i < out.len() {
        if out[i].op == Op::Order {
            let list = out[i].path.clone();
            let inside = |p: &str| {
                p.strip_prefix(list.as_str())
                    .is_some_and(|rest| rest.starts_with('['))
                    || list == "$" && p.starts_with('[')
            };
            if let Some(last) = (i + 1..out.len()).rev().find(|&j| inside(&out[j].path)) {
                let c = out.remove(i);
                out.insert(last, c);
                continue;
            }
        }
        i += 1;
    }
    out
}

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

/// One step of a path.
#[derive(Debug, Clone, PartialEq)]
pub enum Step {
    /// `.name` or `["any key"]`
    Key(String),
    /// `[3]`
    Index(usize),
    /// `[id=3]`: the record whose field has this value.
    Match(String, Value),
}

/// Reads `users[id=2].name`, `tags[1]`, `["a key"].x` or `$`.
pub fn parse_path(path: &str) -> Result<Vec<Step>, String> {
    let chars: Vec<char> = path.chars().collect();
    let mut i = 0;
    let mut steps = Vec::new();
    let err = |msg: &str| format!("invalid path '{path}': {msg}");
    if chars.first() == Some(&'$') {
        i = 1;
    }
    let read_ident = |i: &mut usize| -> String {
        let start = *i;
        while *i < chars.len() && (chars[*i].is_ascii_alphanumeric() || chars[*i] == '_') {
            *i += 1;
        }
        chars[start..*i].iter().collect()
    };
    let read_string = |i: &mut usize| -> Result<String, String> {
        let start = *i;
        *i += 1;
        while *i < chars.len() && chars[*i] != '"' {
            if chars[*i] == '\\' {
                *i += 1;
            }
            *i += 1;
        }
        *i += 1;
        let raw: String = chars[start..(*i).min(chars.len())].iter().collect();
        serde_json::from_str(&raw).map_err(|_| err("bad quoted name"))
    };
    while i < chars.len() {
        match chars[i] {
            '.' => {
                i += 1;
                let name = read_ident(&mut i);
                if name.is_empty() {
                    return Err(err("name expected after '.'"));
                }
                steps.push(Step::Key(name));
            }
            '[' => {
                i += 1;
                if chars.get(i).is_some_and(char::is_ascii_digit) {
                    let start = i;
                    while i < chars.len() && chars[i].is_ascii_digit() {
                        i += 1;
                    }
                    let n: String = chars[start..i].iter().collect();
                    steps.push(Step::Index(n.parse().map_err(|_| err("bad index"))?));
                } else {
                    let name = if chars.get(i) == Some(&'"') {
                        read_string(&mut i)?
                    } else {
                        read_ident(&mut i)
                    };
                    if chars.get(i) == Some(&'=') {
                        i += 1;
                        let start = i;
                        if chars.get(i) == Some(&'"') {
                            read_string(&mut i)?;
                        } else {
                            while i < chars.len() && chars[i] != ']' {
                                i += 1;
                            }
                        }
                        let raw: String = chars[start..i].iter().collect();
                        let v: Value =
                            serde_json::from_str(&raw).map_err(|_| err("bad key value"))?;
                        steps.push(Step::Match(name, v));
                    } else {
                        steps.push(Step::Key(name));
                    }
                }
                if chars.get(i) != Some(&']') {
                    return Err(err("']' expected"));
                }
                i += 1;
            }
            c if steps.is_empty() && (c.is_ascii_alphabetic() || c == '_') => {
                steps.push(Step::Key(read_ident(&mut i)));
            }
            c => return Err(err(&format!("unexpected '{c}'"))),
        }
    }
    Ok(steps)
}

fn find(list: &[Value], key: &str, v: &Value) -> Option<usize> {
    list.iter().position(|x| x.get(key) == Some(v))
}

fn step_mut<'a>(value: &'a mut Value, step: &Step) -> Option<&'a mut Value> {
    match (value, step) {
        (Value::Object(m), Step::Key(k)) => m.get_mut(k),
        (Value::Array(l), Step::Index(i)) => l.get_mut(*i),
        (Value::Array(l), Step::Match(k, v)) => {
            let i = find(l, k, v)?;
            l.get_mut(i)
        }
        _ => None,
    }
}

fn resolve_mut<'a>(value: &'a mut Value, steps: &[Step]) -> Option<&'a mut Value> {
    steps.iter().try_fold(value, |v, s| step_mut(v, s))
}

fn get<'a>(value: &'a Value, steps: &[Step]) -> Option<&'a Value> {
    steps.iter().try_fold(value, |v, s| match (v, s) {
        (Value::Object(m), Step::Key(k)) => m.get(k),
        (Value::Array(l), Step::Index(i)) => l.get(*i),
        (Value::Array(l), Step::Match(k, x)) => find(l, k, x).map(|i| &l[i]),
        _ => None,
    })
}

// ---------------------------------------------------------------------------
// Applying changes
// ---------------------------------------------------------------------------

/// A change that does not fit the document.
#[derive(Debug, Clone, PartialEq)]
pub struct Conflict {
    /// Position of the change in the list.
    pub index: usize,
    pub path: String,
    pub reason: String,
}

impl fmt::Display for Conflict {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.path, self.reason)
    }
}

fn found(v: Option<&Value>) -> String {
    v.map_or("nothing".to_string(), |v| shorten(&json(v), 60))
}

fn shorten(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        format!("{}…", s.chars().take(max - 1).collect::<String>())
    }
}

/// Applies one change; `force` writes it even when the old value differs.
fn apply_one(doc: &mut Value, c: &Change, force: bool) -> Result<(), String> {
    let steps = parse_path(&c.path)?;
    if c.op == Op::Order {
        let Some(Value::Array(list)) = resolve_mut(doc, &steps) else {
            return Err("no list here".to_string());
        };
        let Some(Value::Array(order)) = &c.new else {
            return Err("order without keys".to_string());
        };
        let key = list_key(list, list).ok_or("the list has no key field")?;
        let pos = |x: &Value| {
            order
                .iter()
                .position(|k| Some(k) == x.get(&key))
                .unwrap_or(usize::MAX)
        };
        list.sort_by_key(pos); // stable: records not in `order` keep theirs, at the end
        return Ok(());
    }
    let Some((last, parent_steps)) = steps.split_last() else {
        // The whole document.
        let now = doc.clone();
        if !force && c.op != Op::Add && Some(&now) != c.old.as_ref() {
            return Err(format!(
                "expected {}, found {}",
                found(c.old.as_ref()),
                found(Some(&now))
            ));
        }
        *doc = c.new.clone().unwrap_or(Value::Null);
        return Ok(());
    };
    let current = get(doc, &steps).cloned();
    let parent = resolve_mut(doc, parent_steps).ok_or("the parent does not exist")?;
    match c.op {
        Op::Change => {
            if current.is_none() {
                return Err("nothing to change here".to_string());
            }
            if !force && current.as_ref() != c.old.as_ref() {
                return Err(format!(
                    "expected {}, found {}",
                    found(c.old.as_ref()),
                    found(current.as_ref())
                ));
            }
            *step_mut(parent, last).expect("checked") = c.new.clone().unwrap_or(Value::Null);
        }
        Op::Add => {
            let new = c.new.clone().unwrap_or(Value::Null);
            if let Some(now) = &current {
                if *now == new {
                    return Ok(()); // already there
                }
                if !force {
                    return Err(format!("already exists: {}", found(Some(now))));
                }
                *step_mut(parent, last).expect("checked") = new;
                return Ok(());
            }
            match (parent, last) {
                (Value::Object(m), Step::Key(k)) => {
                    m.insert(k.clone(), new);
                }
                (Value::Array(l), Step::Index(i)) if *i <= l.len() => l.insert(*i, new),
                (Value::Array(l), Step::Index(i)) => {
                    return Err(format!("index {i} is past the end ({} items)", l.len()))
                }
                (Value::Array(l), Step::Match(..)) => l.push(new),
                _ => return Err("cannot add here".to_string()),
            }
        }
        Op::Remove => {
            let Some(now) = current else {
                return Err("nothing to remove here".to_string());
            };
            if !force && Some(&now) != c.old.as_ref() {
                return Err(format!(
                    "expected {}, found {}",
                    found(c.old.as_ref()),
                    found(Some(&now))
                ));
            }
            match (parent, last) {
                (Value::Object(m), Step::Key(k)) => {
                    m.shift_remove(k);
                }
                (Value::Array(l), Step::Index(i)) => {
                    l.remove(*i);
                }
                (Value::Array(l), Step::Match(k, v)) => {
                    if let Some(i) = find(l, k, v) {
                        l.remove(i);
                    }
                }
                _ => return Err("cannot remove here".to_string()),
            }
        }
        Op::Order => unreachable!(),
    }
    Ok(())
}

/// `changes` applied to `data`. Every change must fit: the old value must be
/// the one in the document, otherwise the conflicts are returned.
pub fn apply(data: &Value, changes: &[Change]) -> Result<Value, Vec<Conflict>> {
    let (value, conflicts) = apply_with(data, changes, false);
    if conflicts.is_empty() {
        Ok(value)
    } else {
        Err(conflicts)
    }
}

/// Applies what can be applied (`force`: also over a different old value)
/// and returns the conflicts of the changes that were skipped.
pub fn apply_with(data: &Value, changes: &[Change], force: bool) -> (Value, Vec<Conflict>) {
    let mut doc = data.clone();
    let mut conflicts = Vec::new();
    for (index, c) in changes.iter().enumerate() {
        if let Err(reason) = apply_one(&mut doc, c, force) {
            conflicts.push(Conflict {
                index,
                path: c.path.clone(),
                reason,
            });
        }
    }
    (doc, conflicts)
}

// ---------------------------------------------------------------------------
// Change sets and the history ($changes)
// ---------------------------------------------------------------------------

/// Who, when and why — for a new change set.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Info {
    pub title: Option<String>,
    pub author: Option<String>,
    pub description: Option<String>,
    /// ISO 8601 (`2026-11-01T17:20:00Z`); now when `None`.
    pub date: Option<String>,
}

/// One entry of the history: the changes made together.
#[derive(Debug, Clone, PartialEq)]
pub struct ChangeSet {
    /// Short hash of the change set and the one before it (like a commit).
    pub id: String,
    pub date: String,
    pub author: Option<String>,
    pub title: Option<String>,
    pub description: Option<String>,
    pub changes: Vec<Change>,
}

/// FNV-1a, 64 bit.
fn fnv1a(text: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in text.as_bytes() {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x0100_0000_01b3);
    }
    h
}

fn opt(v: &Option<String>) -> String {
    v.clone().unwrap_or_default()
}

impl ChangeSet {
    /// A change set; `parent` is the id of the previous one in the history.
    pub fn new(changes: Vec<Change>, info: &Info, parent: Option<&str>) -> ChangeSet {
        let date = info.date.clone().unwrap_or_else(now);
        let id = change_id(parent, &date, info, &changes);
        ChangeSet {
            id,
            date,
            author: info.author.clone().filter(|s| !s.is_empty()),
            title: info.title.clone().filter(|s| !s.is_empty()),
            description: info.description.clone().filter(|s| !s.is_empty()),
            changes,
        }
    }

    /// `{id, date, author, title, description, changes: [{op, path, old, new}]}`.
    pub fn to_json(&self) -> Value {
        let s = |v: &Option<String>| v.clone().map_or(Value::Null, Value::String);
        let mut m = Map::new();
        m.insert("id".into(), Value::String(self.id.clone()));
        m.insert("date".into(), Value::String(self.date.clone()));
        m.insert("author".into(), s(&self.author));
        m.insert("title".into(), s(&self.title));
        m.insert("description".into(), s(&self.description));
        m.insert("changes".into(), changes_json(&self.changes));
        Value::Object(m)
    }

    /// Reads a change set written by [`ChangeSet::to_json`].
    pub fn from_json(v: &Value) -> Result<ChangeSet, String> {
        let s = |k: &str| v.get(k).and_then(Value::as_str).map(str::to_string);
        Ok(ChangeSet {
            id: s("id").unwrap_or_default(),
            date: s("date").unwrap_or_default(),
            author: s("author"),
            title: s("title"),
            description: s("description"),
            changes: changes_from_json(v.get("changes").ok_or("a change set needs 'changes'")?)?,
        })
    }
}

/// The id of a change set: FNV-1a of the parent id, date, author, title,
/// description and the changes as compact JSON — 10 hex digits. The same
/// in Rust, Python and TypeScript.
pub fn change_id(parent: Option<&str>, date: &str, info: &Info, changes: &[Change]) -> String {
    let text = format!(
        "{}\n{date}\n{}\n{}\n{}\n{}",
        parent.unwrap_or(""),
        opt(&info.author),
        opt(&info.title),
        opt(&info.description),
        json(&changes_json(changes))
    );
    format!("{:016x}", fnv1a(&text))[..10].to_string()
}

/// The changes as JSON values `{op, path, old, new}`.
pub fn changes_json(changes: &[Change]) -> Value {
    Value::Array(
        changes
            .iter()
            .map(|c| {
                let mut m = Map::new();
                m.insert("op".into(), Value::String(c.op.name().into()));
                m.insert("path".into(), Value::String(c.path.clone()));
                m.insert("old".into(), c.old.clone().unwrap_or(Value::Null));
                m.insert("new".into(), c.new.clone().unwrap_or(Value::Null));
                Value::Object(m)
            })
            .collect(),
    )
}

/// Reads `[{op, path, old, new}, …]`.
pub fn changes_from_json(v: &Value) -> Result<Vec<Change>, String> {
    let list = v.as_array().ok_or("changes must be a list")?;
    list.iter()
        .map(|c| {
            let op = c
                .get("op")
                .and_then(Value::as_str)
                .and_then(Op::parse)
                .ok_or("a change needs op: add, remove, change or order")?;
            let path = c
                .get("path")
                .and_then(Value::as_str)
                .ok_or("a change needs a path")?
                .to_string();
            let val = |k: &str| c.get(k).cloned().unwrap_or(Value::Null);
            Ok(Change {
                op,
                path,
                old: (op != Op::Add).then(|| val("old")),
                new: (op != Op::Remove).then(|| val("new")),
            })
        })
        .collect()
}

/// The history of a document: its `$changes` attribute (oldest first).
pub fn history(text: &str) -> Vec<ChangeSet> {
    match attributes(text).get("changes") {
        Some(Value::Array(list)) => list
            .iter()
            .filter_map(|v| ChangeSet::from_json(v).ok())
            .collect(),
        _ => Vec::new(),
    }
}

/// `data` as compact AK-DATA with the history as `// $changes=[…] //` after
/// it (just the data when the history is empty).
pub fn with_history(data: &Value, history: &[ChangeSet]) -> String {
    let body = encode(data, &EncodeOptions::compact());
    if history.is_empty() {
        return body;
    }
    let list = Value::Array(history.iter().map(ChangeSet::to_json).collect());
    format!(
        "{body} // $changes={} //",
        encode(&list, &EncodeOptions::compact())
    )
}

/// The document `text` (JSON or AK-DATA) updated to `data`, the change
/// recorded in its history; the same text when the data is the same.
pub fn commit(text: &str, data: &Value, info: &Info) -> Result<String, crate::Error> {
    let old = crate::loads_any(text)?;
    let mut past = if crate::is_json(text) {
        Vec::new()
    } else {
        history(text)
    };
    let changes = diff(&old, data);
    if !changes.is_empty() {
        let parent = past.last().map(|s| s.id.clone());
        past.push(ChangeSet::new(changes, info, parent.as_deref()));
    }
    Ok(with_history(data, &past))
}

/// A value in a field typed `any`: primitives as they are, records and lists
/// with their own inline header (`<id:number>(4)`).
pub fn value_akd(v: Option<&Value>) -> String {
    match v {
        None | Some(Value::Null) => "null".to_string(),
        Some(v) if scalar(v) => json(v),
        Some(v) => encode(v, &EncodeOptions::compact()),
    }
}

// ---------------------------------------------------------------------------
// Document attributes
// ---------------------------------------------------------------------------

struct Scan<'a> {
    c: &'a [char],
    i: usize,
}

impl Scan<'_> {
    fn peek(&self) -> Option<char> {
        self.c.get(self.i).copied()
    }
    fn at(&self, s: &str) -> bool {
        s.chars()
            .enumerate()
            .all(|(k, ch)| self.c.get(self.i + k) == Some(&ch))
    }
    fn ws(&mut self) {
        while self.peek().is_some_and(char::is_whitespace) {
            self.i += 1;
        }
    }
    fn string(&mut self, quote: char) {
        self.i += 1;
        while let Some(ch) = self.peek() {
            self.i += 1;
            if ch == '\\' && quote == '"' {
                self.i += 1;
            } else if ch == quote {
                return;
            }
        }
    }
    fn comment(&mut self) {
        self.i += 2;
        let mut depth = 1;
        while depth > 0 && self.i < self.c.len() {
            if self.at("/*") {
                depth += 1;
                self.i += 2;
            } else if self.at("*/") {
                depth -= 1;
                self.i += 2;
            } else {
                self.i += if self.peek() == Some('\\') { 2 } else { 1 };
            }
        }
    }
    fn ident(&mut self) -> String {
        if self.peek() == Some('`') {
            let start = self.i + 1;
            self.string('`');
            return self.c[start..self.i.saturating_sub(1).max(start)]
                .iter()
                .collect();
        }
        let start = self.i;
        while self
            .peek()
            .is_some_and(|ch| ch.is_ascii_alphanumeric() || ch == '_')
        {
            self.i += 1;
        }
        self.c[start..self.i].iter().collect()
    }
    fn group(&mut self) {
        let mut depth = 0usize;
        while let Some(ch) = self.peek() {
            match ch {
                '"' | '`' => {
                    self.string(ch);
                    continue;
                }
                '/' if self.at("/*") => {
                    self.comment();
                    continue;
                }
                '<' | '[' | '(' | '{' => depth += 1,
                '>' | ']' | ')' | '}' => {
                    depth = depth.saturating_sub(1);
                    if depth == 0 {
                        self.i += 1;
                        return;
                    }
                }
                _ => {}
            }
            self.i += 1;
        }
    }
    fn token(&mut self) {
        while let Some(ch) = self.peek() {
            if ch.is_whitespace() || "<>()[]{},/".contains(ch) {
                break;
            }
            self.i += 1;
        }
    }
    /// One value: `<header> value`, `@Type value`, a group or a primitive.
    fn value(&mut self) {
        self.ws();
        match self.peek() {
            Some('<') => {
                self.group();
                self.value();
            }
            Some('@') => {
                self.i += 1;
                self.ident();
                self.ws();
                if self.peek() == Some('<') {
                    self.group();
                }
                self.value();
            }
            Some('[' | '(' | '{') => self.group(),
            Some('"') => self.string('"'),
            _ => self.token(),
        }
    }
    /// `$name[=value]`
    fn attribute(&mut self, out: &mut Map<String, Value>) {
        self.i += 1;
        let name = self.ident();
        self.ws();
        let value = if self.peek() == Some('=') {
            self.i += 1;
            self.ws();
            let start = self.i;
            self.value();
            let raw: String = self.c[start..self.i].iter().collect();
            crate::decode(&raw).unwrap_or(Value::String(raw))
        } else {
            Value::Bool(true)
        };
        out.insert(name, value);
    }
}

impl Scan<'_> {
    /// Metadata between documents: `// … //` blocks, `$attr`, `#tag` and —
    /// in front of a document, not after it — comments.
    fn meta(&mut self, comments: bool) {
        loop {
            self.ws();
            if comments && self.at("/*") {
                self.comment();
            } else if self.at("//") {
                self.i += 2;
                while self.i < self.c.len() && !self.at("//") {
                    match self.peek() {
                        Some('"') => self.string('"'),
                        Some('/') if self.at("/*") => self.comment(),
                        _ => self.i += 1,
                    }
                }
                self.i = (self.i + 2).min(self.c.len());
            } else if self.peek() == Some('$') {
                self.i += 1;
                self.ident();
                self.ws();
                if self.peek() == Some('=') {
                    self.i += 1;
                    self.value();
                }
            } else if self.peek() == Some('#') {
                self.i += 1;
                self.ident();
            } else {
                return;
            }
        }
    }
}

/// Splits text holding several documents one after another (JSON or
/// AK-DATA, e.g. `{"a":1} {"a":2}` or two AK-DATA documents on their own
/// lines). Metadata after a document (its `$changes`) stays with it.
pub fn split_documents(text: &str) -> Vec<String> {
    let chars: Vec<char> = text.chars().collect();
    let mut s = Scan { c: &chars, i: 0 };
    let mut out = Vec::new();
    loop {
        s.ws();
        if s.i >= chars.len() {
            break;
        }
        let start = s.i;
        s.meta(true);
        s.value();
        s.meta(false);
        if s.i == start {
            s.i += 1;
        }
        let doc: String = chars[start..s.i].iter().collect();
        if !doc.trim().is_empty() {
            out.push(doc.trim().to_string());
        }
    }
    out
}

/// The attributes of the document itself (`$name=value` outside the data,
/// in or out of `// … //` blocks), e.g. `$changes`.
pub fn attributes(text: &str) -> Map<String, Value> {
    let chars: Vec<char> = text.chars().collect();
    let mut s = Scan { c: &chars, i: 0 };
    let mut out = Map::new();
    loop {
        s.ws();
        let Some(ch) = s.peek() else { break };
        if s.at("/*") {
            s.comment();
        } else if s.at("//") {
            s.i += 2;
            loop {
                s.ws();
                match s.peek() {
                    None => break,
                    Some('/') if s.at("//") => {
                        s.i += 2;
                        break;
                    }
                    Some('/') if s.at("/*") => s.comment(),
                    Some('$') => s.attribute(&mut out),
                    Some('#') => {
                        s.i += 1;
                        s.ident();
                    }
                    Some(_) => {
                        let start = s.i;
                        s.ident();
                        s.ws();
                        if s.peek() == Some('=') {
                            s.i += 1;
                            s.ws();
                            s.value();
                        }
                        if s.i == start {
                            s.i += 1;
                        }
                    }
                }
            }
        } else if ch == '$' {
            s.attribute(&mut out);
        } else if ch == '#' || ch == '@' {
            s.i += 1;
            s.ident();
        } else if "<[({".contains(ch) {
            s.group();
        } else if ch == '"' {
            s.string('"');
        } else {
            let start = s.i;
            s.token();
            if s.i == start {
                s.i += 1;
            }
        }
    }
    out
}

// ---------------------------------------------------------------------------
// Time
// ---------------------------------------------------------------------------

/// Now in UTC, ISO 8601 to the second: `2026-11-01T17:20:00Z`.
pub fn now() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    iso_date(secs as i64)
}

/// Seconds since 1970 as `YYYY-MM-DDTHH:MM:SSZ`.
pub fn iso_date(secs: i64) -> String {
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);
    // Howard Hinnant's civil_from_days.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + i64::from(m <= 2);
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        rem % 3600 / 60,
        rem % 60
    )
}

/// `2026-11-01T17:20:00Z` as seconds since 1970 (`None` when not ISO).
pub fn parse_date(text: &str) -> Option<i64> {
    let b = text.as_bytes();
    if b.len() < 19 {
        return None;
    }
    let n = |r: std::ops::Range<usize>| text.get(r)?.parse::<i64>().ok();
    let (y, m, d) = (n(0..4)?, n(5..7)?, n(8..10)?);
    let (hh, mm, ss) = (n(11..13)?, n(14..16)?, n(17..19)?);
    // days_from_civil
    let y2 = if m <= 2 { y - 1 } else { y };
    let era = y2.div_euclid(400);
    let yoe = y2 - era * 400;
    let mp = (m + 9) % 12;
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146_097 + doe - 719_468;
    Some(days * 86_400 + hh * 3600 + mm * 60 + ss)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn a() -> Value {
        json!({"team": "core", "debug": true, "users": [
            {"id": 1, "name": "Ada", "tags": ["x"]},
            {"id": 2, "name": "Alan", "tags": []}
        ]})
    }
    fn b() -> Value {
        json!({"team": "core", "users": [
            {"id": 2, "name": "Alan T.", "tags": []},
            {"id": 1, "name": "Ada", "tags": ["x", "y"]},
            {"id": 3, "name": "Grace", "tags": []}
        ], "version": 2})
    }

    #[test]
    fn finds_changes_by_key() {
        let d = diff(&a(), &b());
        let paths: Vec<(&str, &str)> = d.iter().map(|c| (c.op.name(), c.path.as_str())).collect();
        assert_eq!(
            paths,
            vec![
                ("remove", "debug"),
                ("add", "users[id=1].tags[1]"),
                ("change", "users[id=2].name"),
                ("add", "users[id=3]"),
                ("order", "users"),
                ("add", "version"),
            ]
        );
        assert!(diff(&a(), &a()).is_empty());
    }

    #[test]
    fn apply_and_reverse_are_exact() {
        let cases = [
            (a(), b()),
            (json!([1, 2, 3, 4]), json!([1, 5])),
            (json!([1]), json!([1, 2, 3])),
            (
                json!({"l": [{"id": 1}, {"id": 2}]}),
                json!({"l": [{"id": 3}, {"id": 2}]}),
            ),
            (
                json!({"a b": {"c": 1}}),
                json!({"a b": {"c": 2}, "x": null}),
            ),
            (json!(1), json!({"a": 1})),
        ];
        for (x, y) in cases {
            let d = diff(&x, &y);
            assert_eq!(apply(&x, &d).unwrap(), y, "{d:?}");
            assert_eq!(apply(&y, &reverse(&d)).unwrap(), x, "{d:?}");
        }
    }

    #[test]
    fn conflicts_are_reported() {
        let d = diff(&json!({"a": 1}), &json!({"a": 2}));
        let err = apply(&json!({"a": 5}), &d).unwrap_err();
        assert_eq!(err[0].path, "a");
        assert!(err[0].reason.contains("expected 1, found 5"));
        let (v, c) = apply_with(&json!({"a": 5}), &d, true);
        assert_eq!((v, c.len()), (json!({"a": 2}), 0));
    }

    #[test]
    fn paths_round_trip() {
        assert_eq!(
            parse_path(r#"users[id=2].tags[1]["a b"][name="x]"]"#).unwrap(),
            vec![
                Step::Key("users".into()),
                Step::Match("id".into(), json!(2)),
                Step::Key("tags".into()),
                Step::Index(1),
                Step::Key("a b".into()),
                Step::Match("name".into(), json!("x]")),
            ]
        );
        assert_eq!(parse_path("$").unwrap(), vec![]);
        assert!(parse_path("a..b").is_err());
    }

    #[test]
    fn merge_keeps_old_fields_and_adds_new_records() {
        let m = merge(&a(), &b());
        assert_eq!(m["debug"], json!(true));
        assert_eq!(m["version"], json!(2));
        assert_eq!(m["users"][1]["name"], json!("Alan T."));
        assert_eq!(m["users"][2]["name"], json!("Grace"));
        assert_eq!(summary(&diff(&a(), &m)).1, 0);
    }

    #[test]
    fn history_is_metadata() {
        let info = Info {
            title: Some("First".into()),
            author: Some("Ada".into()),
            date: Some("2026-11-01T17:20:00Z".into()),
            ..Info::default()
        };
        let one = ChangeSet::new(diff(&a(), &b()), &info, None);
        let two = ChangeSet::new(diff(&b(), &json!({})), &info, Some(&one.id));
        assert_ne!(one.id, two.id);
        let text = with_history(&b(), &[one.clone(), two.clone()]);
        assert_eq!(crate::decode(&text).unwrap(), b());
        assert_eq!(history(&text), vec![one, two]);
        let pretty = crate::layout::pretty(&text, 60);
        assert_eq!(crate::decode(&pretty).unwrap(), b());
        assert_eq!(history(&pretty).len(), 2);
    }

    /// Random documents and random edits: apply and reverse are exact.
    #[test]
    fn fuzz_round_trip() {
        let mut seed: u64 = 0x2545_f491_4f6c_dd1d;
        let mut rnd = |n: u64| {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed % n
        };
        fn gen(r: &mut dyn FnMut(u64) -> u64, depth: u32) -> Value {
            match r(if depth > 2 { 4 } else { 7 }) {
                0 => json!(r(5)),
                1 => json!(["a", "b", "c"][r(3) as usize]),
                2 => json!(r(2) == 0),
                3 => Value::Null,
                4 => Value::Array((0..r(4)).map(|_| gen(r, depth + 1)).collect()),
                5 => {
                    // records with a key
                    let mut ids: Vec<u64> = (0..6).collect();
                    let n = r(5) as usize;
                    Value::Array(
                        (0..n)
                            .map(|_| {
                                let id = ids.remove(r(ids.len() as u64) as usize);
                                json!({"id": id, "v": gen(r, depth + 1)})
                            })
                            .collect(),
                    )
                }
                _ => {
                    let mut m = Map::new();
                    for _ in 0..r(4) {
                        m.insert(
                            ["x", "y", "z", "w w"][r(4) as usize].to_string(),
                            gen(r, depth + 1),
                        );
                    }
                    Value::Object(m)
                }
            }
        }
        for _ in 0..3000 {
            let a = gen(&mut rnd, 0);
            let b = gen(&mut rnd, 0);
            for (x, y) in [(&a, &b), (&b, &a)] {
                let d = diff(x, y);
                assert_eq!(apply(x, &d).as_ref(), Ok(y), "{x} → {y}: {d:?}");
                assert_eq!(apply(y, &reverse(&d)).as_ref(), Ok(x), "{y} ← {x}: {d:?}");
            }
        }
    }

    #[test]
    fn commit_records_history() {
        let at = |d: &str, t: &str| Info {
            title: Some(t.into()),
            date: Some(d.into()),
            ..Info::default()
        };
        let text = commit(
            r#"{"n": 1}"#,
            &json!({"n": 2}),
            &at("2026-11-01T10:00:00Z", "Bump"),
        )
        .unwrap();
        let text = commit(
            &text,
            &json!({"n": 3}),
            &at("2026-11-01T11:00:00Z", "Again"),
        )
        .unwrap();
        assert_eq!(crate::decode(&text).unwrap(), json!({"n": 3}));
        let log = history(&text);
        assert_eq!(log.len(), 2);
        assert_eq!(log[1].changes[0].old, Some(json!(2)));
        assert_eq!(
            commit(&text, &json!({"n": 3}), &Info::default()).unwrap(),
            text
        );
    }

    #[test]
    fn splits_documents() {
        assert_eq!(
            split_documents(r#"{"a":1} {"a":2}"#),
            vec![r#"{"a":1}"#, r#"{"a":2}"#]
        );
        let two = "<a:number>(1) // $changes=<[id:string]>[(\"x\")] //\n/* c */ <a:number>(2)";
        let docs = split_documents(two);
        assert_eq!(docs.len(), 2, "{docs:?}");
        assert!(docs[0].ends_with("//") && docs[1].ends_with("(2)"));
        assert_eq!(split_documents("@P<x:number>\n<p:@P>((1))\n[1,2]").len(), 2);
        assert_eq!(split_documents("1 \"two\" [3]").len(), 3);
    }

    #[test]
    fn dates() {
        assert_eq!(iso_date(0), "1970-01-01T00:00:00Z");
        assert_eq!(iso_date(1_793_548_800), "2026-11-01T16:00:00Z");
        assert_eq!(parse_date("2026-11-01T16:00:00Z"), Some(1_793_548_800));
    }
}
