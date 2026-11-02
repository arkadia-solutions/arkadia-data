//! `ak-data diff | merge | apply | history`.
//!
//! The history of a document is its `$changes` attribute: a list of change
//! sets (id, date, author, title, description, changes). It is metadata, so
//! the data decodes exactly as before.

use akd::diff::{self, Change, ChangeSet, Info, Op};
use arkadia_data as akd;
use serde_json::Value;

use crate::input;
use crate::textdiff::{self, Kind};
use crate::{emit, ui, Args, Result};

// ---------------------------------------------------------------------------
// Reading
// ---------------------------------------------------------------------------

struct Doc {
    name: String,
    raw: String,
    data: Value,
    history: Vec<ChangeSet>,
    json: bool,
}

fn doc(name: String, raw: String, args: &Args) -> Result<Doc> {
    let parsed = input::parse(&raw, input::Kind::parse(args.get("input"))?)?;
    if let Some(first) = parsed.errors.first() {
        let msg = format!("{name}: {} decode error(s): {first}", parsed.errors.len());
        if args.has("strict") {
            return Err(msg);
        }
        ui::warn(&msg);
    }
    let history = if parsed.json {
        Vec::new()
    } else {
        diff::history(&raw)
    };
    Ok(Doc {
        name,
        raw,
        data: parsed.value,
        history,
        json: parsed.json,
    })
}

/// One document: a file, text or stdin.
fn read_doc(arg: Option<&str>, args: &Args) -> Result<Doc> {
    let (name, raw) = input::source(arg)?;
    doc(name, input::unfence(&raw), args)
}

/// Two documents: two files or texts, or one text / stdin holding both.
fn two_files(args: &Args, cmd: &str, a: &str, b: &str) -> Result<(Doc, Doc)> {
    let [(na, ta), (nb, tb)] = input::two(&args.positional[1..], cmd, a, b)?;
    Ok((doc(na, ta, args)?, doc(nb, tb, args)?))
}

/// `--author`, `$AK_DATA_AUTHOR`, `git config user.name <user.email>`, `$USER`.
fn default_author() -> Option<String> {
    if let Ok(a) = std::env::var("AK_DATA_AUTHOR") {
        if !a.trim().is_empty() {
            return Some(a.trim().to_string());
        }
    }
    let git = |key: &str| {
        std::process::Command::new("git")
            .args(["config", "--get", key])
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
            .filter(|s| !s.is_empty())
    };
    if let Some(name) = git("user.name") {
        return Some(match git("user.email") {
            Some(mail) => format!("{name} <{mail}>"),
            None => name,
        });
    }
    std::env::var("USER")
        .or_else(|_| std::env::var("USERNAME"))
        .ok()
        .filter(|s| !s.is_empty())
}

fn info(args: &Args, default_title: Option<String>) -> Info {
    Info {
        title: args.get("title").map(str::to_string).or(default_title),
        author: args
            .get("author")
            .map(str::to_string)
            .or_else(default_author),
        description: args.get("description").map(str::to_string),
        date: args
            .get("date")
            .map(str::to_string)
            .or_else(|| std::env::var("AK_DATA_DATE").ok().filter(|d| !d.is_empty())),
    }
}

fn base_name(path: &str) -> &str {
    path.rsplit(['/', '\\']).next().unwrap_or(path)
}

// ---------------------------------------------------------------------------
// Colours
// ---------------------------------------------------------------------------

#[derive(Clone, Copy)]
struct Paint(bool);

impl Paint {
    fn p(self, code: &str, text: &str) -> String {
        if self.0 {
            format!("{code}{text}{}", ui::RESET)
        } else {
            text.to_string()
        }
    }
}

const DEL_HI: &str = "\x1b[1;31;48;5;52m";
const INS_HI: &str = "\x1b[1;32;48;5;22m";

fn width() -> usize {
    std::env::var("COLUMNS")
        .ok()
        .and_then(|c| c.parse().ok())
        .unwrap_or(100)
        .max(60)
}

fn shorten(text: &str, max: usize) -> String {
    if text.chars().count() <= max {
        return text.to_string();
    }
    let cut: String = text.chars().take(max.saturating_sub(1)).collect();
    format!("{cut}…")
}

fn counts(c: Paint, changes: &[Change]) -> String {
    let (a, r, ch) = diff::summary(changes);
    format!(
        "{}  {}  {}",
        c.p(ui::GREEN, &format!("+{a} added")),
        c.p(ui::RED, &format!("-{r} removed")),
        c.p(ui::YELLOW, &format!("~{ch} changed")),
    )
}

