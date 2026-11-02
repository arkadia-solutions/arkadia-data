//! Terminal look of `ak-data`: logo, banners and aligned, coloured sections
//! (the same style as the earlier Python `akd`). Colours are used only when
//! stdout is a terminal; `NO_COLOR` or `--no-color` turns them off,
//! `CLICOLOR_FORCE=1` / `COLOR=always` or `--color=always` forces them.

use std::io::IsTerminal;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::OnceLock;

static ENABLED: OnceLock<bool> = OnceLock::new();
static COLUMN: AtomicUsize = AtomicUsize::new(0);

/// Minimum width of the flag column for the following [`options`] sections.
pub fn set_column(width: usize) {
    COLUMN.store(width, Ordering::Relaxed);
}

/// Decides once whether ANSI colours are written (call before printing).
pub fn init(no_color: bool, force: bool) {
    let env_off = std::env::var_os("NO_COLOR").is_some_and(|v| !v.is_empty());
    let env_on = std::env::var("CLICOLOR_FORCE").is_ok_and(|v| v != "0")
        || std::env::var("COLOR").is_ok_and(|v| v == "always");
    let on = if no_color || env_off {
        false
    } else {
        force || env_on || std::io::stdout().is_terminal()
    };
    let _ = ENABLED.set(on);
}

/// True when ANSI colours are written to stdout.
pub fn enabled() -> bool {
    *ENABLED.get().unwrap_or(&false)
}

/// True when colours may be used on stderr (errors, notes).
pub fn stderr_enabled() -> bool {
    enabled() || (std::io::stderr().is_terminal() && std::env::var_os("NO_COLOR").is_none())
}

pub const RESET: &str = "\x1b[0m";
pub const BOLD: &str = "\x1b[1m";
pub const DIM: &str = "\x1b[2m";
pub const WHITE: &str = "\x1b[37m";
pub const YELLOW: &str = "\x1b[33m";
pub const GREEN: &str = "\x1b[32m";
pub const RED: &str = "\x1b[31m";
pub const BLUE: &str = "\x1b[34m";
pub const CYAN: &str = "\x1b[36m";
pub const MAGENTA: &str = "\x1b[35m";
/// Arkadia green (tool name in USAGE).
pub const MAIN: &str = "\x1b[38;5;34m";

/// `code` + `text` + reset when colours are on, otherwise `text`.
pub fn paint(code: &str, text: &str) -> String {
    if enabled() {
        format!("{code}{text}{RESET}")
    } else {
        text.to_string()
    }
}

fn paint_err(code: &str, text: &str) -> String {
    if stderr_enabled() {
        format!("{code}{text}{RESET}")
    } else {
        text.to_string()
    }
}

const LOGO: &str = r"
                                   ; i  :J
                               U, .j..fraaM.  nl
                            b h.obWMkkWWMMWMCdkvz,k
                         ! .mQWM:o hiMoMW v.uaXMdohbi
                        hI,MMmaIao.Wo .IMkoh FCMwqoXa
                      ,.c.aWdM. d,aToW  .    Mb!. MopfQ.L
                       jhj.xoM :k    aCu F: w MpmqMvMMI,I
                      bzMhz:W    .Mw . o lYh ai M iMa pM.j
                     hzqWWM;    M;o.WMWWMkMX f.a aa bModpo.
                     ;tMbbv   xp oJMMWWWWMMMM iv  dLMXakM:T
                       mdh        MMWWWWWWWbQLCzurjktvMor
                      ,QFw ;M,b .MWWWWWWWMWMWd  xz   M,kd X
                      qjMIo IMTW.WWWWWMWWWM.o.I   rpULaMdi.
                       .mMM  uoWWWMWWWWWWp qM,,M l M;mMbrI
                        f nm  MMW MWWjMuMj  I  o   LbMac
                              WWdMWWWW Mv a.b..aauMhMwQf
                              MoWWW,WWtjonJMWtoMdoaoMI
                              MMMM Mi    xd:Mm tMwo Cr,
                             xMMc .otqokWMMMao:oio.
                             MW    .   C..MkTIo
                            WW
                           QWM
                           WW
                          uMW
                          WW
                          MW";

/// One row of a help section: flags (or a command / argument) and its description.
pub struct Opt {
    pub flags: &'static str,
    pub desc: &'static str,
    pub default: Option<&'static str>,
}

/// Shorthand for [`Opt`] without a default.
pub const fn opt(flags: &'static str, desc: &'static str) -> Opt {
    Opt {
        flags,
        desc,
        default: None,
    }
}

/// Shorthand for [`Opt`] with a default value.
pub const fn opt_default(flags: &'static str, desc: &'static str, default: &'static str) -> Opt {
    Opt {
        flags,
        desc,
        default: Some(default),
    }
}

/// Wraps `text` to `width` columns.
fn wrap(text: &str, width: usize) -> Vec<String> {
    let mut lines = vec![];
    let mut line = String::new();
    for word in text.split_whitespace() {
        if !line.is_empty() && line.chars().count() + 1 + word.chars().count() > width {
            lines.push(std::mem::take(&mut line));
        }
        if !line.is_empty() {
            line.push(' ');
        }
        line.push_str(word);
    }
    if !line.is_empty() {
        lines.push(line);
    }
    lines
}

