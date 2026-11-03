//! Readable layout and syntax highlighting of AK-DATA text.
//!
//! [`pretty`] re-flows any AK-DATA text (compact or hand-written) so that it
//! fits a line width: a group that fits stays on one line, a longer one gets
//! one item per line. Whitespace is not significant in AK-DATA, so the result
//! decodes to the same value. [`highlight`] adds ANSI colours (the palette of
//! the encoder's `colorize` option).
//!
//! ```
//! use arkadia_data::layout;
//!
//! let text = r#"<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])"#;
//! assert_eq!(
//!     layout::pretty(text, 40),
//!     "<users:<[id:number, name:string]>>\n([(1, \"Ada\"), (2, \"Alan\")])"
//! );
//! ```

/// One piece of a layout tree.
#[derive(Debug, Clone)]
enum Node {
    /// Text without brackets or top-level commas: a value, `name:`, a
    /// string, a comment or metadata.
    Atom { text: String, space_before: bool },
    /// `open` items separated by commas `close`.
    Group {
        open: char,
        close: char,
        items: Vec<Vec<Node>>,
        space_before: bool,
    },
}

impl Node {
    fn space_before(&self) -> bool {
        match self {
            Node::Atom { space_before, .. } | Node::Group { space_before, .. } => *space_before,
        }
    }
    fn is_header(&self) -> bool {
        matches!(self, Node::Group { open: '<', .. })
    }
    fn is_meta(&self) -> bool {
        match self {
            Node::Atom { text, .. } => {
                text.starts_with("/*")
                    || text.starts_with("//")
                    || text.starts_with('$')
                    || text.starts_with('#')
            }
            Node::Group { .. } => false,
        }
    }
}

fn closing(open: char) -> char {
    match open {
        '<' => '>',
        '(' => ')',
        '[' => ']',
        _ => '}',
    }
}

struct Parser<'a> {
    chars: &'a [char],
    i: usize,
}

impl Parser<'_> {
    fn peek(&self) -> Option<char> {
        self.chars.get(self.i).copied()
    }
    fn peek2(&self) -> Option<char> {
        self.chars.get(self.i + 1).copied()
    }

    /// Copies a quoted part (`"…"` or `` `…` ``) into `out`.
    fn quoted(&mut self, quote: char, out: &mut String) {
        out.push(quote);
        self.i += 1;
        while let Some(c) = self.peek() {
            out.push(c);
            self.i += 1;
            if c == '\\' && quote == '"' {
                if let Some(n) = self.peek() {
                    out.push(n);
                    self.i += 1;
                }
                continue;
            }
            if c == quote {
                break;
            }
        }
    }

    /// `/* … */` (nested) or `// … //`.
    fn comment(&mut self) -> String {
        let mut out = String::new();
        if self.peek2() == Some('*') {
            let mut depth = 0;
            while let Some(c) = self.peek() {
                if c == '/' && self.peek2() == Some('*') {
                    depth += 1;
                    out.push_str("/*");
                    self.i += 2;
                    continue;
                }
                if c == '*' && self.peek2() == Some('/') {
                    depth -= 1;
                    out.push_str("*/");
                    self.i += 2;
                    if depth == 0 {
                        break;
                    }
                    continue;
                }
                out.push(c);
                self.i += 1;
            }
        } else {
            out.push_str("//");
            self.i += 2;
            while let Some(c) = self.peek() {
                if c == '/' && self.peek2() == Some('/') {
                    out.push_str("//");
                    self.i += 2;
                    break;
                }
                if c == '"' {
                    self.quoted('"', &mut out);
                    continue;
                }
                // Runs of whitespace (a block laid out on several lines) → one space.
                if c.is_whitespace() {
                    if !out.ends_with(' ') {
                        out.push(' ');
                    }
                } else {
                    out.push(c);
                }
                self.i += 1;
            }
        }
        out
    }

    /// Items up to `close` (or the end of the text).
    fn items(&mut self, close: Option<char>) -> Vec<Vec<Node>> {
        let mut items: Vec<Vec<Node>> = vec![vec![]];
        let mut space = false;
        while let Some(c) = self.peek() {
            if c.is_whitespace() {
                space = true;
                self.i += 1;
                continue;
            }
            if Some(c) == close {
                self.i += 1;
                break;
            }
            let node = match c {
                ',' => {
                    self.i += 1;
                    items.push(vec![]);
                    space = false;
                    continue;
                }
                '<' | '(' | '[' | '{' => {
                    self.i += 1;
                    let inner = self.items(Some(closing(c)));
                    Node::Group {
                        open: c,
                        close: closing(c),
                        items: inner,
                        space_before: space,
                    }
                }
                '>' | ')' | ']' | '}' => {
                    // Unbalanced closing bracket: keep it as text.
                    self.i += 1;
                    Node::Atom {
                        text: c.to_string(),
                        space_before: space,
                    }
                }
                '/' if matches!(self.peek2(), Some('*' | '/')) => Node::Atom {
                    text: self.comment(),
                    space_before: space,
                },
                _ => {
                    let mut text = String::new();
                    while let Some(c) = self.peek() {
                        if c.is_whitespace() || "<>()[]{},".contains(c) {
                            break;
                        }
                        if c == '/' && matches!(self.peek2(), Some('*' | '/')) {
                            break;
                        }
                        if c == '"' || c == '`' {
                            self.quoted(c, &mut text);
                            continue;
                        }
                        text.push(c);
                        self.i += 1;
                    }
                    Node::Atom {
                        text,
                        space_before: space,
                    }
                }
            };
            space = false;
            items.last_mut().unwrap().push(node);
        }
        // `[]` and `()` have no items; a trailing comma leaves an empty one.
        if items.len() == 1 && items[0].is_empty() {
            items.clear();
        } else if items.last().is_some_and(Vec::is_empty) {
            items.pop();
        }
        items
    }
}

