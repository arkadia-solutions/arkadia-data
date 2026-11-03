//! `ak-data` — command line tool for AK-DATA (Arkadia Data Format).
//!
//!   ak-data data.json [-c]             anything → AK-DATA (laid out, or one line)
//!   echo '{"a":1}' | ak-data          stdin or text works too ('<a:number>(1)')
//!   ak-data data.akd -t json           … or JSON / TOON (-i json|akd, -o file)
//!   ak-data diff old.json new.json     the patch (-o: saved for apply; --info: with context)
//!   ak-data merge old.akd new.json     joined data + the change in its history ($changes)
//!   ak-data apply data.akd patch.akd   apply a patch / change (with or without history)
//!   ak-data history data.akd           who changed what and when, like git log
//!   ak-data prompt data.json -q "…"    copy-paste prompt for a chat model
//!   ak-data example [--prompt]         a random example (with a prompt for AI)
//!   ak-data info [section]             the complete, coloured definition

use std::collections::HashMap;
use std::io::{self, IsTerminal, Read, Write};
use std::process::ExitCode;

use akd::{Answer, EncodeOptions, Format};
use arkadia_data as akd;
use serde_json::Value;

mod cmd_diff;
mod cmd_example;
mod help;
mod info;
mod input;
mod textdiff;
mod ui;

const WITH_VALUE: &[&str] = &[
    "indent",
    "output",
    "format",
    "question",
    "answer",
    "answer-name",
    "example",
    "seed",
    "width",
    "limit",
    "title",
    "author",
    "description",
    "date",
    "change",
    "context",
    "max",
    "path",
    "to",
    "input",
];

#[derive(Default)]
struct Args {
    positional: Vec<String>,
    flags: HashMap<String, String>,
}

impl Args {
    fn parse(argv: &[String]) -> Args {
        let mut out = Args::default();
        let mut i = 0;
        while i < argv.len() {
            let a = &argv[i];
            if a == "-" {
                out.positional.push(a.clone());
            } else if let Some(rest) = a.strip_prefix("--") {
                if let Some((k, v)) = rest.split_once('=') {
                    out.flags.insert(k.to_string(), v.to_string());
                } else if WITH_VALUE.contains(&rest) {
                    i += 1;
                    out.flags
                        .insert(rest.to_string(), argv.get(i).cloned().unwrap_or_default());
                } else {
                    out.flags.insert(rest.to_string(), "true".to_string());
                }
            } else if a.len() > 1 && a.starts_with('-') {
                let short = &a[1..];
                let k = match short {
                    "c" => "compact",
                    "o" => "output",
                    "f" => "format",
                    "q" => "question",
                    "a" => "answer",
                    "e" => "example",
                    "p" => "prompt",
                    "h" => "help",
                    "v" => "version",
                    "m" => "title",
                    "t" => "to",
                    "i" => "input",
                    "R" => "reverse",
                    "U" => "context",
                    "n" => "max",
                    other => other,
                }
                .to_string();
                if WITH_VALUE.contains(&k.as_str()) {
                    i += 1;
                    out.flags
                        .insert(k, argv.get(i).cloned().unwrap_or_default());
                } else {
                    out.flags.insert(k, "true".to_string());
                }
            } else {
                out.positional.push(a.clone());
            }
            i += 1;
        }
        out
    }

    fn has(&self, key: &str) -> bool {
        self.flags.contains_key(key)
    }

    fn get(&self, key: &str) -> Option<&str> {
        self.flags
            .get(key)
            .map(String::as_str)
            .filter(|v| !v.is_empty() && *v != "true")
    }

    fn number(&self, key: &str, default: usize) -> usize {
        self.get(key)
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    }
}

type Result<T> = std::result::Result<T, String>;

/// The input of a command: a file, the text itself (also in ``` fences),
/// or stdin (`-` or nothing).
fn read_input(args: &Args) -> Result<String> {
    if let Some(text) = args.flags.get("stdin-text") {
        return Ok(input::unfence(text));
    }
    let (_, raw) = input::source(args.positional.get(1).map(String::as_str))?;
    Ok(input::unfence(&raw))
}

