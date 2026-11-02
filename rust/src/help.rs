//! Help screens of `ak-data` (main and per command), in the style of the
//! earlier Python tool: logo, banner, USAGE, coloured option sections.

use crate::ui::{self, opt, opt_default, Opt};
use arkadia_data as akd;

const TOOL: &str = "ak-data";

const GLOBAL: &[Opt] = &[
    opt(
        "-h, --help",
        "Show this help (ak-data <command> --help: its options)",
    ),
    opt("-v, --version", "Show version info"),
];

fn meta() -> Vec<(&'static str, String)> {
    vec![
        ("Version", akd::VERSION.to_string()),
        ("Engine", "Rust · arkadia-data".to_string()),
        (
            "Formats",
            "JSON · TOON · AK-DATA · AK-DATA COMPACT".to_string(),
        ),
        ("Input", "file path, or - / nothing for stdin".to_string()),
    ]
}

/// The help screen for `topic` (None: the main screen).
pub fn screen(topic: Option<&str>) -> String {
    let mut out = String::new();
    ui::set_column(26);
    match topic {
        Some("read" | "r" | "cat") => read(&mut out),
        Some("prompt") => prompt(&mut out),
        Some("example" | "examples" | "ex") => example(&mut out),
        Some("info" | "spec") => info(&mut out),
        Some("diff") => diff(&mut out),
        Some("merge") => merge(&mut out),
        Some("apply") => apply(&mut out),
        Some("history" | "log") => history(&mut out),
        _ => main(&mut out),
    }
    out
}

fn main(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool",
        ui::RED,
        "Reads JSON and AK-DATA and shows them as readable, coloured AK-DATA (or converts them), compares documents, keeps their change history, and builds copy-paste prompts for chat models.",
        &meta(),
    );
    ui::usage(out, TOOL, "[command]", "[file | text | -] [flags]");
    ui::note(
        out,
        "Without a command ak-data reads: a file, the text itself ('{…}', '<a:number>(1)') or stdin, shown as AK-DATA.",
    );
    ui::options(
        out,
        "Commands",
        &[
            opt(
                "read",
                "[READ] The default: show as AK-DATA, or convert with -t",
            ),
            opt(
                "diff",
                "[DIFF] The changes between two documents as a patch (--info: for people)",
            ),
            opt(
                "merge",
                "[MERGE] Join a newer document, record the change in $changes",
            ),
            opt("apply", "[APPLY] Apply a patch or a change from a history"),
            opt(
                "history",
                "[HISTORY] Who changed what and when (like git log)",
            ),
            opt(
                "prompt",
                "[PROMPT] Copy-paste prompt for ChatGPT / Gemini / Claude",
            ),
            opt(
                "example",
                "[EXAMPLE] The bundled examples (--prompt: with an AI prompt)",
            ),
            opt("info", "[INFO] The complete format definition, coloured"),
        ],
    );
    read_options(out);
    ui::options(out, "Global Options", GLOBAL);
    live(
        out,
        &[
            r#"echo '{"users":[{"id":1,"name":"Ada"},{"id":2,"name":"Alan"}]}' | ak-data -c"#,
            r#"echo '<a:number,tags:[string]>(1,["x"])' | ak-data -t json-min"#,
            r#"echo '{"a":1,"b":2} {"a":1,"b":3}' | ak-data diff -c"#,
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data data.json", "# readable, coloured AK-DATA"),
            ("ak-data data.json -c -o data.akd", "# one line, to a file"),
            ("ak-data data.akd -t json", "# back to JSON"),
            ("ak-data '<a:number>(1)'", "# text (quote it in the shell)"),
            ("ak-data diff old.json new.json", "# the changes as a patch"),
            (
                "ak-data diff old.json new.json --info",
                "# … with context, for people",
            ),
            ("ak-data diff old.json new.json -o fix.akd", "# … saved"),
            ("ak-data apply data.akd fix.akd", "# … and applied"),
            ("ak-data history data.akd", "# the change history"),
            ("ak-data example", "# a random bundled example"),
            ("ak-data example --list", "# all 66 examples"),
            (
                "ak-data example 3 --prompt",
                "# example 3 with a prompt for AI",
            ),
            (
                "ak-data example --list --features",
                "# one example per feature",
            ),
            ("ak-data info header", "# one section of the definition"),
        ],
    );
    ui::note(
        out,
        "In the shell, put text in single quotes: ak-data '<a:number>(1)'.",
    );
    ui::note(
        out,
        "Libraries: cargo add arkadia-data · pip install arkadia-data · npm install @arkadia/data",
    );
}

