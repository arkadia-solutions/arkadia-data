"""
Differences between documents, merging, applying changes and the change
history kept in a document — the same results as the Rust crate and the npm
package (``ak-data diff | merge | apply | history``).

A change is ``add``, ``remove``, ``change`` or ``order`` at a path
(``users[id=2].name``, ``tags[1]``, ``config.debug``) with the old and the new
value. Lists of records are matched by a key field (``id``, ``key``, ``name``,
``slug``, ``sku``, ``code``, ``uuid`` or the first field) when it is present
and unique in both lists, otherwise by position; ``order`` records a new
order of such a list.

The history is a list of change sets stored as the attribute ``$changes``:
metadata, so ``loads`` of the document still gives exactly the data.

    from arkadia.data import diff

    changes = diff.diff(old, new)            # [Change(op, path, old, new), …]
    diff.apply(old, changes) == new          # True
    text = diff.commit(text, new, title="Rename Alan", author="Ada")
    diff.history(text)                       # [ChangeSet(id, date, …), …]
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .api import dumps, loads, loads_any

__all__ = [
    "Change",
    "ChangeSet",
    "Conflict",
    "ConflictError",
    "diff",
    "merge",
    "apply",
    "apply_with",
    "reverse",
    "summary",
    "parse_path",
    "change_id",
    "changes_json",
    "changes_from_json",
    "history",
    "attributes",
    "with_history",
    "commit",
    "now",
]

OPS = ("add", "remove", "change", "order")
KEYS = ("id", "key", "name", "slug", "sku", "code", "uuid")


@dataclass
class Change:
    """One change: op is add, remove, change or order."""

    op: str
    path: str
    old: Any = None
    new: Any = None

    def to_json(self) -> dict:
        return {"op": self.op, "path": self.path, "old": self.old, "new": self.new}


@dataclass
class Conflict:
    """A change that does not fit the document."""

    index: int
    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


class ConflictError(ValueError):
    """Raised by apply() when changes do not fit; .conflicts lists them."""

    def __init__(self, conflicts: list[Conflict]):
        self.conflicts = conflicts
        super().__init__(
            f"{len(conflicts)} change(s) do not fit: "
            + "; ".join(map(str, conflicts[:3]))
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _eq(a: Any, b: Any) -> bool:
    """JSON equality (True is not 1)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict):
        return (
            isinstance(b, dict)
            and len(a) == len(b)
            and all(k in b and _eq(v, b[k]) for k, v in a.items())
        )
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(map(_eq, a, b))
    if a is None or b is None:
        return a is b
    if isinstance(a, (int, float)):
        return isinstance(b, (int, float)) and a == b
    return type(a) is type(b) and a == b


def _in(x: Any, items: list) -> bool:
    return any(_eq(x, y) for y in items)


def _scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _ident(s: str) -> bool:
    return (
        bool(s)
        and (s[0].isascii() and (s[0].isalpha() or s[0] == "_"))
        and all(c.isascii() and (c.isalnum() or c == "_") for c in s)
    )


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _list_key(a: list, b: list) -> Optional[str]:
    items = a + b
    if not items or not all(isinstance(x, dict) for x in items):
        return None
    candidates = list(KEYS)
    first = next(iter(items[0]), None)
    if first is not None:
        candidates.append(first)

    def unique(lst: list, k: str) -> bool:
        seen: list = []
        for x in lst:
            v = x.get(k, None) if k in x else None
            if k not in x or v is None or not _scalar(v) or _in(v, seen):
                return False
            seen.append(v)
        return True

    for k in candidates:
        if unique(a, k) and unique(b, k):
            return k
    return None


def _child(path: str, key: str) -> str:
    part = key if _ident(key) else f"[{_json(key)}]"
    if path == "$":
        return part
    return f"{path}{part}" if part.startswith("[") else f"{path}.{part}"


def _item(path: str, label: str) -> str:
    return f"{'' if path == '$' else path}[{label}]"


def _key_label(key: str, v: Any) -> str:
    name = key if _ident(key) else _json(key)
    return f"{name}={_json(v)}"


# ---------------------------------------------------------------------------
# diff / merge
# ---------------------------------------------------------------------------