fn parse(text: &str) -> Vec<Node> {
    let chars: Vec<char> = text.chars().collect();
    let mut p = Parser {
        chars: &chars,
        i: 0,
    };
    p.items(None).into_iter().flatten().collect()
}

/// Is a space needed between `prev` and `next` inside one item?
fn gap(prev: &Node, next: &Node) -> bool {
    prev.is_header() || next.space_before() || prev.is_meta() || next.is_meta()
}

thread_local! {
    /// Compact output: "," between items, no optional spaces.
    static TIGHT: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

fn flat_seq(seq: &[Node]) -> String {
    let tight = TIGHT.with(std::cell::Cell::get);
    let mut out = String::new();
    for (i, n) in seq.iter().enumerate() {
        let prev = i.checked_sub(1).map(|j| &seq[j]);
        let space = prev.is_some_and(|p| {
            if tight {
                p.is_meta() || n.is_meta() || p.is_header()
            } else {
                gap(p, n)
            }
        });
        if space {
            out.push(' ');
        }
        out.push_str(&flat(n));
    }
    out
}

fn flat(node: &Node) -> String {
    match node {
        Node::Atom { text, .. } => match structured_block(text) {
            Some((name, value)) => {
                format!("// ${name}={} //", layout(value, usize::MAX / 4, false))
            }
            None => text.clone(),
        },
        Node::Group {
            open, close, items, ..
        } => {
            let sep = if TIGHT.with(std::cell::Cell::get) {
                ","
            } else {
                ", "
            };
            let inner: Vec<String> = items.iter().map(|s| flat_seq(s)).collect();
            format!("{open}{}{close}", inner.join(sep))
        }
    }
}

struct Writer {
    out: String,
    col: usize,
    width: usize,
    /// Depth of `<…>` groups: headers are never filled.
    header: usize,
}

impl Writer {
    fn push(&mut self, s: &str) {
        match s.rfind('\n') {
            Some(i) => self.col = s[i + 1..].chars().count(),
            None => self.col += s.chars().count(),
        }
        self.out.push_str(s);
    }
    fn newline(&mut self, indent: usize) {
        self.out.push('\n');
        self.out.push_str(&" ".repeat(indent));
        self.col = indent;
    }
    fn fits(&self, s: &str, extra: usize) -> bool {
        self.col + s.chars().count() + extra <= self.width
    }

    fn seq(&mut self, seq: &[Node], indent: usize, extra: usize) {
        let whole = flat_seq(seq);
        if self.fits(&whole, extra) {
            self.push(&whole);
            return;
        }
        for (i, n) in seq.iter().enumerate() {
            if i > 0 && gap(&seq[i - 1], n) {
                self.push(" ");
            }
            let tail = if i + 1 == seq.len() { extra } else { 0 };
            self.node(n, indent, tail);
        }
    }

    fn node(&mut self, node: &Node, indent: usize, extra: usize) {
        let text = flat(node);
        if self.fits(&text, extra) {
            self.push(&text);
            return;
        }
        let Node::Group {
            open, close, items, ..
        } = node
        else {
            if let Some((name, value)) = structured_block(&text) {
                // `// $changes=<…>[…] //` too long for a line: the value laid
                // out below the name, the closing `//` on its own line.
                self.push(&format!("// ${name}="));
                let inner = render(&parse(value), self.width.saturating_sub(indent + 2), true);
                for line in inner.lines() {
                    self.newline(indent + 2);
                    self.push(line);
                }
                self.newline(indent);
                self.push("//");
                return;
            }
            self.push(&text);
            return;
        };
        let header = usize::from(*open == '<');
        self.header += header;
        self.group(*open, *close, items, indent, extra);
        self.header -= header;
    }

    fn group(&mut self, open: char, close: char, items: &[Vec<Node>], indent: usize, extra: usize) {
        if items.len() == 1 {
            // `<[ … ]>`, `([ … ])`, `<users:<[ … ]>>`: brackets stay together,
            // the inner group breaks.
            self.push(&open.to_string());
            self.seq(&items[0], indent, extra + 1);
            self.push(&close.to_string());
            return;
        }
        // Records and lists of values fill lines (continuation lines align
        // after the bracket); headers and lists of records get one item per line.
        let values_only = items
            .iter()
            .all(|it| it.iter().all(|n| matches!(n, Node::Atom { .. })));
        let col0 = self.col + 1;
        let each_fits = items
            .iter()
            .all(|it| col0 + flat_seq(it).chars().count() < self.width);
        let fill = self.header == 0
            && each_fits
            && (open == '(' || open == '{' || (open == '[' && values_only));
        if fill {
            self.push(&open.to_string());
            for (i, item) in items.iter().enumerate() {
                let last = i + 1 == items.len();
                let tail = if last { extra + 1 } else { 1 };
                if i > 0 {
                    if self.fits(&format!(" {}", flat_seq(item)), tail) {
                        self.push(" ");
                    } else {
                        self.newline(col0);
                    }
                }
                self.seq(item, col0, tail);
                if !last {
                    self.push(",");
                }
            }
            self.push(&close.to_string());
            return;
        }
        self.push(&open.to_string());
        for (i, item) in items.iter().enumerate() {
            self.newline(indent + 2);
            let last = i + 1 == items.len();
            // Comments in front of an item get their own line.
            let lead = item
                .iter()
                .take_while(|n| matches!(n, Node::Atom { text, .. } if text.starts_with("/*")))
                .count();
            let item = if lead > 0 && lead < item.len() {
                for n in &item[..lead] {
                    self.push(&flat(n));
                    self.newline(indent + 2);
                }
                &item[lead..]
            } else {
                &item[..]
            };
            self.seq(item, indent + 2, usize::from(!last));
            if !last {
                self.push(",");
            }
        }
        self.newline(indent);
        self.push(&close.to_string());
    }
}

/// AK-DATA text laid out to `width` columns: headers and data on their own
/// lines, groups that do not fit broken into one item per line (indent 2).
/// The result decodes to the same value as `text`.
pub fn pretty(text: &str, width: usize) -> String {
    layout(text, width, true)
}

fn layout(text: &str, width: usize, lines: bool) -> String {
    render(&parse(text), width, lines)
}

fn render(nodes: &[Node], width: usize, lines: bool) -> String {
    let mut w = Writer {
        out: String::new(),
        col: 0,
        width: width.max(20),
        header: 0,
    };
    for (i, n) in nodes.iter().enumerate() {
        if i > 0 {
            let prev = &nodes[i - 1];
            // Header, named type declaration and metadata end their line.
            // … and a `// … //` block after the data (`$changes`) starts one.
            let block_after_data = matches!(prev, Node::Group { .. })
                && matches!(n, Node::Atom { text, .. } if text.starts_with("//"));
            let own_line = prev.is_header()
                || prev.is_meta()
                || block_after_data
                || n.is_header() && !prev_is_type_name(prev);
            if own_line && lines {
                w.newline(0);
            } else if if TIGHT.with(std::cell::Cell::get) {
                prev.is_meta() || n.is_meta()
            } else {
                gap(prev, n)
            } {
                w.push(" ");
            }
        }
        w.node(n, 0, 0);
    }
    w.out
}

/// `// $name=<structured value> //` with nothing else in the block.
fn structured_block(text: &str) -> Option<(&str, &str)> {
    let inner = text.strip_prefix("//")?.strip_suffix("//")?.trim();
    let rest = inner.strip_prefix('$')?;
    let eq = rest.find('=')?;
    let (name, value) = (&rest[..eq], rest[eq + 1..].trim());
    let ident = name
        .chars()
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
    if !ident || !value.starts_with(['<', '[', '(', '{', '@']) {
        return None;
    }
    // One value: no further attributes or tags after it.
    let nodes = parse(value);
    let single = nodes.iter().all(|n| !n.is_meta());
    single.then_some((name, value))
}

fn prev_is_type_name(node: &Node) -> bool {
    matches!(node, Node::Atom { text, .. } if text.starts_with('@'))
}

/// The same text on one line without optional spaces (comments and
/// metadata kept).
pub fn compact(text: &str) -> String {
    TIGHT.with(|t| t.set(true));
    let out = layout(text, usize::MAX / 4, false);
    TIGHT.with(|t| t.set(false));
    out
}

fn strip(nodes: Vec<Node>, comments: bool, attributes: bool) -> Vec<Node> {
    nodes
        .into_iter()
        .filter(|n| {
            !n.is_meta()
                || if matches!(n, Node::Atom { text, .. } if text.starts_with("/*")) {
                    comments
                } else {
                    attributes
                }
        })
        .map(|n| match n {
            Node::Group {
                open,
                close,
                items,
                space_before,
            } => Node::Group {
                open,
                close,
                items: items
                    .into_iter()
                    .map(|it| strip(it, comments, attributes))
                    .filter(|it| !it.is_empty())
                    .collect(),
                space_before,
            },
            atom => atom,
        })
        .collect()
}

/// Compact text keeping only the chosen metadata: `comments` keeps
/// `/* comments */`, `attributes` keeps `$attributes`, `#tags` and `// … //`
/// blocks. With both false the result is what the encoder writes.
pub fn strip_meta(text: &str, comments: bool, attributes: bool) -> String {
    let nodes = strip(parse(text), comments, attributes);
    TIGHT.with(|t| t.set(true));
    let out = render(&nodes, usize::MAX / 4, false);
    TIGHT.with(|t| t.set(false));
    out
}

/// A field name as written in a header: as is when it is an identifier
/// (`user_id`), otherwise in backticks (`` `user id` ``).
pub fn name(field: &str) -> String {
    let mut chars = field.chars();
    let ident = chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_');
    if ident {
        field.to_string()
    } else {
        format!("`{field}`")
    }
}

// ---------------------------------------------------------------------------
// Highlighting
// ---------------------------------------------------------------------------

const RESET: &str = "\x1b[0m";
/// Colour of strings.
pub const C_STRING: &str = "\x1b[92m";
/// Colour of numbers.
pub const C_NUMBER: &str = "\x1b[94m";
/// Colour of `true` / `false`.
pub const C_BOOL: &str = "\x1b[95m";
/// Colour of `null`.
pub const C_NULL: &str = "\x1b[90m";
/// Colour of types in headers.
pub const C_TYPE: &str = "\x1b[96m";
/// Colour of field names and record keys.
pub const C_KEY: &str = "\x1b[93m";
/// Colour of the header brackets `<` `>`.
pub const C_SCHEMA: &str = "\x1b[91m";
/// Colour of data brackets and commas.
pub const C_PUNCT: &str = "\x1b[37m";
/// Colour of comments.
pub const C_COMMENT: &str = "\x1b[2;3m";
/// Colour of `$attributes`.
pub const C_ATTR: &str = "\x1b[35m";
/// Colour of `#tags`.
pub const C_TAG: &str = "\x1b[34m";
/// Colour of `@Type` names.
pub const C_NAMED: &str = "\x1b[1;95m";

fn paint(out: &mut String, color: &str, text: &str) {
    out.push_str(color);
    out.push_str(text);
    out.push_str(RESET);
}

const TYPES: &[&str] = &[
    "string", "number", "int", "float", "bool", "null", "any", "binary",
];

/// AK-DATA text with ANSI colours: field names yellow, types cyan, header
/// brackets red, strings green, numbers blue, booleans magenta, `null` grey,
/// comments dim, `$attr` / `#tag` / `@Type` in their own colours.
pub fn highlight(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() * 2);
    let mut stack: Vec<char> = vec![];
    let mut i = 0;
    let read_while = |i: &mut usize, f: &dyn Fn(char) -> bool| -> String {
        let start = *i;
        while *i < chars.len() && f(chars[*i]) {
            *i += 1;
        }
        chars[start..*i].iter().collect()
    };
    while i < chars.len() {
        let c = chars[i];
        let in_header = stack.contains(&'<');
        let in_named = stack.last() == Some(&'{');
        // Comments and meta blocks.
        if c == '/' && matches!(chars.get(i + 1), Some('*' | '/')) {
            let mut p = Parser { chars: &chars, i };
            let s = p.comment();
            i = p.i;
            paint(&mut out, C_COMMENT, &s);
            continue;
        }
        match c {
            '"' | '`' => {
                let mut p = Parser { chars: &chars, i };
                let mut s = String::new();
                p.quoted(c, &mut s);
                i = p.i;
                // A name is followed by ':' (in headers and named records).
                let mut j = i;
                while j < chars.len() && chars[j] == ' ' {
                    j += 1;
                }
                let is_name = chars.get(j) == Some(&':') && (in_header || in_named);
                let color = if is_name || c == '`' { C_KEY } else { C_STRING };
                paint(&mut out, color, &s);
            }
            '<' => {
                stack.push('<');
                paint(&mut out, C_SCHEMA, "<");
                i += 1;
            }
            '>' => {
                if let Some(p) = stack.iter().rposition(|&x| x == '<') {
                    stack.truncate(p);
                }
                paint(&mut out, C_SCHEMA, ">");
                i += 1;
            }
            '(' | '[' | '{' => {
                stack.push(c);
                let color = if in_header { C_SCHEMA } else { C_PUNCT };
                paint(&mut out, color, &c.to_string());
                i += 1;
            }
            ')' | ']' | '}' => {
                stack.pop();
                let color = if stack.contains(&'<') {
                    C_SCHEMA
                } else {
                    C_PUNCT
                };
                paint(&mut out, color, &c.to_string());
                i += 1;
            }
            ',' | ':' => {
                paint(&mut out, C_PUNCT, &c.to_string());
                i += 1;
            }
            '$' | '#' | '@' => {
                i += 1;
                let name = read_while(&mut i, &|ch: char| ch.is_alphanumeric() || ch == '_');
                let color = match c {
                    '$' => C_ATTR,
                    '#' => C_TAG,
                    _ => C_NAMED,
                };
                paint(&mut out, color, &format!("{c}{name}"));
            }
            '=' => {
                paint(&mut out, C_ATTR, "=");
                i += 1;
            }
            ch if ch.is_ascii_digit()
                || ch == '-' && chars.get(i + 1).is_some_and(char::is_ascii_digit) =>
            {
                i += 1;
                let rest = read_while(&mut i, &|ch: char| {
                    ch.is_ascii_digit() || matches!(ch, '.' | 'e' | 'E' | '+' | '-')
                });
                paint(&mut out, C_NUMBER, &format!("{ch}{rest}"));
            }
            ch if ch.is_alphabetic() || ch == '_' => {
                let word = read_while(&mut i, &|ch: char| ch.is_alphanumeric() || ch == '_');
                let mut j = i;
                while j < chars.len() && chars[j] == ' ' {
                    j += 1;
                }
                let is_name = chars.get(j) == Some(&':');
                let color = if is_name {
                    C_KEY
                } else if in_header {
                    if TYPES.contains(&word.as_str()) {
                        C_TYPE
                    } else {
                        C_NAMED
                    }
                } else {
                    match word.as_str() {
                        "true" | "false" => C_BOOL,
                        "null" => C_NULL,
                        _ => C_STRING,
                    }
                };
                paint(&mut out, color, &word);
            }
            _ => {
                out.push(c);
                i += 1;
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::decode;

    const SAMPLE: &str = r#"<orders:<[id:string,customer:<id:number,name:string>,items:<[sku:string,qty:number]>,total:number]>>([("A1",(7,"Ada"),[("KB-01",2),("MS-02",1)],178.0),("A2",(9,"Alan Turing"),[],0),<any> {id:"A3",note:"no items"}])"#;

    #[test]
    fn short_text_stays_on_one_line() {
        assert_eq!(pretty("<[number]>[1,2,3]", 80), "<[number]>\n[1, 2, 3]");
        assert_eq!(pretty("{a:1,b:[]}", 80), "{a:1, b:[]}");
    }

    #[test]
    fn long_text_breaks_and_decodes_to_the_same_value() {
        for width in [20, 40, 60, 80, 120, 400] {
            let out = pretty(SAMPLE, width);
            assert_eq!(decode(&out).unwrap(), decode(SAMPLE).unwrap(), "{out}");
            assert!(highlight(&out).contains("\x1b["));
            assert_eq!(
                crate::decode(&crate::decoder::strip_ansi(&highlight(&out))).unwrap(),
                decode(SAMPLE).unwrap()
            );
        }
        let out = pretty(SAMPLE, 60);
        assert!(out.starts_with("<orders:<[\n  id:string,"), "{out}");
        assert!(out.contains("\n([\n  ("), "{out}");
    }

    #[test]
    fn metadata_and_named_types_survive() {
        let text = r#"/* team */ $source="hr" #draft @User<id:number,name:string> <team:string,lead:@User,members:[@User]>("core",(1,"Ada"),[(2,"Alan"),(3,"Grace")])"#;
        let out = pretty(text, 40);
        assert!(out.contains("/* team */"));
        assert!(out.contains("$source=\"hr\""));
        assert_eq!(decode(&out).unwrap(), decode(text).unwrap(), "{out}");
    }

    #[test]
    fn strings_with_brackets_and_commas_are_kept() {
        let text = r#"<[a:string]>[("x, (y) <z> [w]"),("\"q\"")]"#;
        let out = pretty(text, 10);
        assert_eq!(decode(&out).unwrap(), decode(text).unwrap(), "{out}");
    }
}