fn read(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Read",
        ui::GREEN,
        "The default command (ak-data FILE = ak-data read FILE). Reads JSON or AK-DATA — a file, the text itself or stdin — and shows it as AK-DATA: laid out and coloured, or on one line with -c. -t converts to JSON or TOON, -o writes a file. AK-DATA input is laid out as it is, so comments, attributes and the history ($changes) stay; JSON input, or an encoder option, encodes the data.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data [read]", "", "[file | text | -] [flags]");
    live(
        out,
        &[
            r#"echo '{"users":[{"id":1,"name":"Ada"},{"id":2,"name":"Alan"}]}' | ak-data read -c"#,
            r#"ak-data '{"id":7,"tags":["new","sale"]}'"#,
            r#"echo '<a:number,b:[string]>(1,["x","y"])' | ak-data -t json-min"#,
            r#"echo '{"users":[{"id":1,"name":"Ada"}]}' | ak-data -t toon"#,
        ],
    );
    read_options(out);
    ui::examples(
        out,
        &[
            ("ak-data data.json", "# readable AK-DATA"),
            ("ak-data data.json -c -o data.akd", "# one line, to a file"),
            ("ak-data data.akd -t json -o data.json", "# back to JSON"),
            ("ak-data '<a:number>(1)' -t json", "# text"),
            ("curl -s api/x | ak-data -c", "# from a pipe"),
        ],
    );
}

fn prompt(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Prompt",
        ui::GREEN,
        "Builds a copy-paste prompt for ChatGPT / Gemini / Claude: the format definition, your data and the question.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data prompt", "", "[flags] [file | text | -]");
    live(
        out,
        &[
            r#"echo '{"items":[{"name":"pen","qty":2},{"name":"ink","qty":5}]}' | ak-data prompt -q "Total qty?" --no-definition"#,
        ],
    );
    ui::options(
        out,
        "Question & Answer",
        &[
            opt("-q, --question <text>", "The question about the data"),
            opt(
                "-a, --answer <fields>",
                "Answer shape, e.g. \"name:string,total:number\"",
            ),
            opt_default("--answer-name <name>", "Name of the answer list", "result"),
        ],
    );
    ui::options(
        out,
        "Format",
        &[
            opt_default(
                "-f, --format <f>",
                "json, toon, ak-data, ak-data-compact",
                "ak-data-compact",
            ),
            opt(
                "--all-formats",
                "The prompt in every format, with token estimates",
            ),
            opt("--no-definition", "Leave out the format definition"),
            opt("-o, --output <file>", "Write the prompt to a file"),
        ],
    );
    ui::options(
        out,
        "Bundled Examples",
        &[
            opt(
                "-e, --example <n>",
                "One of the 66 bundled examples (51 real-size + 15 features)",
            ),
            opt("--list", "List the bundled examples"),
            opt("--expected", "With --example: append the expected answer"),
            opt(
                "--attributes",
                "With --example: add $attributes and #tags (JSON/TOON: as notes)",
            ),
            opt(
                "--comments",
                "With --example: add /* comments */ (JSON/TOON: as notes)",
            ),
            opt("--meta", "Both: --attributes --comments"),
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data prompt data.json -q \"Who spent most?\"", ""),
            ("ak-data prompt --example 3 --format toon", ""),
            ("ak-data prompt --example 11 --attributes --comments", ""),
        ],
    );
}

fn example(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Example",
        ui::GREEN,
        "A random AK-DATA example, laid out and coloured: what it shows, the readable and compact forms, token counts and a round-trip check. With --prompt also a ready prompt for ChatGPT / Gemini / Claude and the expected answer. The same 66 examples as the website: 51 real-size ones and 15 feature examples (one part of the format each).",
        &meta()[..1],
    );
    ui::usage(out, "ak-data example", "", "[id|slug] [flags]");
    live(
        out,
        &[
            "ak-data example --list --features | head -6",
            "ak-data example 63 --raw",
        ],
    );
    ui::options(
        out,
        "Arguments",
        &[opt(
            "id|slug",
            "Pick one example (1-66 or e.g. named-types); nothing: random",
        )],
    );
    ui::options(
        out,
        "Options",
        &[
            opt(
                "-p, --prompt",
                "Add a copy-paste prompt for AI and the expected answer",
            ),
            opt_default(
                "-f, --format <f>",
                "Data format in the prompt: ak-data, ak-data-compact, json, toon",
                "ak-data",
            ),
            opt("--json", "Also show the same data as JSON"),
            opt(
                "--raw",
                "Only the AK-DATA (or, with --prompt, only the prompt) — for pipes",
            ),
            opt("--no-definition", "Prompt without the format definition"),
            opt_default("--width <n>", "Line width of the readable form", "72"),
            opt("--seed <n>", "Repeat a random pick"),
            opt(
                "--list",
                "List all examples (--features: only the feature examples)",
            ),
            opt("-o, --output <file>", "Write to a file"),
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data example", "# a random example"),
            ("ak-data example 2 --prompt", "# example 2 with a prompt"),
            (
                "ak-data example --prompt --raw | pbcopy",
                "# random prompt to the clipboard",
            ),
            ("ak-data example metadata --json", ""),
            (
                "ak-data example --list --features",
                "# one example per part of the format",
            ),
        ],
    );
}