/// One line per change: `~ users[id=2].name  "Alan" → "Alan T."`.
fn change_lines(c: Paint, changes: &[Change], limit: usize, indent: &str) -> String {
    let mut out = String::new();
    let shown = &changes[..changes.len().min(limit)];
    let pad_to = shown
        .iter()
        .map(|x| x.path.chars().count())
        .max()
        .unwrap_or(0)
        .min(36);
    let room = width().saturating_sub(indent.len() + pad_to + 6).max(24);
    let value = |v: Option<&Value>, max: usize| shorten(&diff::value_akd(v), max);
    for x in shown {
        let pad = " ".repeat(pad_to.saturating_sub(x.path.chars().count()));
        let line = match x.op {
            Op::Add => format!(
                "{} {}{pad}  {}",
                c.p(&format!("{}{}", ui::BOLD, ui::GREEN), "+"),
                c.p(ui::GREEN, &x.path),
                c.p(ui::GREEN, &value(x.new.as_ref(), room)),
            ),
            Op::Remove => format!(
                "{} {}{pad}  {}",
                c.p(&format!("{}{}", ui::BOLD, ui::RED), "-"),
                c.p(ui::RED, &x.path),
                c.p(
                    &format!("{}{}", ui::DIM, ui::RED),
                    &value(x.old.as_ref(), room)
                ),
            ),
            Op::Change => {
                let half = room.saturating_sub(3) / 2;
                format!(
                    "{} {}{pad}  {} {} {}",
                    c.p(&format!("{}{}", ui::BOLD, ui::YELLOW), "~"),
                    c.p(ui::YELLOW, &x.path),
                    c.p(ui::RED, &value(x.old.as_ref(), half)),
                    c.p(ui::DIM, "→"),
                    c.p(ui::GREEN, &value(x.new.as_ref(), half)),
                )
            }
            Op::Order => {
                let half = room.saturating_sub(10) / 2;
                format!(
                    "{} {}{pad}  {} {} {} {}",
                    c.p(&format!("{}{}", ui::BOLD, ui::CYAN), "↕"),
                    c.p(ui::CYAN, &x.path),
                    c.p(ui::DIM, "order"),
                    c.p(ui::RED, &value(x.old.as_ref(), half)),
                    c.p(ui::DIM, "→"),
                    c.p(ui::GREEN, &value(x.new.as_ref(), half)),
                )
            }
        };
        out.push_str(indent);
        out.push_str(&line);
        out.push('\n');
    }
    if changes.len() > shown.len() {
        out.push_str(&format!(
            "{indent}{}\n",
            c.p(
                ui::DIM,
                &format!(
                    "… {} more (--all shows every change)",
                    changes.len() - shown.len()
                )
            )
        ));
    }
    out
}

/// The data as text for the line diff: pretty JSON or laid-out AK-DATA.
fn data_text(v: &Value, json: bool) -> String {
    if json {
        serde_json::to_string_pretty(v).unwrap_or_default()
    } else {
        akd::layout::pretty(&akd::encode(v), 80)
    }
}

/// Git-like hunks with `context` lines around each change; the changed part
/// of a replaced line is highlighted.
fn unified(c: Paint, old: &str, new: &str, context: usize) -> String {
    let (a, b): (Vec<&str>, Vec<&str>) = (old.lines().collect(), new.lines().collect());
    let lines = textdiff::lines(&a, &b);
    let mut out = String::new();
    for range in textdiff::hunks(&lines, context) {
        let part = &lines[range];
        let first = part[0];
        let (o0, n0) = match first.kind {
            Kind::Same => (first.old_no, first.new_no),
            Kind::Del => (first.old_no, first.new_no + 1),
            Kind::Ins => (first.old_no + 1, first.new_no),
        };
        let olen = part.iter().filter(|l| l.kind != Kind::Ins).count();
        let nlen = part.iter().filter(|l| l.kind != Kind::Del).count();
        out.push_str(&c.p(ui::CYAN, &format!("@@ -{o0},{olen} +{n0},{nlen} @@")));
        out.push('\n');
        let mut i = 0;
        while i < part.len() {
            if part[i].kind == Kind::Same {
                out.push_str(&format!(" {}\n", c.p(ui::DIM, part[i].text)));
                i += 1;
                continue;
            }
            let dels: Vec<&str> = part[i..]
                .iter()
                .take_while(|l| l.kind == Kind::Del)
                .map(|l| l.text)
                .collect();
            let j = i + dels.len();
            let ins: Vec<&str> = part[j..]
                .iter()
                .take_while(|l| l.kind == Kind::Ins)
                .map(|l| l.text)
                .collect();
            let paired = dels.len() == ins.len();
            for (k, d) in dels.iter().enumerate() {
                out.push_str(&line(c, '-', d, paired.then(|| ins[k]), ui::RED, DEL_HI));
            }
            for (k, n) in ins.iter().enumerate() {
                out.push_str(&line(c, '+', n, paired.then(|| dels[k]), ui::GREEN, INS_HI));
            }
            i = j + ins.len();
        }
    }
    out
}