/// The input as a value, read as `-i json|akd|auto`.
fn read_json(args: &Args) -> Result<Value> {
    Ok(read_parsed(args)?.value)
}

fn read_parsed(args: &Args) -> Result<input::Parsed> {
    parse_checked(&read_input(args)?, args)
}

/// `raw` read as `-i`; decode problems warned about (`--strict`: an error).
fn parse_checked(raw: &str, args: &Args) -> Result<input::Parsed> {
    let parsed = input::parse(raw, input::Kind::parse(args.get("input"))?)?;
    if let Some(first) = parsed.errors.first() {
        ui::warn(&format!("{} decode error(s): {first}", parsed.errors.len()));
        if args.has("strict") {
            return Err("invalid AK-DATA".to_string());
        }
    }
    Ok(parsed)
}

fn emit(text: &str, args: &Args) -> Result<()> {
    if let Some(target) = args.get("output") {
        std::fs::write(target, text).map_err(|e| format!("cannot write {target}: {e}"))?;
        ui::info(&format!(
            "Written to {target} (≈{} tokens)",
            akd::estimate_tokens(text)
        ));
    } else {
        let mut out = io::stdout().lock();
        let _ = out.write_all(text.as_bytes());
        if !text.ends_with('\n') {
            let _ = out.write_all(b"\n");
        }
    }
    Ok(())
}

fn parse_format(args: &Args, default: &str) -> Result<Format> {
    args.get("format")
        .unwrap_or(default)
        .parse::<Format>()
        .map_err(|e| e.to_string())
}

/// Colours on: forced with --color, or a terminal without -o.
fn colored(args: &Args) -> bool {
    (args.has("color") && args.get("color") != Some("never"))
        || (ui::enabled() && args.get("output").is_none())
}

