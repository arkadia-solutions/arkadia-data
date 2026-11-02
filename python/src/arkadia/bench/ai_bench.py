"""
AI comprehension benchmark: does a model read the data as well in AK-Data
as in JSON, YAML or TOON, and how many tokens does that cost?

For every dataset the benchmark generates questions whose answers are
computed from the data itself (lookups, counts, extremes, nested paths,
list lengths, field names), sends the same questions with the data in each
format to a model, and scores the answers exactly. An optional "write" task
asks the model to produce data in each format and checks that it decodes
back to the original.

Works with any OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama,
LM Studio, vLLM, Groq, ...) and with the Anthropic Messages API, using only
the standard library.

    from arkadia.bench.ai_bench import run, provider_from_env
    report = run(provider_from_env(model="gpt-4o-mini"))
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from arkadia.data.prompt import HINT
from arkadia.data.tokens import get_tokenizer

from .datasets import Dataset, resolve
from .formats import Format, available_formats
from .generate import generate

TOON_HINT = (
    "Data is in TOON format: indentation shows nesting; key[N]{f1,f2}: is "
    "followed by N rows of comma-separated values in field order; key[N]: a,b "
    "is a list."
)
HINTS = {
    "akd": HINT,
    "akcd": HINT,
    "akd-n": HINT,
    "akcd-n": HINT,
    "toon": TOON_HINT,
}
AK_KEYS = ("akd", "akcd", "akd-n", "akcd-n")
DEFAULT_FORMATS = ("json", "yaml", "toon", "akcd", "akcd-n", "akd-n")

SYSTEM = (
    "You answer questions about the data you are given. Reply with exactly one "
    "line per question, in the form '<number>. <answer>', and nothing else. "
    "Give values exactly as they appear in the data; give counts as numbers; "
    "give lists as comma-separated values."
)


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


@dataclass
class Question:
    kind: str  # lookup | nested | count | extreme | length | fields | value
    text: str
    answer: Any
    dataset: str = ""


def _scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _fmt_path(path: Sequence[str]) -> str:
    return ".".join(path) if path else "(root)"


def _tables(
    data: Any, path: Tuple[str, ...] = ()
) -> List[Tuple[Tuple[str, ...], list]]:
    """Every list of >= 3 dicts in the document, with its path."""
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            out += _tables(v, path + (str(k),))
    elif isinstance(data, list):
        if len(data) >= 3 and all(isinstance(x, dict) for x in data):
            out.append((path, data))
        for i, x in enumerate(data[:1]):
            if isinstance(x, (dict, list)):
                out += [
                    (p, t) for p, t in _tables(x, path + ("[0]",)) if "[0]" not in p
                ]
    return out


def _leaves(data: Any, path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    """Scalar values outside of tables (configuration-like documents)."""
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if _scalar(v):
                out.append((path + (str(k),), v))
            elif isinstance(v, dict):
                out += _leaves(v, path + (str(k),))
    return out


def _key_field(rows: list) -> Optional[str]:
    common = [k for k in rows[0] if all(k in r and _scalar(r[k]) for r in rows)]
    for preferred in ("id", "name", "sku", "key", "rank", "date", "ts"):
        if preferred in common and len({str(r[preferred]) for r in rows}) == len(rows):
            return preferred
    for k in common:
        values = [r[k] for r in rows]
        if all(
            isinstance(v, (str, int)) and not isinstance(v, bool) for v in values
        ) and len({str(v) for v in values}) == len(rows):
            return k
    return None


def _lit(v: Any) -> str:
    """A value in a question as JSON, with letters as they are in the data
    ("Kraków", not "Krak\\u00f3w")."""
    return json.dumps(v, ensure_ascii=False)


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _ordinal(k: int) -> str:
    suffix = (
        "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    )
    return f"{k}{suffix}"


def _table_questions(
    rnd: random.Random, path: Tuple[str, ...], rows: list
) -> List[Question]:
    """Questions about one list of records."""
    pool: List[Question] = []
    where = f"`{_fmt_path(path)}`"
    key = _key_field(rows)
    fields = list(rows[0].keys())
    every = [
        k
        for k in dict.fromkeys(k for r in rows for k in r)
        if all(k in r for r in rows)
    ]
    pool.append(Question("length", f"How many items are in {where}?", len(rows)))
    if all(set(r.keys()) == set(fields) for r in rows):
        pool.append(
            Question(
                "fields",
                f"Which fields does each item in {where} have? List the field names.",
                fields,
            )
        )
    if key:
        ref = lambda row: f"the item whose `{key}` is {_lit(row[key])}"  # noqa: E731
        for _ in range(4):
            row = rnd.choice(rows)
            candidates = [k for k, v in row.items() if k != key and _scalar(v)]
            if candidates:
                f = rnd.choice(candidates)
                pool.append(
                    Question(
                        "lookup", f"In {where}, what is `{f}` of {ref(row)}?", row[f]
                    )
                )
        for _ in range(3):
            row = rnd.choice(rows)
            nested = [(k, v) for k, v in row.items() if isinstance(v, (dict, list))]
            if not nested:
                break
            k, v = rnd.choice(nested)
            if isinstance(v, dict):
                inner = [((ik,), iv) for ik, iv in v.items() if _scalar(iv)]
                inner += [
                    ((ik, jk), jv)
                    for ik, iv in v.items()
                    if isinstance(iv, dict)
                    for jk, jv in iv.items()
                    if _scalar(jv)
                ]
                if inner:
                    ipath, iv = rnd.choice(inner)
                    pool.append(
                        Question(
                            "nested",
                            f"In {where}, what is `{'.'.join((k,) + ipath)}` of {ref(row)}?",
                            iv,
                        )
                    )
            else:
                pool.append(
                    Question(
                        "nested",
                        f"In {where}, how many entries does `{k}` have for {ref(row)}?",
                        len(v),
                    )
                )
            # a sum over a nested list of records
            subs = [
                (k2, v2)
                for k2, v2 in row.items()
                if isinstance(v2, list) and v2 and all(isinstance(x, dict) for x in v2)
            ]
            for k2, v2 in subs[:1]:
                ints = [
                    f
                    for f in v2[0]
                    if all(
                        isinstance(x.get(f), int) and not isinstance(x.get(f), bool)
                        for x in v2
                    )
                ]
                if ints:
                    f = rnd.choice(ints)
                    pool.append(
                        Question(
                            "inner-sum",
                            f"In {where}, what is the sum of `{f}` over the `{k2}` of {ref(row)}?",
                            sum(x[f] for x in v2),
                        )
                    )
    # by position: records are read in order
    for _ in range(2):
        i = rnd.randrange(len(rows))
        row = rows[i]
        candidates = [k for k, v in row.items() if _scalar(v)]
        if candidates:
            f = rnd.choice(candidates)
            pos = (
                "the last item"
                if i == len(rows) - 1
                else f"the {_ordinal(i + 1)} item (counting from 1)"
            )
            pool.append(
                Question("position", f"In {where}, what is `{f}` of {pos}?", row[f])
            )
    # counts over categorical fields
    cats = [
        k
        for k in every
        if all(isinstance(r[k], (str, bool)) for r in rows)
        and 2 <= len({r[k] for r in rows}) <= 8
    ]
    for f in rnd.sample(cats, min(2, len(cats))):
        value = rnd.choice(sorted({r[f] for r in rows}, key=str))
        count = sum(1 for r in rows if r[f] == value)
        pool.append(
            Question(
                "count",
                f"How many items in {where} have `{f}` equal to {_lit(value)}?",
                count,
            )
        )
    if len(cats) >= 2:
        f1, f2 = rnd.sample(cats, 2)
        v1 = rnd.choice(sorted({r[f1] for r in rows}, key=str))
        v2 = rnd.choice(sorted({r[f2] for r in rows if r[f1] == v1}, key=str))
        count = sum(1 for r in rows if r[f1] == v1 and r[f2] == v2)
        pool.append(
            Question(
                "count2",
                f"How many items in {where} have `{f1}` equal to {_lit(v1)} and `{f2}` equal to {_lit(v2)}?",
                count,
            )
        )
    # values inside lists of strings
    lists = [
        k
        for k in every
        if all(
            isinstance(r[k], list) and all(isinstance(x, str) for x in r[k])
            for r in rows
        )
    ]
    for f in lists[:1]:
        values = sorted({x for r in rows for x in r[f]})
        if values:
            v = rnd.choice(values)
            pool.append(
                Question(
                    "contains",
                    f"How many items in {where} have {_lit(v)} in `{f}`?",
                    sum(1 for r in rows if v in r[f]),
                )
            )
    # nulls and optional fields
    nullable = [
        k
        for k in every
        if any(r[k] is None for r in rows) and any(r[k] is not None for r in rows)
    ]
    for f in nullable[:1]:
        pool.append(
            Question(
                "null",
                f"How many items in {where} have `{f}` equal to null?",
                sum(1 for r in rows if r[f] is None),
            )
        )
    optional = [k for k in dict.fromkeys(k for r in rows for k in r) if k not in every]
    for f in rnd.sample(optional, min(2, len(optional))):
        pool.append(
            Question(
                "optional",
                f"How many items in {where} have a `{f}` field at all (items without it do not count)?",
                sum(1 for r in rows if f in r),
            )
        )
    # extremes and filters over numeric fields
    nums = [k for k in every if all(_num(r[k]) for r in rows) and k != key]
    if key:
        for f in rnd.sample(nums, min(2, len(nums))):
            for word, pick in (("highest", max), ("lowest", min)):
                top = pick(r[f] for r in rows)
                winners = [r for r in rows if r[f] == top]
                if len(winners) == 1:
                    pool.append(
                        Question(
                            "extreme",
                            f"In {where}, which item has the {word} `{f}`? Answer with its `{key}`.",
                            winners[0][key],
                        )
                    )
        for f in rnd.sample(nums, min(1, len(nums))):
            values = sorted({r[f] for r in rows}, reverse=True)
            if len(values) >= 4:
                limit = values[min(len(values) - 1, rnd.randrange(1, 5))]
                hits = [r[key] for r in rows if r[f] > limit]
                if 1 <= len(hits) <= 6:
                    pool.append(
                        Question(
                            "filter",
                            f"In {where}, list the `{key}` of every item whose `{f}` is greater than {_lit(limit)}.",
                            hits,
                        )
                    )
    ints = [k for k in nums if all(isinstance(r[k], int) for r in rows)]
    if cats and ints:
        f, c = rnd.choice(ints), rnd.choice(cats)
        v = rnd.choice(sorted({r[c] for r in rows}, key=str))
        group = [r[f] for r in rows if r[c] == v]
        if 2 <= len(group) <= 15:
            pool.append(
                Question(
                    "aggregate",
                    f"In {where}, what is the sum of `{f}` over the items whose `{c}` is {_lit(v)}?",
                    sum(group),
                )
            )
    return pool


def _lists_of_values(
    data: Any, path: Tuple[str, ...] = ()
) -> List[Tuple[Tuple[str, ...], list]]:
    """Lists of scalars outside of tables (configuration-like documents)."""
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list) and v and all(_scalar(x) for x in v):
                out.append((path + (str(k),), v))
            elif isinstance(v, dict):
                out += _lists_of_values(v, path + (str(k),))
    return out


def make_questions(ds: Dataset, n: int = 16, seed: int = 7) -> List[Question]:
    """Deterministic questions with answers computed from the data."""
    rnd = random.Random(f"{seed}:{ds.name}")
    pool: List[Question] = []
    for path, rows in sorted(_tables(ds.data), key=lambda t: -len(t[1]))[:3]:
        pool += _table_questions(rnd, path, rows)
    for path, value in _leaves(ds.data):
        if len(path) >= 1:
            pool.append(
                Question("value", f"What is the value of `{_fmt_path(path)}`?", value)
            )
    for path, values in _lists_of_values(ds.data):
        pool.append(
            Question(
                "length",
                f"How many entries does `{_fmt_path(path)}` have?",
                len(values),
            )
        )

    # de-duplicate, shuffle within each kind, then sample evenly across kinds
    seen, unique = set(), []
    for q in pool:
        if q.text not in seen:
            seen.add(q.text)
            q.dataset = ds.name
            unique.append(q)
    by_kind: Dict[str, List[Question]] = {}
    for q in unique:
        by_kind.setdefault(q.kind, []).append(q)
    for qs in by_kind.values():
        rnd.shuffle(qs)
    kinds = list(by_kind)
    rnd.shuffle(kinds)
    picked: List[Question] = []
    while len(picked) < n and any(by_kind.values()):
        for kind in kinds:
            if by_kind[kind] and len(picked) < n:
                picked.append(by_kind[kind].pop(0))
    return picked


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?(?:e[+-]?\d+)?", re.I)


def _norm(s: str) -> str:
    s = s.strip().strip("`*_ ").rstrip(".").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    return s.rstrip(".").strip().lower()


def score(answer: Optional[str], expected: Any) -> bool:
    if answer is None:
        return False
    a = _norm(answer)
    if isinstance(expected, bool):
        return a in (("true", "yes") if expected else ("false", "no"))
    if expected is None:
        return a in ("null", "none", "nil", "n/a", "empty", "")
    if isinstance(expected, (int, float)):
        m = _NUM.findall(
            a.replace(",", "") if re.fullmatch(r"-?[\d,]+(\.\d+)?", a) else a
        )
        if not m:
            return False
        try:
            return abs(float(m[0].replace(",", ".")) - float(expected)) < 1e-6 * max(
                1.0, abs(float(expected))
            )
        except ValueError:
            return False
    if isinstance(expected, list):
        parts = [_norm(p) for p in re.split(r"[,\n;]+", answer) if _norm(p)]
        return sorted(parts) == sorted(_norm(str(x)) for x in expected)
    return a == _norm(str(expected))


def parse_answers(text: str, n: int) -> List[Optional[str]]:
    answers: List[Optional[str]] = [None] * n
    for line in text.splitlines():
        m = re.match(r"\s*(?:Q)?(\d+)\s*[.):\-]\s*(.*)$", line)
        if m:
            i = int(m.group(1)) - 1
            if 0 <= i < n and answers[i] is None:
                answers[i] = m.group(2)
    return answers


# ---------------------------------------------------------------------------
# Providers (standard library only)
# ---------------------------------------------------------------------------


@dataclass
class Reply:
    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    seconds: float = 0.0


class Provider:
    name = "provider"
    model = ""

    def complete(self, system: str, user: str, max_tokens: int = 800) -> Reply:
        raise NotImplementedError


def _post(
    url: str, headers: Dict[str, str], body: Dict[str, Any], timeout: float = 120
) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    delay = 2.0
    for attempt in range(5):
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json", **headers}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (429, 500, 502, 503, 504, 529) and attempt < 4:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < 2:
                time.sleep(delay)
                continue
            raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc
    raise RuntimeError(f"Giving up on {url}")


class OpenAICompatible(Provider):
    name = "openai"

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        reasoning: Optional[str] = None,
    ):
        self.model = model
        # GPT-5.x and o-series models take reasoning_effort, not temperature.
        self.reasoning_model = bool(re.match(r"^(o\d|gpt-5)", model.split("/")[-1]))
        self.reasoning = reasoning
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (
            base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        ).rstrip("/")

    def _body(self, system: str, user: str, max_tokens: int) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.reasoning_model:
            # GPT-5 / o-series: no temperature; the token limit also covers
            # the hidden reasoning, so it gets room for it.
            body["max_completion_tokens"] = max_tokens + REASONING_BUDGET
            if self.reasoning:
                body["reasoning_effort"] = self.reasoning
        else:
            body["temperature"] = 0
            body["max_tokens"] = max_tokens
        return body

    def complete(self, system: str, user: str, max_tokens: int = 800) -> Reply:
        t0 = time.perf_counter()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        url = f"{self.base_url}/chat/completions"
        try:
            out = _post(url, headers, self._body(system, user, max_tokens))
        except RuntimeError as exc:
            # A model that rejects temperature / max_tokens is a reasoning model.
            text = str(exc)
            if (
                self.reasoning_model
                or "HTTP 400" not in text
                or not ("temperature" in text or "max_tokens" in text)
            ):
                raise
            self.reasoning_model = True
            out = _post(url, headers, self._body(system, user, max_tokens))
        usage = out.get("usage") or {}
        text = (out.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return Reply(
            text,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            time.perf_counter() - t0,
        )


class Anthropic(Provider):
    name = "anthropic"

    def __init__(
        self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")

    def complete(self, system: str, user: str, max_tokens: int = 800) -> Reply:
        t0 = time.perf_counter()
        out = _post(
            f"{self.base_url}/v1/messages",
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        usage = out.get("usage") or {}
        text = "".join(
            b.get("text", "") for b in out.get("content", []) if b.get("type") == "text"
        )
        return Reply(
            text,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            time.perf_counter() - t0,
        )


class Scripted(Provider):
    """Answers with a function — for tests and for scoring a pipeline offline."""

    name = "scripted"

    def __init__(self, fn: Callable[[str, str], str], model: str = "scripted"):
        self.fn = fn
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 800) -> Reply:
        return Reply(self.fn(system, user))


DEFAULT_MODELS = {"openai": "gpt-5.4-mini", "anthropic": "claude-haiku-5-5"}
# Extra completion tokens for the hidden reasoning of GPT-5 / o-series models.
REASONING_BUDGET = 16000


def provider_from_env(
    provider: str = "auto",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> Optional[Provider]:
    """
    Picks a provider: explicit name, else OPENAI_API_KEY / OPENAI_BASE_URL,
    else ANTHROPIC_API_KEY. Returns None when nothing is configured (dry run).
    """
    try:  # optional .env support
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    if provider == "auto":
        if (
            base_url
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENAI_BASE_URL")
        ):
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            return None
    if provider in ("openai", "openai-compatible", "ollama", "openrouter"):
        if provider == "ollama" and not base_url:
            base_url = "http://localhost:11434/v1"
        if provider == "openrouter" and not base_url:
            base_url = "https://openrouter.ai/api/v1"
            api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        return OpenAICompatible(
            model or DEFAULT_MODELS["openai"], api_key, base_url, reasoning
        )
    if provider == "anthropic":
        return Anthropic(model or DEFAULT_MODELS["anthropic"], api_key, base_url)
    raise ValueError(
        f"Unknown provider '{provider}' (openai, anthropic, ollama, openrouter)"
    )


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def wilson(correct: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson confidence interval of a proportion."""
    if total <= 0:
        return (0.0, 0.0)
    p = correct / total
    d = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / d
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass
class Trial:
    dataset: str
    format: str
    questions: int
    correct: int
    prompt_tokens: int  # counted locally, same tokenizer for every format
    data_tokens: int
    hint_tokens: int
    api_input_tokens: Optional[int]
    api_output_tokens: Optional[int]
    seconds: float
    by_kind: Dict[str, List[int]] = field(
        default_factory=dict
    )  # kind -> [correct, total]
    misses: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    repeat: int = 0
    # Everything needed to check the trial by hand: the user prompt (the
    # system prompt is AIReport.system), the raw reply and, per question,
    # the parsed answer and whether it was scored right.
    prompt: str = ""
    reply: Optional[str] = None
    answers: List[Optional[str]] = field(default_factory=list)
    ok: List[bool] = field(default_factory=list)