fn line(c: Paint, sign: char, text: &str, other: Option<&str>, color: &str, hi: &str) -> String {
    let body = match other {
        Some(o) if c.0 => {
            let (pre, suf) = textdiff::changed_span(text, o);
            let chars: Vec<char> = text.chars().collect();
            let mid_end = chars.len() - suf;
            if pre >= mid_end {
                c.p(color, text)
            } else {
                let s = |r: std::ops::Range<usize>| chars[r].iter().collect::<String>();
                format!(
                    "{}{}{}",
                    c.p(color, &s(0..pre)),
                    c.p(hi, &s(pre..mid_end)),
                    c.p(color, &s(mid_end..chars.len()))
                )
            }
        }
        _ => c.p(color, text),
    };
    format!("{}{body}\n", c.p(color, &sign.to_string()))
}

fn short_date(date: &str) -> String {
    date.get(..10).unwrap_or(date).to_string()
}

fn oneline(c: Paint, set: &ChangeSet) -> String {
    let (a, r, ch) = diff::summary(&set.changes);
    format!(
        "{} {} {}  {} {}",
        c.p(ui::YELLOW, &set.id),
        c.p(ui::DIM, &short_date(&set.date)),
        c.p(ui::CYAN, &shorten(&author_name(set.author.as_deref()), 18)),
        c.p(ui::BOLD, set.title.as_deref().unwrap_or("(no title)")),
        c.p(ui::DIM, &format!("+{a} -{r} ~{ch}")),
    )
}

fn author_name(author: Option<&str>) -> String {
    let a = author.unwrap_or("unknown");
    a.split(" <").next().unwrap_or(a).to_string()
}

/// History entries of `new` that `old` does not have (and the other way).
fn history_delta<'a>(
    old: &'a [ChangeSet],
    new: &'a [ChangeSet],
) -> (Vec<&'a ChangeSet>, Vec<&'a ChangeSet>) {
    let only_new = new
        .iter()
        .filter(|s| !old.iter().any(|o| o.id == s.id))
        .collect();
    let only_old = old
        .iter()
        .filter(|s| !new.iter().any(|n| n.id == s.id))
        .collect();
    (only_new, only_old)
}

// ---------------------------------------------------------------------------
// Writing
// ---------------------------------------------------------------------------

/// The document text: AK-DATA (data + `$changes`) or JSON (data only).
/// Returns the text and whether a history had to be left out.
fn document(
    data: &Value,
    history: &[ChangeSet],
    args: &Args,
    target: Option<&str>,
) -> (String, bool) {
    let json = args.get("format") == Some("json") || target.is_some_and(|t| t.ends_with(".json"));
    let to_terminal = target.is_none() && ui::enabled() && args.get("output").is_none();
    if json {
        let text = if args.has("compact") {
            serde_json::to_string(data).unwrap_or_default()
        } else {
            serde_json::to_string_pretty(data).unwrap_or_default()
        };
        return (text, !history.is_empty());
    }
    let compact = diff::with_history(data, history);
    let text = if args.has("compact") {
        compact
    } else {
        akd::layout::pretty(&compact, args.number("width", 80))
    };
    let text = if to_terminal {
        akd::layout::highlight(&text)
    } else {
        text
    };
    (text, false)
}

fn write_file(path: &str, text: &str) -> Result<()> {
    let text = if text.ends_with('\n') {
        text.to_string()
    } else {
        format!("{text}\n")
    };
    std::fs::write(path, text).map_err(|e| format!("cannot write {path}: {e}"))
}

fn exit_code(args: &Args, changed: bool) {
    if args.has("exit-code") && changed {
        std::process::exit(1);
    }
}