fn info(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Info",
        ui::BLUE,
        "The complete AK-DATA definition: document structure, values, headers and types, records, lists, overrides, named types, metadata, encoder rules, JSON mapping, grammar and how to write AK-DATA. Every example is decoded live.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data info", "", "[section] [flags]");
    live(out, &["ak-data info --list | head -8"]);
    ui::options(
        out,
        "Arguments",
        &[opt(
            "section",
            "overview, document, values, header, records, lists, overrides, named, metadata, encoder, json, grammar, writing, tools (or its number)",
        )],
    );
    ui::options(
        out,
        "Options",
        &[
            opt("--list", "Only the table of contents"),
            opt("-o, --output <file>", "Write to a file (no colours)"),
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data info", "# everything"),
            ("ak-data info grammar", "# one section"),
            (
                "ak-data info --color | less -R",
                "# page through, with colours",
            ),
        ],
    );
}

fn diff(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Diff",
        ui::YELLOW,
        "Writes what changed in NEW relative to OLD as a patch: one change set (id, date, author, title, description) with its changes (op, path, old, new) — coloured AK-DATA in a terminal. -o saves it for ak-data apply. --info shows the changes for people instead: the changed paths (users[id=2].name), the changes in place with the lines around them like git diff, and the history entries only one of the two has.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data diff", "", "[flags] OLD NEW");
    ui::note(
        out,
        "OLD and NEW: files, text ('{…}', '<a:number>(1)'), or both on stdin, one after the other.",
    );
    live(
        out,
        &[
            r#"echo '{"a":1,"b":2} {"a":1,"b":3}' | ak-data diff -m "Bump b""#,
            r#"echo '{"a":1,"b":2} {"a":1,"b":3}' | ak-data diff --info"#,
            r#"ak-data diff '{"tags":["x"],"v":1}' '{"tags":["x","y"]}' --paths"#,
            r#"ak-data diff '{"n":1}' '{"n":2}' -t json -c"#,
        ],
    );
    ui::options(
        out,
        "Patch",
        &[
            opt_default("-t, --to <type>", "akd or json", "akd"),
            opt("-c, --compact", "One line"),
            opt("-o, --output <file>", "Save the patch for ak-data apply"),
            opt("-m, --title <text>", "Title of the change"),
            opt(
                "--author <name>",
                "Author (default: $AK_DATA_AUTHOR, git user, $USER)",
            ),
            opt("--description <text>", "Longer description"),
            opt("--date <iso>", "Date (default: now, UTC)"),
            opt("-i, --input <type>", "Read OLD and NEW as json or akd"),
            opt("--exit-code", "Exit with 1 when the data differs"),
        ],
    );
    ui::options(
        out,
        "Info (for people)",
        &[
            opt(
                "--info",
                "Paths, the changes in place with context, history entries",
            ),
            opt_default("-U, --context <n>", "Lines around each change", "3"),
            opt("--full", "The whole document, changes marked"),
            opt("--paths", "Only the list of changes, all of them"),
            opt(
                "--akd",
                "Changes in place as AK-DATA (default: one JSON value per line)",
            ),
            opt_default("--limit <n>", "Changes in the list", "12"),
            opt("--all", "Every change in the list"),
            opt("--plain", "Without colours"),
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data diff old.json new.json", "# the patch, coloured"),
            (
                "ak-data diff old.json new.json --info",
                "# what changed, with context",
            ),
            (
                "ak-data diff v1.json v2.json -m \"Prices 2027\" -o fix.akd",
                "# save the patch",
            ),
            (
                "ak-data apply data.akd fix.akd",
                "# apply it to another copy",
            ),
        ],
    );
    ui::note(
        out,
        "Lists of records are matched by id / key / name / slug / sku / code / uuid (or the first field) when it is unique, otherwise by position. Changes: add, remove, change, order. The info options (--paths, -U, --full …) imply --info.",
    );
}