@dataclass
class WriteTrial:
    dataset: str
    format: str
    valid: bool
    output_tokens: Optional[int]
    error: Optional[str] = None


@dataclass
class AIReport:
    provider: str
    model: str
    tokenizer: str
    source: str
    hint: str
    formats: Dict[str, str]
    dry_run: bool
    trials: List[Trial] = field(default_factory=list)
    writes: List[WriteTrial] = field(default_factory=list)
    questions: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    repeats: int = 1
    generated: int = 0
    seed: int = 7
    reasoning: Optional[str] = None
    system: str = SYSTEM
    questions_per_dataset: int = 16

    def summary(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for key in self.formats:
            ts = [t for t in self.trials if t.format == key and t.error is None]
            if not ts:
                continue
            errors = sum(1 for t in self.trials if t.format == key and t.error)
            q = sum(t.questions for t in ts)
            c = sum(t.correct for t in ts)
            # tokens of one pass over the questions (repeats send the same prompts)
            once = [t for t in ts if t.repeat == 0] or ts
            tokens = sum(t.prompt_tokens for t in once)
            api_in = [
                t.api_input_tokens for t in once if t.api_input_tokens is not None
            ]
            kinds: Dict[str, List[int]] = {}
            for t in ts:
                for k, (kc, kt) in t.by_kind.items():
                    kinds.setdefault(k, [0, 0])
                    kinds[k][0] += kc
                    kinds[k][1] += kt
            writes = [w for w in self.writes if w.format == key]
            real = not self.dry_run
            out[key] = {
                "accuracy": (c / q) if q and real else None,
                "ci95": list(wilson(c, q)) if q and real else None,
                "correct": c,
                "questions": q,
                "errors": errors,
                "prompt_tokens": tokens,
                "data_tokens": sum(t.data_tokens for t in once),
                "api_input_tokens": sum(api_in) if len(api_in) == len(once) else None,
                "api_output_tokens": sum(t.api_output_tokens or 0 for t in ts)
                if real
                else None,
                "seconds": sum(t.seconds for t in ts),
                "correct_per_10k_tokens": (
                    c / len({t.repeat for t in ts}) / tokens * 10000
                )
                if tokens and real
                else None,
                "by_kind": {k: v[0] / v[1] for k, v in kinds.items() if v[1]}
                if real
                else {},
                "by_kind_n": {k: v[1] for k, v in kinds.items()},
                "write_valid": (sum(w.valid for w in writes) / len(writes))
                if writes
                else None,
            }
        return out

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["summary"] = self.summary()
        return d


def _use_hint(hint: str, key: str) -> bool:
    if hint == "all":
        return key in HINTS
    return hint == "auto" and key in AK_KEYS


def _prompt(
    fmt: Format, data: Any, questions: List[Question], hint: bool
) -> Tuple[str, str, str]:
    payload = fmt.encode(data)
    hint_text = HINTS.get(fmt.key, "") if hint else ""
    lines = [hint_text] if hint_text else []
    lines += [f"<data>\n{payload}\n</data>", "", "Questions:"]
    lines += [f"{i}. {q.text}" for i, q in enumerate(questions, 1)]
    return "\n".join(lines), payload, hint_text


def _write_prompt(fmt: Format, sample: Any) -> str:
    target = {
        "json": "JSON",
        "json-min": "minified JSON",
        "yaml": "YAML",
        "toon": "TOON",
        "akd": "AK-Data",
        "akcd": "AK-Data (single line)",
        "akd-n": "AK-Data",
        "akcd-n": "AK-Data (single line)",
    }[fmt.key]
    guide = HINTS.get(fmt.key, "")
    example = ""
    if fmt.key in HINTS:
        example = f"\nExample of {target}:\n" + fmt.encode(
            {"items": [{"id": 1, "tag": "a"}, {"id": 2, "tag": "b"}]}
        )
    return (
        f"Convert this JSON to {target}. {guide}{example}\n\n"
        f"JSON:\n{json.dumps(sample, ensure_ascii=False)}\n\n"
        f"Output only the {target}, no explanations, no code fences."
    )


def _write_sample(ds: Dataset) -> Optional[Any]:
    tables = _tables(ds.data)
    if not tables:
        return None
    path, rows = max(tables, key=lambda t: len(t[1]))
    return {path[-1] if path else "items": rows[:4]}


def _default_keys(formats: Optional[List[str]]) -> Tuple[Dict[str, Format], List[str]]:
    all_formats = available_formats(variants=True)
    default = [k for k in DEFAULT_FORMATS if k in all_formats]
    return all_formats, [k for k in (formats or default) if k in all_formats]


def benchmark_sets(
    directory: Optional[str] = None, random_sets: int = 0, seed: int = 7
) -> List[Dataset]:
    """The bundled datasets (or a directory) plus `random_sets` generated ones."""
    return resolve(directory) + (generate(random_sets, seed) if random_sets else [])


def list_prompts(
    directory: Optional[str] = None,
    formats: Optional[List[str]] = None,
    questions: int = 16,
    hint: str = "all",
    write: bool = False,
    datasets: Optional[List[Dataset]] = None,
    random_sets: int = 0,
    seed: int = 7,
) -> List[Dict[str, Any]]:
    """Every prompt the AI benchmark would send, without calling a model."""
    all_formats, keys = _default_keys(formats)
    sets = (
        datasets
        if datasets is not None
        else benchmark_sets(directory, random_sets, seed)
    )
    out: List[Dict[str, Any]] = []
    for ds in sets:
        qs = make_questions(ds, questions, seed)
        if not qs:
            continue
        for key in keys:
            user, _, _ = _prompt(all_formats[key], ds.data, qs, _use_hint(hint, key))
            out.append(
                {
                    "dataset": ds.name,
                    "format": key,
                    "kind": "questions",
                    "system": SYSTEM,
                    "user": user,
                    "answers": [q.answer for q in qs],
                }
            )
        sample = _write_sample(ds) if write else None
        if sample is not None:
            for key in keys:
                if all_formats[key].decode:
                    out.append(
                        {
                            "dataset": ds.name,
                            "format": key,
                            "kind": "write",
                            "system": "You convert data between formats.",
                            "user": _write_prompt(all_formats[key], sample),
                            "answers": None,
                        }
                    )
    return out


def run(
    provider: Optional[Provider],
    directory: Optional[str] = None,
    formats: Optional[List[str]] = None,
    questions: int = 16,
    hint: str = "all",
    write: bool = False,
    encoding: str = "o200k_base",
    parallel: int = 4,
    datasets: Optional[List[Dataset]] = None,
    progress: Optional[Callable[[str], None]] = None,
    random_sets: int = 0,
    seed: int = 7,
    repeats: int = 1,
) -> AIReport:
    """
    provider=None is a dry run: questions and prompt sizes, no model calls.
    hint: "all" (format definition for AK-Data and TOON), "auto" (AK-Data
    only), "none". random_sets adds that many generated datasets (seed);
    repeats sends every prompt that many times (answers vary between calls).
    """
    tok = get_tokenizer(encoding)
    all_formats, keys = _default_keys(formats)
    sets = (
        datasets
        if datasets is not None
        else benchmark_sets(directory, random_sets, seed)
    )
    source = directory or "bundled datasets"
    if random_sets and datasets is None:
        source += f" + {random_sets} generated (seed {seed})"
    report = AIReport(
        provider=provider.name if provider else "dry-run",
        model=provider.model if provider else "",
        tokenizer=tok.label,
        source=source,
        hint=hint,
        formats={k: all_formats[k].label for k in keys},
        dry_run=provider is None,
        repeats=max(1, repeats),
        generated=random_sets if datasets is None else 0,
        seed=seed,
        reasoning=getattr(provider, "reasoning", None),
        questions_per_dataset=questions,
    )

    jobs = []
    for ds in sets:
        qs = make_questions(ds, questions, seed)
        if not qs:
            continue
        report.questions[ds.name] = [asdict(q) for q in qs]
        for repeat in range(report.repeats if provider else 1):
            for key in keys:
                jobs.append((ds, all_formats[key], qs, _use_hint(hint, key), repeat))

    def ask(job):
        ds, fmt, qs, use_hint, repeat = job
        user, payload, hint_text = _prompt(fmt, ds.data, qs, use_hint)
        trial = Trial(
            ds.name,
            fmt.key,
            len(qs),
            0,
            tok.count(SYSTEM) + tok.count(user),
            tok.count(payload),
            tok.count(hint_text) if hint_text else 0,
            None,
            None,
            0.0,
            repeat=repeat,
            prompt=user,
        )
        if provider is None:
            return trial
        try:
            reply = provider.complete(SYSTEM, user, max_tokens=40 + 40 * len(qs))
        except Exception as exc:
            trial.error = str(exc)[:300]
            if progress:
                progress(f"{ds.name:22} {fmt.key:8} error: {trial.error[:80]}")
            return trial
        trial.api_input_tokens = reply.input_tokens
        trial.api_output_tokens = reply.output_tokens
        trial.seconds = reply.seconds
        trial.reply = reply.text
        for q, a in zip(qs, parse_answers(reply.text, len(qs))):
            ok = score(a, q.answer)
            trial.answers.append(a)
            trial.ok.append(bool(ok))
            trial.correct += ok
            k = trial.by_kind.setdefault(q.kind, [0, 0])
            k[0] += ok
            k[1] += 1
            if not ok:
                trial.misses.append(
                    {"q": q.text, "kind": q.kind, "expected": q.answer, "got": a}
                )
        if progress:
            progress(f"{ds.name:22} {fmt.key:8} {trial.correct}/{trial.questions}")
        return trial

    with ThreadPoolExecutor(max_workers=max(1, parallel if provider else 1)) as pool:
        report.trials = list(pool.map(ask, jobs))

    if write and provider is not None:
        write_jobs = []
        for ds in sets:
            sample = _write_sample(ds)
            if sample is not None:
                write_jobs += [
                    (ds, all_formats[k], sample) for k in keys if all_formats[k].decode
                ]

        def produce(job):
            ds, fmt, sample = job
            try:
                reply = provider.complete(
                    "You convert data between formats.",
                    _write_prompt(fmt, sample),
                    1500,
                )
                text = reply.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                back = fmt.decode(text)
                return WriteTrial(ds.name, fmt.key, back == sample, reply.output_tokens)
            except Exception as exc:
                return WriteTrial(ds.name, fmt.key, False, None, str(exc)[:200])

        with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
            report.writes = list(pool.map(produce, write_jobs))
    return report


def to_markdown(report: AIReport) -> str:
    s = report.summary()
    keys = [k for k in report.formats if k in s]
    who = (
        "dry run (no model)"
        if report.dry_run
        else f"{report.provider} · `{report.model}`"
        + (f" (reasoning: {report.reasoning})" if report.reasoning else "")
    )
    n_questions = sum(len(v) for v in report.questions.values())
    lines = [
        f"# ak-data AI benchmark — {who}",
        "",
        f"Datasets: {report.source} ({len(report.questions)}) · questions: {n_questions}"
        + (f" × {report.repeats} repeats" if report.repeats > 1 else "")
        + f" · hint: {report.hint} · tokens counted with {report.tokenizer}",
        "",
        "Accuracy with its 95% confidence interval: two formats whose intervals overlap",
        "are not shown to differ by this run.",
        "",
        "| format | accuracy | 95% CI | prompt tokens | data tokens | correct / 10k tokens | write valid |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for k in keys:
        r = s[k]
        acc = (
            f"{r['accuracy'] * 100:.1f}% ({r['correct']}/{r['questions']})"
            if r["accuracy"] is not None
            else "–"
        )
        ci = (
            f"{r['ci95'][0] * 100:.1f}–{r['ci95'][1] * 100:.1f}%"
            if r.get("ci95")
            else "–"
        )
        eff = (
            f"{r['correct_per_10k_tokens']:.1f}"
            if r["correct_per_10k_tokens"] is not None
            else "–"
        )
        wv = f"{r['write_valid'] * 100:.0f}%" if r["write_valid"] is not None else "–"
        err = f" ({r['errors']} failed requests)" if r.get("errors") else ""
        lines.append(
            f"| {report.formats[k]} | {acc}{err} | {ci} | {r['prompt_tokens']:,} | {r['data_tokens']:,} | {eff} | {wv} |"
        )
    if not report.dry_run:
        kinds = sorted({kind for k in keys for kind in s[k]["by_kind"]})
        if kinds:
            lines += [
                "",
                "| question type | n | "
                + " | ".join(report.formats[k] for k in keys)
                + " |",
                "|---|---:|" + "---:|" * len(keys),
            ]
            for kind in kinds:
                n = max(s[k]["by_kind_n"].get(kind, 0) for k in keys)
                vals = [f"{s[k]['by_kind'].get(kind, 0) * 100:.0f}%" for k in keys]
                lines.append(f"| {kind} | {n} | " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"