/// Re-indents serde_json's 2-space output.
fn reindent(text: &str, indent: usize) -> String {
    text.lines()
        .map(|line| {
            let lead = line.len() - line.trim_start_matches(' ').len();
            format!("{}{}", " ".repeat(lead / 2 * indent), &line[lead..])
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn cmd_prompt(args: &Args) -> Result<()> {
    if args.has("list") {
        let all = akd::examples::all();
        let mut lines = vec![
            String::new(),
            ui::paint(
                ui::BOLD,
                &format!(
                    "{} bundled examples (ak-data prompt --example N [-f json|toon|ak-data|ak-data-compact] [--attributes] [--comments])",
                    all.len()
                ),
            ),
            ui::paint(
                ui::DIM,
                "meta: has attributes and comments to add · needs: the question needs them",
            ),
            String::new(),
        ];
        for ex in all {
            let j = akd::estimate_tokens(&ex.prompt(Format::Json, true));
            let a = akd::estimate_tokens(&ex.prompt(Format::AkDataCompact, true));
            let tag = if ex.tags.iter().any(|t| t == "needs metadata") {
                ui::paint(ui::MAGENTA, "meta+needs")
            } else if ex.has_meta() {
                ui::paint(ui::BLUE, "meta      ")
            } else {
                "          ".to_string()
            };
            lines.push(format!(
                "{} {}  {} {}",
                ui::paint(ui::YELLOW, &format!("{:>2}", ex.id)),
                ui::paint(ui::WHITE, &format!("{:<56}", ex.title)),
                tag,
                ui::paint(ui::DIM, &format!("JSON ≈{j} → AK-DATA COMPACT ≈{a}"))
            ));
        }
        return emit(&lines.join("\n"), args);
    }
    let mut question = args.get("question").unwrap_or("").to_string();
    let mut answer = args
        .get("answer")
        .and_then(|spec| Answer::parse(spec, args.get("answer-name")));
    let mut example = None;
    let data = if let Some(key) = args.get("example") {
        let ex = akd::examples::get(key)
            .ok_or_else(|| format!("No example '{key}' (see: ak-data prompt --list)"))?;
        if question.is_empty() {
            question = ex.question.clone();
        }
        if answer.is_none() {
            answer = Some(ex.answer.clone());
        }
        let data = ex.data.clone();
        example = Some(ex);
        data
    } else {
        if question.is_empty() {
            return Err("give --question (or use --example N, --list)".to_string());
        }
        read_json(args)?
    };
    let definition = !args.has("no-definition");
    let comments = args.has("comments") || args.has("meta");
    let attributes = args.has("attributes") || args.has("meta");
    if (comments || attributes) && example.is_none() {
        return Err("--attributes / --comments work with --example N (the bundled examples carry the metadata)".to_string());
    }
    if let Some(ex) = &example {
        if (comments || attributes) && !ex.has_meta() {
            ui::warn(&format!(
                "Example {} has no metadata; the prompt is the same without it.",
                ex.id
            ));
        }
    }
    let all = args.has("all-formats");
    let formats: Vec<Format> = if all {
        Format::PROMPT_FORMATS.to_vec()
    } else {
        vec![parse_format(args, "ak-data-compact")?]
    };
    let parts: Vec<String> = formats
        .iter()
        .map(|&f| {
            let text = match &example {
                Some(ex) if question == ex.question => {
                    ex.prompt_with(f, definition, comments, attributes)
                }
                _ => akd::build_prompt(&data, &question, f, answer.as_ref(), definition),
            };
            if all {
                format!(
                    "===== {} · ≈{} tokens =====\n{text}",
                    f.label(),
                    akd::estimate_tokens(&text)
                )
            } else {
                text
            }
        })
        .collect();
    let mut out = parts.join("\n");
    if let (true, Some(ex)) = (args.has("expected"), &example) {
        let mut wrapper = serde_json::Map::new();
        wrapper.insert(ex.answer.name.clone(), ex.expected.clone());
        out.push_str("\n===== expected answer =====\n");
        out.push_str(&akd::encode(&Value::Object(wrapper)));
        out.push('\n');
    }
    emit(&out, args)
}

/// `ak-data read FILE`: any input (JSON or AK-DATA) shown as AK-DATA —
/// laid out, or on one line with -c — or written as JSON / TOON with -t.
/// AK-DATA input is laid out as it is (comments, attributes and the history
/// $changes stay); JSON input, or an encoder option, encodes the data.
fn cmd_read(args: &Args) -> Result<()> {
    let raw = read_input(args)?;
    let raw = raw.as_str();
    let parsed = parse_checked(raw, args)?;
    let json_in = parsed.json;
    let value = parsed.value;
    let to = args
        .get("to")
        .or_else(|| args.get("format"))
        .unwrap_or("akd")
        .to_ascii_lowercase();
    let text = match to.as_str() {
        "json" | "json-min" | "toon" => {
            let format = match to.as_str() {
                "json" if args.number("indent", 2) == 0 || args.has("compact") => Format::JsonMin,
                "json" => Format::Json,
                "json-min" => Format::JsonMin,
                _ => Format::Toon,
            };
            let text = match format {
                Format::Json => {
                    let pretty = serde_json::to_string_pretty(&value).unwrap_or_default();
                    match args.number("indent", 2) {
                        2 => pretty,
                        n => reindent(&pretty, n),
                    }
                }
                other => akd::encode_as(&value, other),
            };
            if colored(args) && format != Format::Toon {
                ui::highlight_json(&text)
            } else {
                text
            }
        }
        "akd" | "ak-data" | "akdata" | "akd-compact" | "ak-data-compact" | "akcd" => {
            let encoder_option = [
                "no-types",
                "no-schema",
                "sizes",
                "prompt-output",
                "canonical",
            ]
            .iter()
            .any(|o| args.has(o));
            let source = if json_in || encoder_option {
                let compact = akd::encode_with(
                    &value,
                    &EncodeOptions {
                        compact: true,
                        indent: 2,
                        escape_new_lines: true,
                        include_types: !args.has("no-types"),
                        prompt_output: args.has("prompt-output"),
                        colorize: false,
                        include_schema: !args.has("no-schema"),
                        array_sizes: if args.has("sizes") {
                            Some(args.number("sizes", 1))
                        } else {
                            None
                        },
                    },
                );
                if !json_in
                    && akd::layout::strip_meta(raw, false, false) != akd::layout::compact(raw)
                {
                    ui::warn("Encoded again from the data: comments, attributes and the history ($changes) are left out.");
                }
                compact
            } else {
                raw.to_string()
            };
            let keep_comments = !args.has("no-comments");
            let keep_attributes = !args.has("no-attributes");
            let stripped = if keep_comments && keep_attributes {
                akd::layout::compact(&source)
            } else {
                akd::layout::strip_meta(&source, keep_comments, keep_attributes)
            };
            let one_line = args.has("compact") || to.contains("compact") || to == "akcd";
            let out = if one_line {
                stripped
            } else {
                akd::layout::pretty(&stripped, args.number("width", 80))
            };
            if colored(args) {
                akd::layout::highlight(&out)
            } else {
                out
            }
        }
        other => {
            return Err(format!(
                "unknown format '{other}': -t akd (default), akd-compact, json, json-min or toon"
            ))
        }
    };
    emit(&text, args)
}

fn main() -> ExitCode {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let args = Args::parse(&argv);
    ui::init(
        args.has("no-color") || args.get("color") == Some("never"),
        args.has("color") && args.get("color") != Some("never"),
    );
    if args.has("version") {
        println!(
            "{} {} {}",
            ui::paint(&format!("{}{}", ui::BOLD, ui::WHITE), "ak-data"),
            ui::paint(ui::YELLOW, &format!("v{}", akd::VERSION)),
            ui::paint(ui::DIM, "(arkadia-data, AK-DATA — Arkadia Data Format)")
        );
        return ExitCode::SUCCESS;
    }
    let mut args = args;
    // `echo '…' | ak-data`: no command, data on stdin → read it.
    if args.positional.is_empty() && !args.has("help") && !std::io::stdin().is_terminal() {
        let mut text = String::new();
        let _ = io::stdin().read_to_string(&mut text);
        if !text.trim().is_empty() {
            args.flags.insert("stdin-text".to_string(), text);
            return finish(cmd_read(&args));
        }
    }
    let cmd = args.positional.first().map(String::as_str);
    if args.has("help") || matches!(cmd, None | Some("help")) {
        // `ak-data help diff` and `ak-data diff --help` show the command's help.
        let topic = match cmd {
            Some("help") => args.positional.get(1).map(String::as_str),
            other => other,
        };
        print!("{}", help::screen(topic));
        return ExitCode::SUCCESS;
    }
    // `ak-data data.json` / `ak-data '{"a":1}'` = `ak-data read …`.
    if let Some(first) = cmd {
        if !COMMANDS.contains(&first) && input::source(Some(first)).is_ok() {
            let mut positional = vec!["read".to_string()];
            positional.extend(args.positional.iter().cloned());
            let shifted = Args {
                positional,
                flags: args.flags.clone(),
            };
            return finish(cmd_read(&shifted));
        }
    }
    let run: fn(&Args) -> Result<()> = match cmd {
        Some("read" | "r" | "cat") => cmd_read,
        Some("prompt") => cmd_prompt,
        Some("example" | "examples" | "ex") => cmd_example::run,
        Some("info" | "spec") => info::run,
        Some("diff") => cmd_diff::run_diff,
        Some("merge") => cmd_diff::run_merge,
        Some("apply") => cmd_diff::run_apply,
        Some("history" | "log") => cmd_diff::run_history,
        Some(other) => {
            ui::error(&format!(
                "unknown command '{other}'. Commands: read, diff, merge, apply, history, prompt, example, info (ak-data --help)."
            ));
            return ExitCode::from(2);
        }
        None => unreachable!(),
    };
    finish(run(&args))
}

const COMMANDS: &[&str] = &[
    "read", "r", "cat", "diff", "merge", "apply", "history", "log", "prompt", "example",
    "examples", "ex", "info", "spec", "help",
];

fn finish(result: Result<()>) -> ExitCode {
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            ui::error(&e);
            ExitCode::FAILURE
        }
    }
}