def _walk(a: Any, b: Any, path: str, out: list[Change]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k, va in a.items():
            if k in b:
                _walk(va, b[k], _child(path, k), out)
            else:
                out.append(Change("remove", _child(path, k), va, None))
        for k, vb in b.items():
            if k not in a:
                out.append(Change("add", _child(path, k), None, vb))
        return
    if isinstance(a, list) and isinstance(b, list):
        key = _list_key(a, b)
        if key is not None:
            removed = []
            for ia in a:
                p = _item(path, _key_label(key, ia[key]))
                match = next((ib for ib in b if _eq(ib[key], ia[key])), None)
                if match is not None:
                    _walk(ia, match, p, out)
                else:
                    removed.append(Change("remove", p, ia, None))
            out.extend(reversed(removed))
            for ib in b:
                if not any(_eq(ia[key], ib[key]) for ia in a):
                    out.append(
                        Change("add", _item(path, _key_label(key, ib[key])), None, ib)
                    )
            ka, kb = [x[key] for x in a], [x[key] for x in b]

            def naive(src: list, dst: list) -> list:
                return [k for k in src if _in(k, dst)] + [
                    k for k in dst if not _in(k, src)
                ]

            if not _eq(naive(ka, kb), kb) or not _eq(naive(kb, ka), ka):
                out.append(Change("order", path, ka, kb))
            return
        common = min(len(a), len(b))
        for i in range(common):
            _walk(a[i], b[i], _item(path, str(i)), out)
        for i in range(len(a) - 1, common - 1, -1):
            out.append(Change("remove", _item(path, str(i)), a[i], None))
        for i in range(common, len(b)):
            out.append(Change("add", _item(path, str(i)), None, b[i]))
        return
    if not _eq(a, b):
        out.append(Change("change", path, a, b))


def diff(a: Any, b: Any) -> list[Change]:
    """The changes that turn ``a`` into ``b`` (``apply(a, diff(a, b)) == b``)."""
    out: list[Change] = []
    _walk(a, b, "$", out)
    return out


def merge(a: Any, b: Any) -> Any:
    """``b`` merged into ``a``: records field by field (``b`` wins, fields only
    in ``a`` stay), lists of records by key (new records appended), other
    lists and values replaced by ``b``'s."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = {k: (merge(v, b[k]) if k in b else v) for k, v in a.items()}
        for k, v in b.items():
            if k not in a:
                out[k] = v
        return out
    if isinstance(a, list) and isinstance(b, list):
        key = _list_key(a, b)
        if key is None:
            return b
        out = []
        for ia in a:
            match = next((ib for ib in b if _eq(ib[key], ia[key])), None)
            out.append(merge(ia, match) if match is not None else ia)
        out.extend(ib for ib in b if not any(_eq(ia[key], ib[key]) for ia in a))
        return out
    return b


def summary(changes: list[Change]) -> tuple[int, int, int]:
    """Counts of added, removed and changed values (``order`` not counted)."""
    return tuple(
        sum(1 for c in changes if c.op == op) for op in ("add", "remove", "change")
    )  # type: ignore[return-value]


def reverse(changes: list[Change]) -> list[Change]:
    """The changes that undo ``changes``."""
    swap = {"add": "remove", "remove": "add"}
    out = [
        Change(swap.get(c.op, c.op), c.path, c.new, c.old) for c in reversed(changes)
    ]
    i = 0
    while i < len(out):
        if out[i].op == "order":
            lst = out[i].path

            def inside(p: str) -> bool:
                if lst == "$":
                    return p.startswith("[")
                return p.startswith(lst) and p[len(lst) : len(lst) + 1] == "["

            last = next(
                (j for j in range(len(out) - 1, i, -1) if inside(out[j].path)), None
            )
            if last is not None:
                out.insert(last, out.pop(i))
                continue
        i += 1
    return out


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def parse_path(path: str) -> list[tuple]:
    """``users[id=2].tags[1]`` → [("key", "users"), ("match", "id", 2),
    ("key", "tags"), ("index", 1)]; ``$`` → []."""
    i, steps, n = 0, [], len(path)

    def err(msg: str) -> ValueError:
        return ValueError(f"invalid path '{path}': {msg}")

    def ident() -> str:
        nonlocal i
        start = i
        while i < n and path[i].isascii() and (path[i].isalnum() or path[i] == "_"):
            i += 1
        return path[start:i]

    def string() -> str:
        nonlocal i
        start = i
        i += 1
        while i < n and path[i] != '"':
            i += 2 if path[i] == "\\" else 1
        i += 1
        try:
            return json.loads(path[start:i])
        except ValueError:
            raise err("bad quoted name") from None

    if path.startswith("$"):
        i = 1
    while i < n:
        ch = path[i]
        if ch == ".":
            i += 1
            name = ident()
            if not name:
                raise err("name expected after '.'")
            steps.append(("key", name))
        elif ch == "[":
            i += 1
            if i < n and path[i].isdigit():
                start = i
                while i < n and path[i].isdigit():
                    i += 1
                steps.append(("index", int(path[start:i])))
            else:
                name = string() if i < n and path[i] == '"' else ident()
                if i < n and path[i] == "=":
                    i += 1
                    start = i
                    if i < n and path[i] == '"':
                        string()
                    else:
                        while i < n and path[i] != "]":
                            i += 1
                    try:
                        value = json.loads(path[start:i])
                    except ValueError:
                        raise err("bad key value") from None
                    steps.append(("match", name, value))
                else:
                    steps.append(("key", name))
            if i >= n or path[i] != "]":
                raise err("']' expected")
            i += 1
        elif not steps and (ch.isascii() and (ch.isalpha() or ch == "_")):
            steps.append(("key", ident()))
        else:
            raise err(f"unexpected '{ch}'")
    return steps


_MISSING = object()


def _find(lst: list, key: str, v: Any) -> int:
    for i, x in enumerate(lst):
        if isinstance(x, dict) and key in x and _eq(x[key], v):
            return i
    return -1


def _step(value: Any, step: tuple) -> Any:
    kind = step[0]
    if kind == "key" and isinstance(value, dict):
        return value.get(step[1], _MISSING)
    if kind == "index" and isinstance(value, list):
        return value[step[1]] if step[1] < len(value) else _MISSING
    if kind == "match" and isinstance(value, list):
        i = _find(value, step[1], step[2])
        return value[i] if i >= 0 else _MISSING
    return _MISSING


def _get(value: Any, steps: list) -> Any:
    for s in steps:
        if value is _MISSING:
            return _MISSING
        value = _step(value, s)
    return value


def _short(v: Any) -> str:
    if v is _MISSING:
        return "nothing"
    s = _json(v)
    return s if len(s) <= 60 else s[:59] + "…"


def _set(parent: Any, step: tuple, value: Any) -> None:
    kind = step[0]
    if kind == "key":
        parent[step[1]] = value
    elif kind == "index":
        parent[step[1]] = value
    else:
        parent[_find(parent, step[1], step[2])] = value


def _apply_one(doc: list, c: Change, force: bool) -> None:
    """doc is a one-item box [value]; raises ValueError with the reason."""
    steps = parse_path(c.path)
    if c.op == "order":
        lst = _get(doc[0], steps)
        if not isinstance(lst, list):
            raise ValueError("no list here")
        key = _list_key(lst, lst)
        if key is None:
            raise ValueError("the list has no key field")
        order = c.new or []

        def pos(x: Any) -> int:
            return next(
                (i for i, k in enumerate(order) if _eq(k, x.get(key))), len(order)
            )

        lst.sort(key=pos)
        return
    if not steps:
        if not force and c.op != "add" and not _eq(doc[0], c.old):
            raise ValueError(f"expected {_short(c.old)}, found {_short(doc[0])}")
        doc[0] = c.new
        return
    current = _get(doc[0], steps)
    parent = _get(doc[0], steps[:-1])
    last = steps[-1]
    if parent is _MISSING or not isinstance(parent, (dict, list)):
        raise ValueError("the parent does not exist")
    if c.op == "change":
        if current is _MISSING:
            raise ValueError("nothing to change here")
        if not force and not _eq(current, c.old):
            raise ValueError(f"expected {_short(c.old)}, found {_short(current)}")
        _set(parent, last, c.new)
    elif c.op == "add":
        if current is not _MISSING:
            if _eq(current, c.new):
                return
            if not force:
                raise ValueError(f"already exists: {_short(current)}")
            _set(parent, last, c.new)
            return
        kind = last[0]
        if kind == "key" and isinstance(parent, dict):
            parent[last[1]] = c.new
        elif kind == "index" and isinstance(parent, list):
            if last[1] > len(parent):
                raise ValueError(
                    f"index {last[1]} is past the end ({len(parent)} items)"
                )
            parent.insert(last[1], c.new)
        elif kind == "match" and isinstance(parent, list):
            parent.append(c.new)
        else:
            raise ValueError("cannot add here")
    elif c.op == "remove":
        if current is _MISSING:
            raise ValueError("nothing to remove here")
        if not force and not _eq(current, c.old):
            raise ValueError(f"expected {_short(c.old)}, found {_short(current)}")
        kind = last[0]
        if kind == "key":
            del parent[last[1]]
        elif kind == "index":
            del parent[last[1]]
        else:
            del parent[_find(parent, last[1], last[2])]
    else:
        raise ValueError(f"unknown op {c.op!r}")


def apply_with(
    data: Any, changes: list[Change], force: bool = False
) -> tuple[Any, list[Conflict]]:
    """Applies what fits (``force``: also over a different old value); returns
    the new value and the conflicts of the skipped changes."""
    doc = [json.loads(json.dumps(data))]
    conflicts = []
    for i, c in enumerate(changes):
        try:
            _apply_one(doc, c, force)
        except ValueError as e:
            conflicts.append(Conflict(i, c.path, str(e)))
    return doc[0], conflicts


def apply(data: Any, changes: list[Change], force: bool = False) -> Any:
    """``changes`` applied to ``data``. Raises ConflictError when a change does
    not fit (unless ``force``)."""
    value, conflicts = apply_with(data, changes, force)
    if conflicts and not force:
        raise ConflictError(conflicts)
    return value


# ---------------------------------------------------------------------------
# Change sets and history
# ---------------------------------------------------------------------------


def now() -> str:
    """Now in UTC: ``2026-11-01T17:20:00Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def changes_json(changes: list[Change]) -> list[dict]:
    return [c.to_json() for c in changes]


def changes_from_json(value: Any) -> list[Change]:
    if not isinstance(value, list):
        raise ValueError("changes must be a list")
    out = []
    for c in value:
        if not isinstance(c, dict) or c.get("op") not in OPS:
            raise ValueError("a change needs op: add, remove, change or order")
        if not isinstance(c.get("path"), str):
            raise ValueError("a change needs a path")
        out.append(Change(c["op"], c["path"], c.get("old"), c.get("new")))
    return out


def _fnv1a(text: str) -> int:
    h = 0xCBF29CE484222325
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def change_id(
    parent: Optional[str],
    date: str,
    changes: list[Change],
    author: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """FNV-1a of the parent id, date, author, title, description and the
    changes as compact JSON — 10 hex digits, as in Rust and TypeScript."""
    text = "\n".join(
        [
            parent or "",
            date,
            author or "",
            title or "",
            description or "",
            _json(changes_json(changes)),
        ]
    )
    return f"{_fnv1a(text):016x}"[:10]


@dataclass
class ChangeSet:
    """One entry of the history."""

    id: str
    date: str
    author: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    changes: list[Change] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        changes: list[Change],
        *,
        title: Optional[str] = None,
        author: Optional[str] = None,
        description: Optional[str] = None,
        date: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> "ChangeSet":
        date = date or now()
        title, author, description = (v or None for v in (title, author, description))
        return cls(
            change_id(parent, date, changes, author, title, description),
            date,
            author,
            title,
            description,
            list(changes),
        )

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "author": self.author,
            "title": self.title,
            "description": self.description,
            "changes": changes_json(self.changes),
        }

    @classmethod
    def from_json(cls, v: dict) -> "ChangeSet":
        if not isinstance(v, dict) or "changes" not in v:
            raise ValueError("a change set needs 'changes'")
        return cls(
            v.get("id") or "",
            v.get("date") or "",
            v.get("author"),
            v.get("title"),
            v.get("description"),
            changes_from_json(v["changes"]),
        )


class _Scan:
    def __init__(self, text: str):
        self.t, self.i, self.n = text, 0, len(text)

    def peek(self) -> str:
        return self.t[self.i] if self.i < self.n else ""

    def at(self, s: str) -> bool:
        return self.t.startswith(s, self.i)

    def ws(self) -> None:
        while self.i < self.n and self.t[self.i].isspace():
            self.i += 1

    def string(self, q: str) -> None:
        self.i += 1
        while self.i < self.n:
            ch = self.t[self.i]
            self.i += 1
            if ch == "\\" and q == '"':
                self.i += 1
            elif ch == q:
                return

    def comment(self) -> None:
        self.i += 2
        depth = 1
        while depth and self.i < self.n:
            if self.at("/*"):
                depth += 1
                self.i += 2
            elif self.at("*/"):
                depth -= 1
                self.i += 2
            else:
                self.i += 2 if self.t[self.i] == "\\" else 1

    def ident(self) -> str:
        if self.peek() == "`":
            start = self.i + 1
            self.string("`")
            return self.t[start : max(start, self.i - 1)]
        start = self.i
        while self.i < self.n and (
            self.t[self.i].isascii()
            and (self.t[self.i].isalnum() or self.t[self.i] == "_")
        ):
            self.i += 1
        return self.t[start : self.i]

    def group(self) -> None:
        depth = 0
        while self.i < self.n:
            ch = self.t[self.i]
            if ch in '"`':
                self.string(ch)
                continue
            if self.at("/*"):
                self.comment()
                continue
            if ch in "<[({":
                depth += 1
            elif ch in ">])}":
                depth -= 1
                if depth <= 0:
                    self.i += 1
                    return
            self.i += 1

    def token(self) -> None:
        while self.i < self.n and not (
            self.t[self.i].isspace() or self.t[self.i] in "<>()[]{},/"
        ):
            self.i += 1

    def value(self) -> None:
        self.ws()
        ch = self.peek()
        if ch == "<":
            self.group()
            self.value()
        elif ch == "@":
            self.i += 1
            self.ident()
            self.ws()
            if self.peek() == "<":
                self.group()
            self.value()
        elif ch and ch in "[({":
            self.group()
        elif ch == '"':
            self.string('"')
        else:
            self.token()

    def attribute(self, out: dict) -> None:
        self.i += 1
        name = self.ident()
        self.ws()
        if self.peek() == "=":
            self.i += 1
            self.ws()
            start = self.i
            self.value()
            raw = self.t[start : self.i]
            try:
                out[name] = loads(raw)
            except ValueError:
                out[name] = raw
        else:
            out[name] = True


def attributes(text: str) -> dict:
    """The attributes of the document itself (``$name=value`` outside the
    data, in or out of ``// … //`` blocks), e.g. ``$changes``."""
    s = _Scan(text)
    out: dict = {}
    while True:
        s.ws()
        ch = s.peek()
        if not ch:
            break
        if s.at("/*"):
            s.comment()
        elif s.at("//"):
            s.i += 2
            while True:
                s.ws()
                c = s.peek()
                if not c:
                    break
                if s.at("//"):
                    s.i += 2
                    break
                if s.at("/*"):
                    s.comment()
                elif c == "$":
                    s.attribute(out)
                elif c == "#":
                    s.i += 1
                    s.ident()
                else:
                    start = s.i
                    s.ident()
                    s.ws()
                    if s.peek() == "=":
                        s.i += 1
                        s.ws()
                        s.value()
                    if s.i == start:
                        s.i += 1
        elif ch == "$":
            s.attribute(out)
        elif ch in "#@":
            s.i += 1
            s.ident()
        elif ch in "<[({":
            s.group()
        elif ch == '"':
            s.string('"')
        else:
            start = s.i
            s.token()
            if s.i == start:
                s.i += 1
    return out


def history(text: str) -> list[ChangeSet]:
    """The history of a document: its ``$changes`` attribute (oldest first)."""
    value = attributes(text).get("changes")
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        try:
            out.append(ChangeSet.from_json(v))
        except ValueError:
            pass
    return out


def with_history(data: Any, history: list[ChangeSet]) -> str:
    """``data`` as compact AK-DATA with ``// $changes=[…] //`` after it."""
    body = dumps(data)
    if not history:
        return body
    return f"{body} // $changes={dumps([s.to_json() for s in history])} //"


def commit(
    text: str,
    data: Any,
    *,
    title: Optional[str] = None,
    author: Optional[str] = None,
    description: Optional[str] = None,
    date: Optional[str] = None,
) -> str:
    """The document ``text`` updated to ``data``, the change recorded in its
    history (unchanged when the data is the same)."""
    old = loads_any(text)
    past = [] if text.lstrip()[:1] in ("{", "[") and _is_json(text) else history(text)
    changes = diff(old, data)
    if changes:
        past = past + [
            ChangeSet.new(
                changes,
                title=title,
                author=author,
                description=description,
                date=date,
                parent=past[-1].id if past else None,
            )
        ]
    return with_history(data, past)


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False
