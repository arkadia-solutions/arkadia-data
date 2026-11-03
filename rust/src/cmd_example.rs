//! `ak-data example` — a random (or chosen) AK-DATA snippet, laid out and
//! coloured, optionally with a ready prompt for a chat model.

use akd::gallery::{self, Snippet};
use akd::{layout, Format};
use arkadia_data as akd;

use crate::ui;
use crate::Args;

const RULE: usize = 64;

fn seed_from_clock() -> u64 {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(7);
    (nanos ^ u64::from(std::process::id()).rotate_left(17)) % 100_000
}

/// Coloured AK-DATA when colours are on.
fn code(text: &str) -> String {
    if ui::enabled() {
        layout::highlight(text)
    } else {
        text.to_string()
    }
}

/// A section title on its own line (nothing to the left of the content, so
/// the code and the prompt can be selected straight from the terminal).
fn heading(out: &mut String, title: &str, right: &str) {
    let pad = RULE.saturating_sub(title.chars().count() + right.chars().count() + 4);
    out.push_str(&format!(
        "\n{} {} {}{}\n\n",
        ui::paint(ui::GREEN, "──"),
        ui::paint(ui::BOLD, title),
        ui::paint(ui::DIM, &"─".repeat(pad)),
        ui::paint(ui::DIM, &format!(" {right}"))
    ));
}

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

/// The prompt, flush left (the data block coloured), between two rules.
fn prompt_block(prompt: &str) -> String {
    let rule = ui::paint(ui::DIM, &"┄".repeat(RULE + 2));
    let mut out = format!("{rule}\n");
    let mut in_data = false;
    for line in prompt.trim_end().lines() {
        let shown = if line == "<data>" {
            in_data = true;
            ui::paint(ui::DIM, line)
        } else if line == "</data>" {
            in_data = false;
            ui::paint(ui::DIM, line)
        } else if in_data {
            code(line)
        } else if let Some(q) = line.strip_prefix("Question: ") {
            format!(
                "{} {}",
                ui::paint(ui::BOLD, "Question:"),
                ui::paint(ui::WHITE, q)
            )
        } else if line.starts_with('<') {
            code(line)
        } else {
            ui::paint(ui::WHITE, line)
        };
        out.push_str(&shown);
        out.push('\n');
    }
    out.push_str(&format!("{rule}\n"));
    out
}

fn list(features_only: bool) -> String {
    let mut out = format!(
        "\n{}\n",
        ui::paint(
            ui::BOLD,
            "AK-DATA EXAMPLES  (ak-data example <id|slug> [--prompt] · the same as on the website)"
        )
    );
    let all = gallery::all();
    let groups: [(&str, bool); 2] = [
        ("FEATURES · one part of the format each", true),
        (
            "REAL-SIZE EXAMPLES · data, a question and the expected answer",
            false,
        ),
    ];
    for (title, feature) in groups {
        if features_only && !feature {
            continue;
        }
        out.push_str(&format!("\n{}\n", ui::paint(ui::GREEN, title)));
        for s in all.iter().filter(|s| s.is_feature() == feature) {
            let json = akd::estimate_tokens(&s.text(Format::Json, 80));
            let akcd = akd::estimate_tokens(&s.text(Format::AkDataCompact, 80));
            let tags: Vec<&str> = s
                .tags
                .iter()
                .filter(|t| *t != "feature")
                .map(|t| {
                    if t == "metadata" {
                        "meta"
                    } else {
                        "needs meta"
                    }
                })
                .collect();
            out.push_str(&format!(
                "{} {} {}  {} {}\n",
                ui::paint(ui::YELLOW, &format!("{:>2}", s.id)),
                ui::paint(ui::CYAN, &format!("{:<22}", s.slug)),
                ui::paint(ui::WHITE, &format!("{:<52}", s.title)),
                ui::paint(ui::DIM, &format!("JSON ≈{json} → ≈{akcd}")),
                ui::paint(ui::MAGENTA, &tags.join(" "))
            ));
        }
    }
    out.push_str(&format!(
        "\n{}\n",
        ui::paint(
            ui::DIM,
            "--features: only the feature examples · prompts in every format: ak-data prompt --example <id> --all-formats · the format itself: ak-data info"
        )
    ));
    out
}