fn merge(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Merge",
        ui::GREEN,
        "Joins NEW into OLD and records what changed in the history: the attribute $changes after the data. The structure of the data stays as it is — decoding the document gives exactly the data. Records are merged field by field (NEW wins, fields only in OLD stay), lists of records by key (new records appended), other values replaced. --latest does not join: NEW is taken as it is and only the change is recorded.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data merge", "", "[flags] OLD NEW");
    live(
        out,
        &[
            r#"ak-data merge '{"a":1,"cfg":{"x":1}}' '{"cfg":{"y":2}}' -c --no-history --quiet"#,
            r#"ak-data merge '{"a":1,"cfg":{"x":1}}' '{"cfg":{"y":2}}' -c --no-history --quiet --latest"#,
            r#"ak-data merge '{"n":1}' '{"n":2}' -m Bump -c --quiet"#,
        ],
    );
    ui::options(
        out,
        "Options",
        &[
            opt("--latest", "Keep NEW as it is, only record the change"),
            opt(
                "-m, --title <text>",
                "Title of the change (default: Merge NEW)",
            ),
            opt(
                "--author <name>",
                "Author (default: $AK_DATA_AUTHOR, git user, $USER)",
            ),
            opt("--description <text>", "Longer description"),
            opt("--date <iso>", "Date (default: now, UTC)"),
            opt("--no-history", "Only the data, no $changes"),
            opt_default("-t, --to <type>", "akd or json (the data only)", "akd"),
            opt("-c, --compact", "One line"),
            opt("--quiet", "No summary on stderr"),
            opt("-o, --output <file>", "Write to a file (may be OLD itself)"),
        ],
    );
    ui::examples(
        out,
        &[
            (
                "ak-data merge data.akd update.json -m \"Prices 2027\" -o data.akd",
                "# record a change",
            ),
            (
                "ak-data merge data.akd export.json --latest -o data.akd",
                "# newest as it is",
            ),
            ("ak-data history data.akd", "# what was changed"),
        ],
    );
}

fn apply(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · Apply",
        ui::CYAN,
        "Applies a change to DATA: a patch saved by ak-data diff -o, or a document with a history — then the entries DATA does not have yet (like a pull), or the ones chosen with --change. A file is updated in place; text or stdin is printed. Each change must fit — the old value must be the one in DATA — otherwise nothing is written. The applied change sets are added to the history unless --no-history.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data apply", "", "[flags] DATA PATCH");
    live(
        out,
        &[
            r#"ak-data apply '{"n":1}' '{"changes":[{"op":"change","path":"n","old":1,"new":2}]}' -c --no-history --quiet"#,
            r#"ak-data apply '{"n":5}' '{"changes":[{"op":"change","path":"n","old":1,"new":2}]}' --quiet"#,
        ],
    );
    ui::options(
        out,
        "Options",
        &[
            opt(
                "--change <id,…>",
                "Only these change sets of PATCH's history (id prefix)",
            ),
            opt(
                "-R, --reverse",
                "Undo the change (recorded as \"Revert …\")",
            ),
            opt("--no-history", "Change the data only, do not record it"),
            opt(
                "--force",
                "Apply what fits, write over different old values",
            ),
            opt("--dry-run", "Show what would change, write nothing"),
            opt("-m, --title <text>", "Title of the change"),
            opt("--author / --description", "Set them on the change"),
            opt("-o, --output <file>", "Write elsewhere instead of DATA"),
            opt("--stdout", "Print the result instead of writing"),
            opt("-c, --compact", "One line"),
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data diff v1.json v2.json -o fix.akd", "# a patch …"),
            ("ak-data apply data.akd fix.akd", "# … applied and recorded"),
            ("ak-data apply data.akd fix.akd --no-history", "# data only"),
            (
                "ak-data apply copy.akd data.akd",
                "# bring in the newer history",
            ),
            (
                "ak-data apply data.akd data.akd --change 3f2a1c -R",
                "# undo one change",
            ),
        ],
    );
    ui::note(
        out,
        "A JSON DATA file stays JSON (the history needs AK-DATA: -o data.akd).",
    );
}