// ---------------------------------------------------------------------------
// diff
// ---------------------------------------------------------------------------

/// `diff` writes the changes as a patch (coloured in a terminal) — what -o
/// saves for `ak-data apply`; --info shows them for people instead.
pub fn run_diff(args: &Args) -> Result<()> {
    let (old, new) = two_files(args, "diff", "old", "new")?;
    let changes = diff::diff(&old.data, &new.data);
    let patch_type = args.get("to").or_else(|| args.get("format"));
    let target = args.get("output");
    // --info (or a view option): the changes for people — paths, context,
    // history. Otherwise the patch itself, what -o saves for `ak-data apply`.
    let info_view = args.has("info")
        || ["paths", "full", "context", "akd", "limit", "all", "plain"]
            .iter()
            .any(|o| args.has(o));
    if info_view && target.is_none() {
        let c = Paint(ui::enabled() && !args.has("plain"));
        print_out(&diff_view(c, &old, &new, &changes, args));
        exit_code(args, !changes.is_empty());
        return Ok(());
    }
    // A patch: one change set, ready for `ak-data apply`.
    let parent = old.history.last().map(|s| s.id.as_str());
    let set = ChangeSet::new(changes.clone(), &info(args, None), parent);
    let as_json = match patch_type.unwrap_or("akd").to_ascii_lowercase().as_str() {
        "json" => true,
        "akd" | "ak-data" => false,
        other => {
            return Err(format!(
                "unknown patch type '{other}': -t akd (default) or json"
            ))
        }
    };
    let to_terminal = target.is_none() && ui::enabled();
    let text = if as_json {
        let t = if args.has("compact") {
            serde_json::to_string(&set.to_json()).unwrap_or_default()
        } else {
            serde_json::to_string_pretty(&set.to_json()).unwrap_or_default()
        };
        if to_terminal {
            ui::highlight_json(&t)
        } else {
            t
        }
    } else {
        let compact = akd::encode(&set.to_json());
        let t = if args.has("compact") {
            compact
        } else {
            akd::layout::pretty(&compact, args.number("width", 80))
        };
        if to_terminal {
            akd::layout::highlight(&t)
        } else {
            t
        }
    };
    match target {
        Some(path) => {
            write_file(path, &text)?;
            if info_view {
                print_out(&diff_view(Paint(ui::enabled()), &old, &new, &changes, args));
            }
            ui::info(&format!(
                "Patch written to {path} ({} change(s)). Apply it with: ak-data apply <file> {path}",
                changes.len()
            ));
        }
        None => print_out(&text),
    }
    exit_code(args, !changes.is_empty());
    Ok(())
}

fn print_out(text: &str) {
    let mut out = std::io::stdout().lock();
    let _ = std::io::Write::write_all(&mut out, text.as_bytes());
    if !text.ends_with('\n') {
        let _ = std::io::Write::write_all(&mut out, b"\n");
    }
}

fn diff_view(c: Paint, old: &Doc, new: &Doc, changes: &[Change], args: &Args) -> String {
    let mut out = format!(
        "{} {} {} {}   {}\n",
        c.p(&format!("{}{}", ui::BOLD, ui::MAGENTA), "diff"),
        c.p(ui::BOLD, &old.name),
        c.p(ui::DIM, "→"),
        c.p(ui::BOLD, &new.name),
        counts(c, changes),
    );
    let (only_new, only_old) = history_delta(&old.history, &new.history);
    if changes.is_empty() && only_new.is_empty() && only_old.is_empty() {
        out.push_str(&format!(
            "  {}\n",
            c.p(ui::GREEN, "✓ no changes — the data is the same")
        ));
        return out;
    }
    let all = args.has("all") || args.has("paths");
    if !changes.is_empty() {
        out.push('\n');
        out.push_str(&change_lines(
            c,
            changes,
            if all {
                usize::MAX
            } else {
                args.number("limit", 12)
            },
            "  ",
        ));
    }
    if !args.has("paths") && !changes.is_empty() {
        // The changes in place, with the lines around them.
        // One value per line reads best; --akd shows the AK-DATA layout.
        let json = !args.has("akd");
        let context = args.number("context", 3);
        let (a, b) = (data_text(&old.data, json), data_text(&new.data, json));
        out.push('\n');
        if args.has("full") {
            out.push_str(&unified(c, &a, &b, usize::MAX / 4));
        } else {
            out.push_str(&unified(c, &a, &b, context));
        }
    }
    if !only_new.is_empty() || !only_old.is_empty() {
        out.push('\n');
        out.push_str(&c.p(ui::BOLD, "history"));
        out.push('\n');
        for s in only_new {
            out.push_str(&format!("  {} {}\n", c.p(ui::GREEN, "+"), oneline(c, s)));
        }
        for s in only_old {
            out.push_str(&format!("  {} {}\n", c.p(ui::RED, "-"), oneline(c, s)));
        }
    }
    out
}