fn show(s: &Snippet, args: &Args, seed: Option<u64>, width: usize) -> crate::Result<String> {
    let total = gallery::all().len();
    let want_prompt = args.has("prompt");
    let format = match args.get("format") {
        Some(f) => f.parse::<Format>().map_err(|e| e.to_string())?,
        None => Format::AkData,
    };
    let definition = !args.has("no-definition");

    // Plain output for pipes and the clipboard.
    if args.has("raw") {
        return Ok(if want_prompt {
            s.prompt(format, width, definition)
        } else {
            s.text(format, width) + "\n"
        });
    }

    let readable = s.text(Format::AkData, width);
    let compact = s.text(Format::AkDataCompact, width);
    let json = s.text(Format::Json, width);
    let (t_read, t_comp, t_json) = (
        akd::estimate_tokens(&readable),
        akd::estimate_tokens(&compact),
        akd::estimate_tokens(&json),
    );

    let mut out = String::new();
    let tag = format!("EXAMPLE {} / {total} · {}", s.id, s.slug);
    let right = seed.map(|n| format!("seed {n}")).unwrap_or_default();
    let pad = RULE.saturating_sub(tag.chars().count() + right.chars().count());
    out.push_str(&format!(
        "\n{}{}{}\n",
        ui::paint(&format!("{}{}", ui::BOLD, ui::GREEN), &tag),
        " ".repeat(pad + 2),
        ui::paint(ui::DIM, &right)
    ));
    out.push_str(&format!(
        "{}\n",
        ui::paint(&format!("{}{}", ui::BOLD, ui::WHITE), &s.title)
    ));
    for line in wrap(&s.shows, RULE + 2) {
        out.push_str(&format!("{}\n", ui::paint(ui::DIM, &line)));
    }

    heading(&mut out, "AK-DATA · readable", &format!("≈{t_read} tokens"));
    out.push_str(&code(&readable));
    out.push('\n');

    heading(
        &mut out,
        "AK-DATA COMPACT · one line, for prompts",
        &format!("≈{t_comp} tokens"),
    );
    out.push_str(&code(&compact));
    out.push('\n');

    if args.has("json") {
        heading(
            &mut out,
            "JSON · the same data",
            &format!("≈{t_json} tokens"),
        );
        out.push_str(&ui::paint(ui::DIM, &json));
        out.push('\n');
    }

    let lossless = akd::decode(&readable).ok().as_ref() == Some(&s.data)
        && akd::decode(&compact).ok().as_ref() == Some(&s.data);
    let saved = (t_json as f64 - t_comp as f64) / t_json.max(1) as f64 * 100.0;
    out.push('\n');
    out.push_str(&format!(
        "{}   {}\n",
        if lossless {
            ui::paint(ui::GREEN, "✓ lossless: both forms decode to the same JSON")
        } else {
            ui::paint(ui::RED, "✗ round-trip differs")
        },
        ui::paint(
            if saved > 0.0 { ui::GREEN } else { ui::YELLOW },
            &format!("{:+.1}% tokens vs JSON (≈{t_json})", -saved)
        )
    ));

    if want_prompt {
        let prompt = s.prompt(format, width, definition);
        heading(
            &mut out,
            &format!("PROMPT FOR AI · {}", format.label()),
            &format!("≈{} tokens", akd::estimate_tokens(&prompt)),
        );
        out.push_str(&prompt_block(&prompt));
        heading(&mut out, "EXPECTED ANSWER", "computed from the data");
        out.push_str(&code(&layout::pretty(&s.expected_akd(), width)));
        out.push('\n');
    }

    let id = s.id;
    let mut next = vec![];
    if !want_prompt {
        next.push(format!("ak-data example {id} --prompt"));
    } else {
        next.push(format!("ak-data example {id} --prompt --raw | pbcopy"));
    }
    if !args.has("json") {
        next.push(format!("ak-data example {id} --json"));
    }
    next.push("ak-data example --list".to_string());
    next.push("ak-data info".to_string());
    out.push_str(&format!(
        "\n{} {}\n",
        ui::paint(ui::DIM, "next:"),
        next.iter()
            .map(|n| ui::paint(ui::CYAN, n))
            .collect::<Vec<_>>()
            .join(&ui::paint(ui::DIM, " · "))
    ));
    Ok(out)
}

pub fn run(args: &Args) -> crate::Result<()> {
    if args.has("list") {
        return crate::emit(&list(args.has("features")), args);
    }
    let width = args.number("width", 72).clamp(30, 400);
    let key = args
        .positional
        .get(1)
        .cloned()
        .or_else(|| args.get("example").map(str::to_string));
    let (snippet, seed) = match key {
        Some(k) => (
            gallery::get(&k)
                .ok_or_else(|| format!("No example '{k}' (see: ak-data example --list)"))?,
            None,
        ),
        None => {
            let seed = args
                .get("seed")
                .and_then(|v| v.parse().ok())
                .unwrap_or_else(seed_from_clock);
            (gallery::pick(seed), Some(seed))
        }
    };
    let text = show(&snippet, args, seed, width)?;
    crate::emit(&text, args)
}
