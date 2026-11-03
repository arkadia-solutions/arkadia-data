"""
Copy-paste prompts: the same data and question in JSON, TOON, AK-Data or
AK-Data compact, with the format definition, ready to paste into ChatGPT,
Gemini, Claude or any chat model.

    from arkadia.bench.prompts import build_prompt, load_examples
    text = build_prompt(data, "Which service has most errors?", "akcd",
                        answer=("result", [("service", "string"), ("errors", "number")]))

The Rust `ak-data prompt` command builds the same prompts, including the ten
bundled examples (`ak-data prompt --list`, `ak-data prompt --example 3 -f toon`).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from arkadia.data import layout
from arkadia.data.prompt import FORMAT_DEFINITION, TOON_DEFINITION

from .formats import available_formats

EXAMPLES_DIR = pathlib.Path(__file__).resolve().parent / "examples"

# Accepted spellings for the --format parameter.
FORMAT_ALIASES = {
    "json": "json",
    "json-min": "json-min",
    "toon": "toon",
    "akd": "akd",
    "ak-data": "akd",
    "akdata": "akd",
    "akcd": "akcd",
    "ak-data-compact": "akcd",
    "compact": "akcd",
}
FORMAT_NAMES = {
    "json": "JSON",
    "json-min": "JSON (minified)",
    "toon": "TOON",
    "akd": "AK-DATA",
    "akcd": "AK-DATA COMPACT",
}

Answer = Tuple[str, Sequence[Tuple[str, str]]]  # (name, [(field, type), ...])


def normalize_format(name: str) -> str:
    key = FORMAT_ALIASES.get(name.strip().lower().replace("_", "-").replace(" ", "-"))
    if not key:
        raise ValueError(
            f"Unknown format '{name}'. Use one of: json, toon, ak-data, ak-data-compact"
        )
    return key


def _answer_instruction(fmt: str, answer: Answer) -> str:
    name, fields = answer
    if fmt in ("akd", "akcd"):
        header = f"<{name}:<[" + ",".join(f"{f}:{t}" for f, t in fields) + "]>>"
        return (
            "Answer in AK-DATA only (no prose, no code fences), with exactly this "
            f"header and one record per item:\n{header}"
        )
    if fmt == "toon":
        cols = ",".join(f for f, _ in fields)
        return (
            f"Answer in TOON only (no prose, no code fences): {name}[N]{{{cols}}}: "
            "followed by one row per item."
        )
    shape = ", ".join(f'"{f}": <{t}>' for f, t in fields)
    return f'Answer with JSON only (no prose): {{"{name}": [{{{shape}}}, ...]}}'


# Width of the readable AK-DATA in prompts (same in Rust and TypeScript).
PROMPT_WIDTH = 80


def payload(data: Any, fmt: str) -> str:
    """The data in a prompt format (readable AK-DATA is laid out to 80 columns)."""
    formats = available_formats()
    if fmt not in formats:
        raise ValueError(
            f"Format '{fmt}' needs an optional library (pip install 'arkadia-data[bench]')"
        )
    if fmt == "akd":
        return layout.pretty(formats["akcd"].encode(data), PROMPT_WIDTH)
    return formats[fmt].encode(data).rstrip("\n")


def assemble(
    fmt: str,
    data_text: str,
    question: str,
    answer: Optional[Answer] = None,
    definition: bool = True,
    notes: str = "",
) -> str:
    """Intro, format definition, notes, <data>…</data>, question, answer format."""
    intro = {"akd": "AK-DATA", "akcd": "AK-DATA (compact, single-line form)"}
    parts = [f"The data below is in {intro.get(fmt, FORMAT_NAMES[fmt])}."]
    if definition and fmt in ("akd", "akcd"):
        parts.append(FORMAT_DEFINITION)
    elif definition and fmt == "toon":
        parts.append(TOON_DEFINITION)
    if notes:
        parts.append(notes)
    parts.append(f"<data>\n{data_text}\n</data>")
    parts.append(f"Question: {question}")
    if answer:
        parts.append(_answer_instruction(fmt, answer))
    return "\n\n".join(parts) + "\n"


def build_prompt(
    data: Any,
    question: str,
    fmt: str = "akcd",
    answer: Optional[Answer] = None,
    definition: bool = True,
) -> str:
    """The full prompt text: intro, format definition, data, question, answer format."""
    fmt = normalize_format(fmt)
    return assemble(fmt, payload(data, fmt), question, answer, definition)


# ---------------------------------------------------------------------------
# Bundled examples
# ---------------------------------------------------------------------------


@dataclass
class Example:
    id: int
    slug: str
    title: str
    description: str
    question: str
    answer: Answer
    expected: Any
    expected_note: str
    data: Any
    # Metadata: the compact AK-DATA with all of it, and the same facts as notes.
    akd_meta: Optional[str] = None
    notes: Optional[Dict[str, List[str]]] = None
    tags: Optional[List[str]] = None
    # Hand-written AK-DATA (feature examples: named types, metadata …).
    akd: Optional[str] = None

    def data_text(
        self, fmt: str, comments: bool = False, attributes: bool = False
    ) -> str:
        """The data in `fmt`, with the chosen metadata (inline for AK-DATA)."""
        fmt = normalize_format(fmt)
        if fmt in ("akd", "akcd") and self.akd_meta and (comments or attributes):
            from .catalog import variant_text

            text = variant_text(self.akd_meta, comments, attributes)
            return layout.pretty(text, PROMPT_WIDTH) if fmt == "akd" else text
        if fmt in ("akd", "akcd") and self.akd:
            text = layout.strip_meta(self.akd)
            return layout.pretty(text, PROMPT_WIDTH) if fmt == "akd" else text
        return payload(self.data, fmt)

    def notes_text(self, fmt: str, comments: bool, attributes: bool) -> str:
        """Notes before the data for formats without comments (JSON, TOON)."""
        from .catalog import notes_block

        if normalize_format(fmt) in ("akd", "akcd") or not self.notes:
            return ""
        return notes_block(self.notes, comments, attributes)

    def prompt(
        self,
        fmt: str = "akcd",
        definition: bool = True,
        comments: bool = False,
        attributes: bool = False,
    ) -> str:
        fmt = normalize_format(fmt)
        return assemble(
            fmt,
            self.data_text(fmt, comments, attributes),
            self.question,
            self.answer,
            definition,
            self.notes_text(fmt, comments, attributes),
        )


def load_examples(directory: pathlib.Path = EXAMPLES_DIR) -> List[Example]:
    out = []
    for path in sorted(pathlib.Path(directory).glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            Example(
                id=d["id"],
                slug=d["slug"],
                title=d["title"],
                description=d["description"],
                question=d["question"],
                answer=(d["answer"]["name"], [tuple(f) for f in d["answer"]["fields"]]),
                expected=d.get("expected"),
                expected_note=d.get("expected_note", ""),
                data=d["data"],
                akd_meta=d.get("akd_meta"),
                notes=d.get("notes"),
                tags=d.get("tags", []),
                akd=d.get("akd"),
            )
        )
    return sorted(out, key=lambda e: e.id)


def get_example(key: str) -> Example:
    for ex in load_examples():
        if str(ex.id) == str(key) or ex.slug == key:
            return ex
    raise ValueError(f"No example '{key}' (see: ak-data prompt --list)")


COMBOS = {
    "none": (False, False),
    "comments": (True, False),
    "attributes": (False, True),
    "both": (True, True),
}


def example_matrix(
    formats: Sequence[str] = ("json", "toon", "akd", "akcd"),
    encoding: str = "o200k_base",
) -> Dict[str, Any]:
    """
    Every example in every format and metadata combination, with token counts
    (for the website): {"index": …, "details": [one dict per example]}.
    """
    from arkadia.data.tokens import get_tokenizer

    tok = get_tokenizer(encoding)
    all_formats = available_formats()
    index: Dict[str, Any] = {
        "tokenizer": tok.label,
        "formats": {k: FORMAT_NAMES[k] for k in formats},
        "combos": list(COMBOS),
        "definition_tokens": {
            "akd": tok.count(FORMAT_DEFINITION),
            "akcd": tok.count(FORMAT_DEFINITION),
            "toon": tok.count(TOON_DEFINITION),
            "json": 0,
        },
        "examples": [],
    }
    details = []
    for ex in load_examples():
        combos = list(COMBOS) if ex.akd_meta else ["none"]
        prompts = {
            f: {c: ex.prompt(f, True, *COMBOS[c]) for c in combos} for f in formats
        }
        tokens = {
            f: {c: tok.count(t) for c, t in v.items()} for f, v in prompts.items()
        }
        expected = {ex.answer[0]: ex.expected}
        answers = {
            "json": json.dumps(expected, ensure_ascii=False, indent=2),
            "akcd": all_formats["akcd"].encode(expected),
        }
        if "toon" in all_formats:
            answers["toon"] = all_formats["toon"].encode(expected)
        head = {
            "id": ex.id,
            "slug": ex.slug,
            "title": ex.title,
            "description": ex.description,
            "tags": ex.tags or [],
            "question": ex.question,
            "tokens": tokens,
        }
        index["examples"].append(head)
        details.append(
            {
                **head,
                "answer": {
                    "name": ex.answer[0],
                    "fields": [list(f) for f in ex.answer[1]],
                },
                "expected": ex.expected,
                "expected_note": ex.expected_note,
                "notes": ex.notes or {"comments": [], "attributes": []},
                "prompts": prompts,
                "data_tokens": {
                    f: {c: tok.count(ex.data_text(f, *COMBOS[c])) for c in combos}
                    for f in formats
                },
                "expected_answers": answers,
                "answer_tokens": {k: tok.count(v) for k, v in answers.items()},
            }
        )
    return {"index": index, "details": details}
