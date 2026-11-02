"""
Readable layout of AK-DATA text — the same algorithm (and output) as
`arkadia_data::layout` in Rust and `pretty` / `compact` in `@arkadia/data`.

    pretty(text, 80)      re-flow to a line width: groups that fit stay on one
                          line, records fill lines, headers and lists of
                          records get one item per line
    compact(text)         one line, no optional spaces (metadata kept)
    strip_meta(text, comments=False, attributes=False)
                          the compact text with comments and/or attributes,
                          tags and // … // blocks removed

Whitespace is not significant in AK-DATA, so every result decodes to the same
value as the input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

_CLOSE = {"<": ">", "(": ")", "[": "]", "{": "}"}


@dataclass
class _Atom:
    text: str
    space_before: bool


@dataclass
class _Group:
    open: str
    close: str
    items: List[List["_Node"]] = field(default_factory=list)
    space_before: bool = False


_Node = Union[_Atom, _Group]


def _is_header(n: _Node) -> bool:
    return isinstance(n, _Group) and n.open == "<"


def _is_meta(n: _Node) -> bool:
    return isinstance(n, _Atom) and (
        n.text.startswith("/*") or n.text.startswith("//") or n.text[:1] in ("$", "#")
    )


def _is_comment(n: _Node) -> bool:
    return isinstance(n, _Atom) and n.text.startswith("/*")


class _Parser:
    def __init__(self, text: str):
        self.t = text
        self.i = 0

    def peek(self, k: int = 0) -> Optional[str]:
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def quoted(self, q: str) -> str:
        out = [q]
        self.i += 1
        while self.i < len(self.t):
            c = self.t[self.i]
            out.append(c)
            self.i += 1
            if c == "\\" and q == '"':
                if self.i < len(self.t):
                    out.append(self.t[self.i])
                    self.i += 1
                continue
            if c == q:
                break
        return "".join(out)

    def comment(self) -> str:
        out = []
        if self.peek(1) == "*":
            depth = 0
            while self.i < len(self.t):
                c = self.t[self.i]
                if c == "/" and self.peek(1) == "*":
                    depth += 1
                    out.append("/*")
                    self.i += 2
                    continue
                if c == "*" and self.peek(1) == "/":
                    depth -= 1
                    out.append("*/")
                    self.i += 2
                    if depth == 0:
                        break
                    continue
                out.append(c)
                self.i += 1
        else:
            out.append("//")
            self.i += 2
            while self.i < len(self.t):
                c = self.t[self.i]
                if c == "/" and self.peek(1) == "/":
                    out.append("//")
                    self.i += 2
                    break
                if c == '"':
                    out.append(self.quoted('"'))
                    continue
                out.append(" " if c.isspace() else c)
                self.i += 1
        return "".join(out)

    def items(self, close: Optional[str]) -> List[List[_Node]]:
        items: List[List[_Node]] = [[]]
        space = False
        while self.i < len(self.t):
            c = self.t[self.i]
            if c.isspace():
                space = True
                self.i += 1
                continue
            if c == close:
                self.i += 1
                break
            if c == ",":
                self.i += 1
                items.append([])
                space = False
                continue
            if c in _CLOSE:
                self.i += 1
                node: _Node = _Group(c, _CLOSE[c], self.items(_CLOSE[c]), space)
            elif c in ">)]}":
                self.i += 1
                node = _Atom(c, space)
            elif c == "/" and self.peek(1) in ("*", "/"):
                node = _Atom(self.comment(), space)
            else:
                text = []
                while self.i < len(self.t):
                    ch = self.t[self.i]
                    if ch.isspace() or ch in "<>()[]{},":
                        break
                    if ch == "/" and self.peek(1) in ("*", "/"):
                        break
                    if ch in '"`':
                        text.append(self.quoted(ch))
                        continue
                    text.append(ch)
                    self.i += 1
                node = _Atom("".join(text), space)
            space = False
            items[-1].append(node)
        if len(items) == 1 and not items[0]:
            items.clear()
        elif items and not items[-1]:
            items.pop()
        return items


def _parse(text: str) -> List[_Node]:
    return [n for item in _Parser(text).items(None) for n in item]


def _gap(prev: _Node, nxt: _Node) -> bool:
    return _is_header(prev) or nxt.space_before or _is_meta(prev) or _is_meta(nxt)


class _Writer:
    def __init__(self, width: int, tight: bool):
        self.out: List[str] = []
        self.col = 0
        self.width = width
        self.tight = tight
        self.header = 0

    # flat rendering -----------------------------------------------------
    def flat_seq(self, seq: List[_Node]) -> str:
        out = []
        for i, n in enumerate(seq):
            if i > 0:
                p = seq[i - 1]
                space = (
                    (_is_meta(p) or _is_meta(n) or _is_header(p))
                    if self.tight
                    else _gap(p, n)
                )
                if space:
                    out.append(" ")
            out.append(self.flat(n))
        return "".join(out)

    def flat(self, n: _Node) -> str:
        if isinstance(n, _Atom):
            return n.text
        sep = "," if self.tight else ", "
        return n.open + sep.join(self.flat_seq(s) for s in n.items) + n.close

    # writing ------------------------------------------------------------
    def push(self, s: str) -> None:
        k = s.rfind("\n")
        self.col = len(s) - k - 1 if k >= 0 else self.col + len(s)
        self.out.append(s)

    def newline(self, indent: int) -> None:
        self.out.append("\n" + " " * indent)
        self.col = indent

    def fits(self, s: str, extra: int) -> bool:
        return self.col + len(s) + extra <= self.width

    def seq(self, seq: List[_Node], indent: int, extra: int) -> None:
        whole = self.flat_seq(seq)
        if self.fits(whole, extra):
            self.push(whole)
            return
        for i, n in enumerate(seq):
            if i > 0 and _gap(seq[i - 1], n):
                self.push(" ")
            self.node(n, indent, extra if i + 1 == len(seq) else 0)

    def node(self, n: _Node, indent: int, extra: int) -> None:
        text = self.flat(n)
        if self.fits(text, extra) or isinstance(n, _Atom):
            self.push(text)
            return
        h = 1 if n.open == "<" else 0
        self.header += h
        self.group(n.open, n.close, n.items, indent, extra)
        self.header -= h

    def group(self, open_: str, close: str, items, indent: int, extra: int) -> None:
        if len(items) == 1:
            self.push(open_)
            self.seq(items[0], indent, extra + 1)
            self.push(close)
            return
        values_only = all(isinstance(n, _Atom) for it in items for n in it)
        col0 = self.col + 1
        each_fits = all(col0 + len(self.flat_seq(it)) < self.width for it in items)
        fill = (
            self.header == 0
            and each_fits
            and (open_ in "({" or (open_ == "[" and values_only))
        )
        self.push(open_)
        if fill:
            for i, item in enumerate(items):
                last = i + 1 == len(items)
                tail = extra + 1 if last else 1
                if i > 0:
                    if self.fits(" " + self.flat_seq(item), tail):
                        self.push(" ")
                    else:
                        self.newline(col0)
                self.seq(item, col0, tail)
                if not last:
                    self.push(",")
            self.push(close)
            return
        for i, item in enumerate(items):
            self.newline(indent + 2)
            last = i + 1 == len(items)
            lead = 0
            while lead < len(item) and _is_comment(item[lead]):
                lead += 1
            if 0 < lead < len(item):
                for n in item[:lead]:
                    self.push(self.flat(n))
                    self.newline(indent + 2)
                item = item[lead:]
            self.seq(item, indent + 2, 0 if last else 1)
            if not last:
                self.push(",")
        self.newline(indent)
        self.push(close)


def _layout(nodes: List[_Node], width: int, lines: bool, tight: bool) -> str:
    w = _Writer(max(width, 20), tight)
    for i, n in enumerate(nodes):
        if i > 0:
            prev = nodes[i - 1]
            type_name = isinstance(prev, _Atom) and prev.text.startswith("@")
            own_line = (
                _is_header(prev) or _is_meta(prev) or (_is_header(n) and not type_name)
            )
            if own_line and lines:
                w.newline(0)
            elif (_is_meta(prev) or _is_meta(n)) if tight else _gap(prev, n):
                w.push(" ")
        w.node(n, 0, 0)
    return "".join(w.out)


def pretty(text: str, width: int = 80) -> str:
    """AK-DATA laid out to `width` columns; decodes to the same value."""
    return _layout(_parse(text), width, True, False)


def compact(text: str) -> str:
    """The same AK-DATA on one line without optional spaces (metadata kept)."""
    return _layout(_parse(text), 10**9, False, True)


def _strip(nodes: List[_Node], comments: bool, attributes: bool) -> List[_Node]:
    out: List[_Node] = []
    for n in nodes:
        if isinstance(n, _Atom) and _is_meta(n):
            keep = comments if _is_comment(n) else attributes
            if not keep:
                continue
        if isinstance(n, _Group):
            items = [_strip(it, comments, attributes) for it in n.items]
            n = _Group(n.open, n.close, [it for it in items if it], n.space_before)
        out.append(n)
    return out


def strip_meta(text: str, comments: bool = False, attributes: bool = False) -> str:
    """
    Compact text keeping only the chosen metadata: `comments` keeps
    /* comments */, `attributes` keeps $attributes, #tags and // … // blocks.
    """
    return _layout(_strip(_parse(text), comments, attributes), 10**9, False, True)