// ---------------------------------------------------------------------------
// merge
// ---------------------------------------------------------------------------

pub fn run_merge(args: &Args) -> Result<()> {
    let (old, new) = two_files(args, "merge", "old", "new")?;
    let latest = args.has("latest");
    let data = if latest {
        new.data.clone()
    } else {
        diff::merge(&old.data, &new.data)
    };
    let changes = diff::diff(&old.data, &data);
    // OLD's history, the entries only NEW has, then this merge.
    let mut history = old.history.clone();
    history.extend(
        new.history
            .iter()
            .filter(|s| !old.history.iter().any(|o| o.id == s.id))
            .cloned(),
    );
    let default_title = Some(if latest {
        format!("Take {} as it is", base_name(&new.name))
    } else {
        format!("Merge {}", base_name(&new.name))
    });
    let set = (!changes.is_empty()).then(|| {
        ChangeSet::new(
            changes.clone(),
            &info(args, default_title),
            history.last().map(|s| s.id.as_str()),
        )
    });
    if let Some(s) = &set {
        history.push(s.clone());
    }
    let keep = if args.has("no-history") {
        &[][..]
    } else {
        &history[..]
    };
    let (text, dropped) = document(&data, keep, args, args.get("output"));
    emit(&text, args)?;
    if !args.has("quiet") {
        let c = Paint(ui::stderr_enabled());
        let mode = if latest { "latest" } else { "merged" };
        let mut view = format!(
            "{} {} {} {} {}   {}\n",
            c.p(&format!("{}{}", ui::BOLD, ui::MAGENTA), "merge"),
            c.p(ui::BOLD, &old.name),
            c.p(ui::DIM, "+"),
            c.p(ui::BOLD, &new.name),
            c.p(ui::DIM, &format!("({mode})")),
            counts(c, &changes),
        );
        if let Some(s) = &set {
            view.push_str(&format!("  {}\n", oneline(c, s)));
        }
        view.push_str(&change_lines(
            c,
            &changes,
            if args.has("all") {
                usize::MAX
            } else {
                args.number("limit", 20)
            },
            "  ",
        ));
        if dropped {
            view.push_str(&c.p(
                ui::YELLOW,
                "  JSON keeps only the data: the history ($changes) is in AK-DATA output only\n",
            ));
        }
        eprint!("\n{view}");
    }
    exit_code(args, !changes.is_empty());
    Ok(())
}

// ---------------------------------------------------------------------------
// apply
// ---------------------------------------------------------------------------

/// The change sets in a patch: a change set, a list of them, a list of
/// changes, or a document with a history (`--change ID`, or every entry the
/// target does not have yet).
fn patch_sets(patch: &Doc, target: &Doc, args: &Args) -> Result<Vec<ChangeSet>> {
    let wanted: Vec<&str> = args
        .get("change")
        .map(|v| {
            v.split(',')
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .collect()
        })
        .unwrap_or_default();
    let pick = |list: Vec<ChangeSet>| -> Result<Vec<ChangeSet>> {
        if wanted.is_empty() {
            return Ok(list);
        }
        wanted
            .iter()
            .map(|w| {
                let found: Vec<&ChangeSet> = list.iter().filter(|s| s.id.starts_with(w)).collect();
                match found.as_slice() {
                    [one] => Ok((*one).clone()),
                    [] => Err(format!("no change {w} in {}", patch.name)),
                    _ => Err(format!("change id {w} is ambiguous in {}", patch.name)),
                }
            })
            .collect()
    };
    if !patch.history.is_empty() {
        let sets = pick(patch.history.clone())?;
        if !wanted.is_empty() {
            return Ok(sets);
        }
        return Ok(sets
            .into_iter()
            .filter(|s| !target.history.iter().any(|t| t.id == s.id))
            .collect());
    }
    let is_set = |v: &Value| v.get("changes").is_some_and(Value::is_array);
    let is_change = |v: &Value| v.get("op").is_some() && v.get("path").is_some();
    let sets = match &patch.data {
        v if is_set(v) => vec![ChangeSet::from_json(v)?],
        Value::Array(l) if !l.is_empty() && l.iter().all(is_set) => {
            l.iter().map(ChangeSet::from_json).collect::<std::result::Result<_, _>>()?
        }
        Value::Array(l) if l.iter().all(is_change) => {
            let changes = diff::changes_from_json(&patch.data)?;
            vec![ChangeSet::new(changes, &info(args, None), None)]
        }
        _ => {
            return Err(format!(
                "{} is not a patch (a change set from ak-data diff, or a document with $changes). To bring in a newer file use: ak-data merge",
                patch.name
            ))
        }
    };
    pick(sets)
}