/// Logo, tool name, description and metadata (label → value).
pub fn banner(
    out: &mut String,
    title: &str,
    color: &str,
    description: &str,
    meta: &[(&str, String)],
) {
    out.push_str(&paint(color, LOGO));
    out.push_str("\n\n\n");
    out.push_str(&format!(
        "  {}\n",
        paint(&format!("{BOLD}{WHITE}"), &title.to_uppercase())
    ));
    out.push_str(&format!("   {}\n", paint(DIM, &"-".repeat(50))));
    if !description.is_empty() {
        for line in wrap(description, 65) {
            out.push_str(&format!("   {}\n", paint(WHITE, &line)));
        }
        out.push('\n');
    }
    let width = meta
        .iter()
        .map(|(k, _)| k.chars().count())
        .max()
        .unwrap_or(0)
        + 2;
    for (i, (key, value)) in meta.iter().enumerate() {
        let label = format!("{key}:");
        let pad = " ".repeat(width.saturating_sub(label.chars().count()) + 4);
        let color = if i == 0 { YELLOW } else { CYAN };
        out.push_str(&format!(
            "   {}{pad}{}\n",
            paint(DIM, &label),
            paint(color, value)
        ));
    }
    out.push_str("\n\n");
}

/// `USAGE:` line.
pub fn usage(out: &mut String, tool: &str, command: &str, args: &str) {
    out.push_str(&format!("{}\n", paint(BOLD, "USAGE:")));
    let mut line = format!("   {}", paint(MAIN, tool));
    if !command.is_empty() {
        line.push(' ');
        line.push_str(&paint(BOLD, command));
    }
    if !args.is_empty() {
        line.push(' ');
        line.push_str(args);
    }
    out.push_str(&line);
    out.push_str("\n\n");
}

/// A titled section of aligned options; flags starting with `-` are green,
/// commands and arguments cyan.
pub fn options(out: &mut String, title: &str, rows: &[Opt]) {
    if rows.is_empty() {
        return;
    }
    out.push_str(&format!(
        "{}\n",
        paint(YELLOW, &format!("{}:", title.to_uppercase()))
    ));
    // At least column(), so the sections of one screen line up.
    let col = (rows
        .iter()
        .map(|o| o.flags.chars().count())
        .max()
        .unwrap_or(0)
        + 4)
    .max(COLUMN.load(Ordering::Relaxed));
    for o in rows {
        let color = if o.flags.starts_with('-') {
            GREEN
        } else {
            CYAN
        };
        let pad = " ".repeat(col - o.flags.chars().count());
        let mut line = format!("   {}{pad}{}", paint(color, o.flags), paint(WHITE, o.desc));
        if let Some(d) = o.default {
            line.push(' ');
            line.push_str(&paint(DIM, &format!("[default: {d}]")));
        }
        out.push_str(&line);
        out.push('\n');
    }
    out.push('\n');
}

/// `EXAMPLES:` — commands with a dim comment.
pub fn examples(out: &mut String, rows: &[(&str, &str)]) {
    out.push_str(&format!("{}\n", paint(YELLOW, "EXAMPLES:")));
    let col = rows
        .iter()
        .map(|(c, _)| c.chars().count())
        .max()
        .unwrap_or(0)
        + 4;
    for (cmd, note) in rows {
        if note.is_empty() {
            out.push_str(&format!("   {}\n", paint(BOLD, cmd)));
            continue;
        }
        let pad = " ".repeat(col - cmd.chars().count());
        out.push_str(&format!(
            "   {}{pad}{}\n",
            paint(BOLD, cmd),
            paint(DIM, note)
        ));
    }
    out.push('\n');
}

/// A dim note line at the end of a help screen.
pub fn note(out: &mut String, text: &str) {
    for line in wrap(text, 76) {
        out.push_str(&format!("   {}\n", paint(DIM, &line)));
    }
    out.push('\n');
}

/// JSON text with ANSI colours: keys yellow, strings green, numbers blue,
/// `true` / `false` magenta, `null` grey (the AK-DATA palette).
pub fn highlight_json(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len() * 2);
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '"' {
            let start = i;
            i += 1;
            while i < chars.len() && chars[i] != '"' {
                i += if chars[i] == '\\' { 2 } else { 1 };
            }
            i = (i + 1).min(chars.len());
            let s: String = chars[start..i].iter().collect();
            let mut j = i;
            while j < chars.len() && chars[j] == ' ' {
                j += 1;
            }
            let color = if chars.get(j) == Some(&':') {
                "\x1b[93m"
            } else {
                "\x1b[92m"
            };
            out.push_str(&format!("{color}{s}{RESET}"));
            continue;
        }
        if c == '-' || c.is_ascii_digit() {
            let start = i;
            while i < chars.len() && (chars[i].is_ascii_alphanumeric() || "+-.".contains(chars[i]))
            {
                i += 1;
            }
            let s: String = chars[start..i].iter().collect();
            out.push_str(&format!("\x1b[94m{s}{RESET}"));
            continue;
        }
        if c.is_ascii_alphabetic() {
            let start = i;
            while i < chars.len() && chars[i].is_ascii_alphabetic() {
                i += 1;
            }
            let s: String = chars[start..i].iter().collect();
            let color = if s == "null" { "\x1b[90m" } else { "\x1b[95m" };
            out.push_str(&format!("{color}{s}{RESET}"));
            continue;
        }
        if "{}[],:".contains(c) {
            out.push_str(&format!("\x1b[37m{c}{RESET}"));
        } else {
            out.push(c);
        }
        i += 1;
    }
    out
}

/// `Error: …` on stderr (red when stderr is a terminal).
pub fn error(message: &str) {
    eprintln!("{} {message}", paint_err(&format!("{BOLD}{RED}"), "Error:"));
}

/// A dim informational line on stderr.
pub fn info(message: &str) {
    eprintln!("{}", paint_err(DIM, message));
}

/// A yellow warning on stderr.
pub fn warn(message: &str) {
    eprintln!("{}", paint_err(YELLOW, message));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wrap_keeps_words_and_width() {
        let lines = wrap("one two three four five six", 9);
        assert_eq!(lines, vec!["one two", "three", "four five", "six"]);
    }
}