fn history(out: &mut String) {
    ui::banner(
        out,
        "Arkadia Data Tool · History",
        ui::MAGENTA,
        "The change history of an AK-DATA document ($changes), newest first, like git log: id, author, date, title, description and the changes.",
        &meta()[..1],
    );
    ui::usage(out, "ak-data history", "", "[flags] [file | text | -]");
    live(
        out,
        &[
            r#"ak-data merge '{"n":1}' '{"n":2,"tag":"x"}' -m "Bump n" --quiet | ak-data history --oneline"#,
            r#"ak-data merge '{"n":1}' '{"n":2}' -m "Bump n" --quiet | ak-data history"#,
        ],
    );
    ui::options(
        out,
        "Options",
        &[
            opt("--oneline", "One line per change set"),
            opt(
                "-p, --patch",
                "Every change with its whole old and new value",
            ),
            opt(
                "--path <path>",
                "Only changes at or under a path (users, users[id=2])",
            ),
            opt("--author <text>", "Only change sets by this author"),
            opt(
                "--change <id>",
                "One change set (id prefix), with its changes",
            ),
            opt("-n, --max <n>", "At most n change sets"),
            opt("-R, --reverse", "Oldest first"),
            opt("-t json", "The history as JSON"),
        ],
    );
    ui::examples(
        out,
        &[
            ("ak-data history data.akd", ""),
            ("ak-data history data.akd --oneline -n 10", ""),
            ("ak-data history data.akd --path users -p", ""),
        ],
    );
}

/// `QUICK EXAMPLES:` — small commands with text input and their real output
/// (run with this binary when the help is shown, so they are always right).
fn live(out: &mut String, commands: &[&str]) {
    out.push_str(&format!("{}\n", ui::paint(ui::YELLOW, "QUICK EXAMPLES:")));
    for cmd in commands {
        out.push_str(&format!(
            "   {} {}\n",
            ui::paint(ui::DIM, "$"),
            ui::paint(ui::BOLD, cmd)
        ));
        if let Some(result) = run(cmd) {
            for line in result.trim_end().lines() {
                if line.trim().is_empty() {
                    out.push('\n');
                } else {
                    out.push_str(&format!("   {}\n", ui::paint(ui::CYAN, line)));
                }
            }
        }
        out.push('\n');
    }
}

/// Output of a shell command line with `ak-data` being this binary
/// (author and date fixed, no colours). `None` when it cannot run.
fn run(cmd: &str) -> Option<String> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.to_str()?.replace('\'', "'\\''");
    let line = cmd.replace("ak-data", &format!("'{exe}'"));
    let output = std::process::Command::new("sh")
        .arg("-c")
        .arg(format!("{line} 2>&1"))
        .env("NO_COLOR", "1")
        .env("COLUMNS", "80")
        .env("AK_DATA_AUTHOR", "Ada")
        .env("AK_DATA_DATE", "2026-11-01T09:00:00Z")
        .stdin(std::process::Stdio::null())
        .output()
        .ok()?;
    Some(String::from_utf8_lossy(&output.stdout).to_string())
}

/// The options of reading (the default command): input / output, AK-DATA,
/// colours — on the main help and on `ak-data read --help`.
fn read_options(out: &mut String) {
    ui::options(
        out,
        "Input / Output",
        &[
            opt_default("-i, --input <type>", "json or akd", "auto"),
            opt_default(
                "-t, --to <type>",
                "akd, akd-compact, json, json-min, toon",
                "akd",
            ),
            opt("-o, --output <file>", "Write to a file"),
            opt("-c, --compact", "One line (AK-DATA or JSON)"),
            opt_default("--width <n>", "Line width of the laid-out AK-DATA", "80"),
            opt_default("--indent <n>", "JSON indentation", "2"),
        ],
    );
    ui::options(
        out,
        "AK-DATA",
        &[
            opt("--no-comments", "Drop /* comments */"),
            opt(
                "--no-attributes",
                "Drop $attributes, #tags, // … // blocks and the history",
            ),
            opt(
                "--sizes[=n]",
                "$size=N on lists (of n+ items): models need not count",
            ),
            opt("--no-types", "Header without primitive types"),
            opt("--no-schema", "Leave out the header"),
            opt("--prompt-output", "Structural template for model output"),
            opt(
                "--canonical",
                "Encode AK-DATA input again (what encoders write)",
            ),
            opt("--strict", "Fail on any decode error"),
        ],
    );
    ui::options(
        out,
        "Color Control",
        &[
            opt("--color", "Force colours (e.g. | less -R)"),
            opt("--no-color", "Plain text (also NO_COLOR=1)"),
        ],
    );
}