pub fn run_apply(args: &Args) -> Result<()> {
    let (target, patch) = two_files(args, "apply", "data", "patch")?;
    let mut sets = patch_sets(&patch, &target, args)?;
    if sets.is_empty() {
        ui::info(&format!(
            "Nothing to apply: {} already has every change of {}.",
            target.name, patch.name
        ));
        return Ok(());
    }
    let mut history = target.history.clone();
    let parent = |h: &[ChangeSet]| h.last().map(|s| s.id.clone());
    if args.has("reverse") {
        // Undo: a new change set with the reversed changes.
        sets = sets
            .iter()
            .rev()
            .map(|s| {
                let title = format!("Revert \"{}\"", s.title.as_deref().unwrap_or(&s.id));
                ChangeSet::new(diff::reverse(&s.changes), &info(args, Some(title)), None)
            })
            .collect();
    } else if args.get("title").is_some()
        || args.get("description").is_some()
        || args.get("author").is_some()
    {
        for s in &mut sets {
            if let Some(t) = args.get("title") {
                s.title = Some(t.to_string());
            }
            if let Some(d) = args.get("description") {
                s.description = Some(d.to_string());
            }
            if let Some(a) = args.get("author") {
                s.author = Some(a.to_string());
            }
        }
    }
    let force = args.has("force");
    let mut data = target.data.clone();
    let mut skipped = Vec::new();
    for s in &mut sets {
        let (next, conflicts) = diff::apply_with(&data, &s.changes, force);
        if !conflicts.is_empty() && !force {
            let c = Paint(ui::stderr_enabled());
            let mut msg = format!(
                "{} change(s) of {} do not fit {}:\n",
                conflicts.len(),
                c.p(
                    ui::YELLOW,
                    &match (s.title.as_deref(), s.id.as_str()) {
                        (Some(t), _) => format!("\"{t}\""),
                        (None, "") => "the patch".to_string(),
                        (None, id) => id.to_string(),
                    }
                ),
                target.name
            );
            for x in &conflicts {
                msg.push_str(&format!(
                    "  {} {}  {}\n",
                    c.p(ui::RED, "✗"),
                    c.p(ui::BOLD, &x.path),
                    x.reason
                ));
            }
            msg.push_str("Nothing was written. --force applies what fits (and writes over different old values).");
            return Err(msg);
        }
        skipped.extend(conflicts);
        data = next;
        // Re-chained ids for change sets made here (reverts); kept ids for
        // entries that come from another history.
        if args.has("reverse") || s.id.is_empty() {
            *s = ChangeSet::new(
                s.changes.clone(),
                &Info {
                    title: s.title.clone(),
                    author: s.author.clone(),
                    description: s.description.clone(),
                    date: Some(s.date.clone()).filter(|d| !d.is_empty()),
                },
                parent(&history).as_deref(),
            );
        }
        if !history.iter().any(|h| h.id == s.id) {
            history.push(s.clone());
        }
    }
    let all_changes: Vec<Change> = sets.iter().flat_map(|s| s.changes.clone()).collect();
    let real = diff::diff(&target.data, &data);
    let c = Paint(ui::stderr_enabled());
    let mut view = format!(
        "{} {} {} {}   {}\n",
        c.p(
            &format!("{}{}", ui::BOLD, ui::MAGENTA),
            if args.has("reverse") {
                "revert"
            } else {
                "apply"
            }
        ),
        c.p(ui::BOLD, &patch.name),
        c.p(ui::DIM, "→"),
        c.p(ui::BOLD, &target.name),
        counts(c, &real),
    );
    for s in &sets {
        view.push_str(&format!("  {}\n", oneline(c, s)));
    }
    view.push_str(&change_lines(
        c,
        &all_changes,
        if args.has("all") {
            usize::MAX
        } else {
            args.number("limit", 20)
        },
        "  ",
    ));
    for x in &skipped {
        view.push_str(&format!(
            "  {} {}  {}\n",
            c.p(ui::YELLOW, "skipped"),
            x.path,
            x.reason
        ));
    }
    let keep_history = !args.has("no-history");
    let keep = if keep_history {
        &history[..]
    } else {
        &target.history[..]
    };
    if args.has("dry-run") {
        eprint!("{view}");
        ui::info("Dry run: nothing was written.");
        return Ok(());
    }
    let target_path = if args.has("stdout") {
        None
    } else {
        // In place when the data came from a file; text and stdin print.
        args.get("output")
            .map(str::to_string)
            .or_else(|| {
                std::path::Path::new(&target.name)
                    .is_file()
                    .then(|| target.name.clone())
            })
            .filter(|p| p != "-")
    };
    let (text, dropped) = document(&data, keep, args, target_path.as_deref());
    match &target_path {
        Some(p) => {
            write_file(p, &text)?;
            view.push_str(&format!("  {} {p}\n", c.p(ui::DIM, "written to")));
        }
        None => {
            let out = std::io::stdout();
            let mut lock = out.lock();
            let _ = std::io::Write::write_all(&mut lock, format!("{text}\n").as_bytes());
        }
    }
    if dropped && keep_history {
        view.push_str(&c.p(
            ui::YELLOW,
            "  JSON keeps only the data: write AK-DATA (-o file.akd) to keep the history ($changes)\n",
        ));
    }
    if !args.has("quiet") {
        eprint!("{view}");
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// history
// ---------------------------------------------------------------------------

fn ago(date: &str) -> String {
    let (Some(then), Ok(now)) = (
        diff::parse_date(date),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH),
    ) else {
        return String::new();
    };
    let s = now.as_secs() as i64 - then;
    let (n, unit) = match s {
        s if s < 60 => return "just now".to_string(),
        s if s < 3600 => (s / 60, "minute"),
        s if s < 86_400 => (s / 3600, "hour"),
        s if s < 30 * 86_400 => (s / 86_400, "day"),
        s if s < 365 * 86_400 => (s / (30 * 86_400), "month"),
        s => (s / (365 * 86_400), "year"),
    };
    format!("{n} {unit}{} ago", if n == 1 { "" } else { "s" })
}

fn wrap(text: &str, width: usize) -> Vec<String> {
    let mut out = Vec::new();
    for para in text.split('\n') {
        let mut line = String::new();
        for word in para.split_whitespace() {
            if !line.is_empty() && line.chars().count() + 1 + word.chars().count() > width {
                out.push(std::mem::take(&mut line));
            }
            if !line.is_empty() {
                line.push(' ');
            }
            line.push_str(word);
        }
        out.push(line);
    }
    out
}

pub fn run_history(args: &Args) -> Result<()> {
    let doc = read_doc(args.positional.get(1).map(String::as_str), args)?;
    let path = &doc.name;
    if doc.json {
        return Err(format!(
            "{path} is JSON: a history is kept in AK-DATA files (ak-data merge / apply write it as $changes)"
        ));
    }
    let _ = &doc.raw;
    let mut sets: Vec<(usize, ChangeSet)> = doc.history.iter().cloned().enumerate().collect();
    let total = sets.len();
    // Filters: --path, --author, --change.
    if let Some(p) = args.get("path") {
        sets = sets
            .into_iter()
            .filter_map(|(i, mut s)| {
                s.changes.retain(|c| {
                    c.path == p
                        || c.path.starts_with(&format!("{p}."))
                        || c.path.starts_with(&format!("{p}["))
                });
                (!s.changes.is_empty()).then_some((i, s))
            })
            .collect();
    }
    if let Some(a) = args.get("author") {
        let a = a.to_lowercase();
        sets.retain(|(_, s)| {
            s.author
                .as_deref()
                .unwrap_or("")
                .to_lowercase()
                .contains(&a)
        });
    }
    if let Some(id) = args.get("change") {
        sets.retain(|(_, s)| s.id.starts_with(id));
    }
    if !args.has("reverse") {
        sets.reverse(); // newest first, like git log
    }
    if let Some(n) = args.get("max").and_then(|v| v.parse::<usize>().ok()) {
        sets.truncate(n);
    }
    if args.get("format") == Some("json") {
        let list = Value::Array(sets.iter().map(|(_, s)| s.to_json()).collect());
        return emit(
            &serde_json::to_string_pretty(&list).unwrap_or_default(),
            args,
        );
    }
    let c = Paint(ui::enabled());
    if total == 0 {
        return emit(
            &c.p(
                ui::DIM,
                &format!("{path} has no history yet ($changes): ak-data merge / apply record one."),
            ),
            args,
        );
    }
    let patch = args.has("patch") || args.has("prompt") || args.get("change").is_some();
    let mut out = String::new();
    for (k, (i, s)) in sets.iter().enumerate() {
        if args.has("oneline") {
            out.push_str(&oneline(c, s));
            out.push('\n');
            continue;
        }
        if k > 0 {
            out.push('\n');
        }
        let latest = if *i + 1 == total {
            c.p(&format!("{}{}", ui::BOLD, ui::CYAN), " (latest)")
        } else {
            String::new()
        };
        out.push_str(&format!(
            "{}{latest}\n",
            c.p(ui::YELLOW, &format!("change {}", s.id))
        ));
        out.push_str(&format!(
            "Author: {}\n",
            s.author.as_deref().unwrap_or("unknown")
        ));
        let when = ago(&s.date);
        out.push_str(&format!(
            "Date:   {}{}\n\n",
            s.date.replacen('T', " ", 1).replace('Z', " UTC"),
            if when.is_empty() {
                String::new()
            } else {
                c.p(ui::DIM, &format!("  ({when})"))
            }
        ));
        out.push_str(&format!(
            "    {}\n",
            c.p(ui::BOLD, s.title.as_deref().unwrap_or("(no title)"))
        ));
        if let Some(d) = &s.description {
            out.push('\n');
            for l in wrap(d, 72) {
                out.push_str(&format!("    {l}\n"));
            }
        }
        out.push('\n');
        let limit = if patch || args.has("all") {
            usize::MAX
        } else {
            args.number("limit", 8)
        };
        if patch {
            for x in &s.changes {
                out.push_str(&full_change(c, x));
            }
        } else {
            out.push_str(&change_lines(c, &s.changes, limit, "    "));
        }
        out.push_str(&format!("    {}\n", counts(c, &s.changes)));
    }
    emit(out.trim_end(), args)
}

/// A change with its whole values (`history -p`).
fn full_change(c: Paint, x: &Change) -> String {
    let block = |v: Option<&Value>, sign: char, color: &str| -> String {
        let text = match v {
            Some(v) if v.is_object() || v.is_array() => akd::layout::pretty(&akd::encode(v), 72),
            v => diff::value_akd(v),
        };
        text.lines()
            .map(|l| format!("      {}\n", c.p(color, &format!("{sign} {l}"))))
            .collect()
    };
    let (sym, color) = match x.op {
        Op::Add => ("+", ui::GREEN),
        Op::Remove => ("-", ui::RED),
        Op::Change => ("~", ui::YELLOW),
        Op::Order => ("↕", ui::CYAN),
    };
    let mut out = format!(
        "    {} {}\n",
        c.p(&format!("{}{color}", ui::BOLD), sym),
        c.p(color, &x.path)
    );
    if x.op != Op::Add {
        out.push_str(&block(x.old.as_ref(), '-', ui::RED));
    }
    if x.op != Op::Remove {
        out.push_str(&block(x.new.as_ref(), '+', ui::GREEN));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn view_lists_every_change() {
        let changes = diff::diff(&json!({"a": 1, "b": [1]}), &json!({"a": 2, "c": "x"}));
        let text = change_lines(Paint(false), &changes, 50, "");
        assert!(text.contains("~ a  1 → 2"), "{text}");
        assert!(text.contains("+ c  \"x\""), "{text}");
        assert!(counts(Paint(false), &changes).contains("+1 added  -1 removed  ~1 changed"));
    }

    #[test]
    fn unified_shows_context() {
        let a = "a\nb\nc\nd\ne\nf\ng\nh";
        let b = "a\nb\nc\nd\nE\nf\ng\nh";
        let text = unified(Paint(false), a, b, 1);
        assert_eq!(text, "@@ -4,3 +4,3 @@\n d\n-e\n+E\n f\n");
    }

    #[test]
    fn wraps_descriptions() {
        assert_eq!(wrap("one two three", 7), vec!["one two", "three"]);
    }
}
