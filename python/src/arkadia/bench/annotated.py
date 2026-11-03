"""
Annotated datasets: the same data with and without metadata.

Each dataset is hand-designed so that some questions can only be answered
with the information carried by its metadata — what a status code means, the
unit of a number, which records are tests — and others need only the data.
The information is written twice: as `/* comments */` in plain words and as
`$attributes` / `#tags`, so the variants can be compared:

    plain       no metadata (what the encoder writes)
    comments    /* comments */ only
    attributes  $attributes, #tags and // … // blocks only
    full        both
    json        JSON (no place for metadata)
    json-notes  JSON with the same facts as a "Notes:" list before it

Every variant decodes to exactly the same JSON (checked by `variants()`).
Used by the metadata benchmark (`arkadia.bench.meta_bench`) and by the
copy-paste metadata examples (`scripts/make_examples.py`).
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import arkadia.data as akd


@dataclass
class Field:
    name: str
    type: str
    attrs: str = ""  # e.g. '$unit="EUR cents"'
    comment: str = ""  # plain words


@dataclass
class Q:
    text: str
    answer: Any
    needs_meta: bool


@dataclass
class Annotated:
    name: str
    title: str
    description: str
    root: str  # name of the list field
    fields: List[Field]
    rows: List[Tuple[Any, ...]]
    doc_attrs: str  # '$source="shop" #snapshot' (written as a // … // block)
    doc_comment: str
    row_attrs: Dict[int, str] = field(default_factory=dict)  # index -> '#test'
    row_comments: Dict[int, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)  # the facts, for json-notes
    questions: List[Q] = field(default_factory=list)
    # One question with a structured answer, for the copy-paste example.
    example_question: str = ""
    example_answer: Tuple[str, List[Tuple[str, str]]] = ("result", [])
    example_expected: Any = None

    @property
    def data(self) -> Dict[str, Any]:
        return {
            self.root: [dict(zip([f.name for f in self.fields], r)) for r in self.rows]
        }

    def text(self, comments: bool = True, attributes: bool = True) -> str:
        """The readable AK-DATA with the chosen kinds of metadata."""
        lines: List[str] = []
        if attributes and self.doc_attrs:
            lines.append(f"// {self.doc_attrs} //")
        if comments and self.doc_comment:
            lines.append(f"/* {self.doc_comment} */")
        lines.append(f"<{self.root}:<[")
        for i, f in enumerate(self.fields):
            parts = [f"  {name(f.name)}:{f.type}"]
            if attributes and f.attrs:
                parts.append(f.attrs)
            if comments and f.comment:
                parts.append(f"/* {f.comment} */")
            lines.append(" ".join(parts) + ("," if i + 1 < len(self.fields) else ""))
        lines.append("]>>")
        lines.append("([")
        for i, row in enumerate(self.rows):
            parts = [
                "  (" + ", ".join(json.dumps(v, ensure_ascii=False) for v in row) + ")"
            ]
            if attributes and i in self.row_attrs:
                parts.append(self.row_attrs[i])
            if comments and i in self.row_comments:
                parts.append(f"/* {self.row_comments[i]} */")
            lines.append(" ".join(parts) + ("," if i + 1 < len(self.rows) else ""))
        lines.append("])")
        return "\n".join(lines)

    def notes_text(self) -> str:
        return "Notes about the data:\n" + "\n".join(f"- {n}" for n in self.notes)


def name(n: str) -> str:
    return n if re.fullmatch(r"[A-Za-z_]\w*", n) else f"`{n}`"


def squeeze(text: str) -> str:
    """One line, no optional whitespace; strings, comments and metadata kept."""
    out: List[str] = []
    i = 0
    pending_space = False

    def word(c: str) -> bool:
        return c.isalnum() or c in '_"`$#.-'

    while i < len(text):
        c = text[i]
        if c.isspace():
            pending_space = True
            i += 1
            continue
        if pending_space and out:
            prev = out[-1][-1]
            # keep a space where tokens would merge or around metadata
            if (
                (word(prev) and word(c))
                or c in "$#/"
                or prev in "/"
                or out[-1].endswith("*/")
            ):
                if prev not in "(<[{,:" and c not in ")>]},:":
                    out.append(" ")
        pending_space = False
        if c in '"`':
            j = i + 1
            while j < len(text) and text[j] != c:
                j += 2 if text[j] == "\\" and c == '"' else 1
            out.append(text[i : j + 1])
            i = j + 1
            continue
        if c == "/" and text[i + 1 : i + 2] == "*":
            j = text.find("*/", i + 2)
            j = len(text) if j < 0 else j + 2
            out.append(text[i:j])
            i = j
            pending_space = True
            continue
        out.append(c)
        i += 1
    return "".join(out)


VARIANTS = ["json", "json-notes", "plain", "comments", "attributes", "full"]
VARIANT_LABELS = {
    "json": "JSON",
    "json-notes": "JSON + notes",
    "plain": "AK-DATA, no metadata",
    "comments": "AK-DATA + /* comments */",
    "attributes": "AK-DATA + $attributes #tags",
    "full": "AK-DATA + comments + attributes",
}


def variants(ds: Annotated, compact: bool = True) -> Dict[str, str]:
    """The data in every variant (AK-DATA compact or readable); all decode equal."""
    data = ds.data
    out = {
        "json": json.dumps(data, ensure_ascii=False, indent=2),
        "json-notes": ds.notes_text()
        + "\n\n"
        + json.dumps(data, ensure_ascii=False, indent=2),
        "plain": akd.encode(data, {"compact": True})
        if compact
        else ds.text(False, False),
        "comments": ds.text(True, False),
        "attributes": ds.text(False, True),
        "full": ds.text(True, True),
    }
    for k in ("comments", "attributes", "full"):
        if compact:
            out[k] = squeeze(out[k])
    for k in ("plain", "comments", "attributes", "full"):
        r = akd.decode(out[k])
        assert not r.errors, (ds.name, k, r.errors[:1])
        assert r.node.dict() == data, (ds.name, k)
    return out


# ---------------------------------------------------------------------------
# The datasets
# ---------------------------------------------------------------------------

R = random.Random(29)
COMPANIES = [
    "Acme",
    "Globex",
    "Initech",
    "Umbrella",
    "Hooli",
    "Stark",
    "Wayne",
    "Tyrell",
    "Soylent",
    "Wonka",
]


def orders() -> Annotated:
    rows, tests = [], {3, 9}
    for i in range(14):
        st = [1, 2, 3, 3, 3, 4][R.randrange(6)]
        rows.append(
            (
                f"A-{1001 + i}",
                COMPANIES[i % 10],
                st,
                R.randrange(9, 400) * 100 + R.choice([0, 50, 99]),
                R.randint(1, 5),
            )
        )
    rows[5] = (rows[5][0], rows[5][1], 4, rows[5][3], rows[5][4])
    real = [r for i, r in enumerate(rows) if i not in tests]
    shipped_eur = round(sum(r[3] for r in real if r[2] == 3) / 100, 2)
    refunded = [r[0] for r in real if r[2] == 4]
    ds = Annotated(
        name="orders",
        title="Shop orders: status codes, cents and test orders",
        description="Order status is a code, amounts are in cents, two orders are tests — only the metadata says so.",
        root="orders",
        fields=[
            Field("id", "string", "$required"),
            Field("cust", "string", "", "customer name"),
            Field(
                "st",
                "number",
                '$enum="1=new,2=paid,3=shipped,4=refunded"',
                "status: 1 new, 2 paid, 3 shipped, 4 refunded",
            ),
            Field(
                "amt",
                "number",
                '$unit="EUR cents"',
                "amount in euro cents (1999 = 19.99 EUR)",
            ),
            Field("items", "number"),
        ],
        rows=rows,
        doc_attrs='$source="shop-eu" $currency="EUR" #snapshot',
        doc_comment="Orders of the EU shop. Amounts are euro cents. Orders marked as tests are not real sales.",
        row_attrs={i: "#test" for i in tests},
        row_comments={i: "test order, not a real sale" for i in tests},
        notes=[
            "st is the order status: 1 = new, 2 = paid, 3 = shipped, 4 = refunded.",
            "amt is the amount in euro cents (1999 = 19.99 EUR).",
            f"Orders {', '.join(rows[i][0] for i in sorted(tests))} are test orders, not real sales.",
        ],
        questions=[
            Q("How many real (non-test) orders were refunded?", len(refunded), True),
            Q(
                "What is the total amount in euros of shipped orders, excluding test orders?",
                shipped_eur,
                True,
            ),
            Q(
                "Which order ids are test orders? List them.",
                [rows[i][0] for i in sorted(tests)],
                True,
            ),
            Q(
                f"What is the amount in euros of order {rows[6][0]}?",
                round(rows[6][3] / 100, 2),
                True,
            ),
            Q("How many orders are listed?", len(rows), False),
            Q(f"What is `cust` of order {rows[7][0]}?", rows[7][1], False),
            Q(f"How many items does order {rows[2][0]} have?", rows[2][4], False),
        ],
        example_question="Which real orders (not tests) were refunded, and how much was each in euros?",
        example_answer=("refunds", [("id", "string"), ("eur", "number")]),
        example_expected=[
            {"id": r[0], "eur": round(r[3] / 100, 2)} for r in real if r[2] == 4
        ],
    )
    return ds


def sensors() -> Annotated:
    rooms = [
        "lab",
        "office",
        "server",
        "hall",
        "kitchen",
        "lab",
        "office",
        "server",
        "store",
        "hall",
    ]
    rows = []
    for i, room in enumerate(rooms):
        rows.append(
            (
                f"S-{i + 1}",
                room,
                R.randint(180, 290),
                R.randint(30, 65),
                f"2026-10-29T{8 + i:02d}:00:00Z",
            )
        )
    calib = {2, 7}
    rows[2] = (
        rows[2][0],
        rows[2][1],
        412,
        rows[2][3],
        rows[2][4],
    )  # broken while calibrating
    ok = [r for i, r in enumerate(rows) if i not in calib]
    hottest = max(ok, key=lambda r: r[2])
    return Annotated(
        name="sensors",
        title="Sensors: tenths of a degree, UTC times, calibrating",
        description="Temperatures are tenths of °C, times are UTC, two sensors are being calibrated and their values are not valid.",
        root="readings",
        fields=[
            Field("sensor", "string", "$required"),
            Field("room", "string"),
            Field(
                "temp",
                "number",
                '$unit="0.1 C"',
                "temperature in tenths of a degree Celsius (215 = 21.5 °C)",
            ),
            Field("hum", "number", '$unit="%"', "relative humidity in percent"),
            Field("at", "string", '$tz="UTC"', "time of the reading, UTC"),
        ],
        rows=rows,
        doc_attrs='$site="Warsaw HQ" $interval="1h" #telemetry',
        doc_comment="Hourly readings from the Warsaw office. Sensors being calibrated report values that must be ignored.",
        row_attrs={i: "#calibrating $valid=false" for i in calib},
        row_comments={i: "being calibrated, value not valid" for i in calib},
        notes=[
            "temp is in tenths of a degree Celsius (215 = 21.5 °C).",
            "hum is relative humidity in percent; at is the time in UTC.",
            f"Sensors {', '.join(rows[i][0] for i in sorted(calib))} are being calibrated; their values are not valid.",
        ],
        questions=[
            Q("What is the highest valid temperature in °C?", hottest[2] / 10, True),
            Q("Which sensor reported the highest valid temperature?", hottest[0], True),
            Q(
                "Which sensors are being calibrated? List them.",
                [rows[i][0] for i in sorted(calib)],
                True,
            ),
            Q(
                f"What is the temperature in °C of sensor {rows[4][0]}?",
                rows[4][2] / 10,
                True,
            ),
            Q("How many readings are there?", len(rows), False),
            Q(f"In which room is sensor {rows[5][0]}?", rows[5][1], False),
            Q(f"What is `hum` of sensor {rows[8][0]}?", rows[8][3], False),
        ],
        example_question="Which room was the warmest, using only valid readings? Give the sensor, the room and the temperature in °C.",
        example_answer=(
            "warmest",
            [("sensor", "string"), ("room", "string"), ("celsius", "number")],
        ),
        example_expected=[
            {"sensor": hottest[0], "room": hottest[1], "celsius": hottest[2] / 10}
        ],
    )


def staff() -> Annotated:
    people = [
        "Ada",
        "Alan",
        "Grace",
        "Linus",
        "Margaret",
        "Dennis",
        "Barbara",
        "Ken",
        "Radia",
        "Edsger",
        "Hedy",
        "Tim",
    ]
    rows = []
    for i, p in enumerate(people):
        rows.append(
            (
                100 + i,
                p,
                ["ENG", "OPS", "FIN"][i % 3],
                R.choice([1, 2, 2, 3, 3]),
                R.randrange(70, 260) * 100,
            )
        )
    contractors = {4, 10}
    seniors = [r for r in rows if r[3] == 3]
    top = max(rows, key=lambda r: r[4])
    return Annotated(
        name="staff",
        title="Staff: levels as codes, monthly salaries, contractors",
        description="Level is a code, salary is monthly in PLN, two people are contractors — written only in the metadata.",
        root="staff",
        fields=[
            Field("id", "number", "$required"),
            Field("name", "string"),
            Field(
                "dept",
                "string",
                '$enum="ENG=engineering,OPS=operations,FIN=finance"',
                "department: ENG engineering, OPS operations, FIN finance",
            ),
            Field(
                "lvl",
                "number",
                '$enum="1=junior,2=mid,3=senior"',
                "level: 1 junior, 2 mid, 3 senior",
            ),
            Field(
                "sal",
                "number",
                '$unit="PLN" $period="month"',
                "gross salary per month in PLN",
            ),
        ],
        rows=rows,
        doc_attrs='$company="Arkadia" $as_of="2026-10-01" #hr #confidential',
        doc_comment="Payroll snapshot from 1 October 2026. Contractors are not employees.",
        row_attrs={i: "#contractor" for i in contractors},
        row_comments={i: "contractor, not an employee" for i in contractors},
        notes=[
            "dept: ENG = engineering, OPS = operations, FIN = finance.",
            "lvl is the level: 1 = junior, 2 = mid, 3 = senior.",
            "sal is the gross salary per month in PLN.",
            f"{', '.join(rows[i][1] for i in sorted(contractors))} are contractors, not employees.",
        ],
        questions=[
            Q("How many people are senior?", len(seniors), True),
            Q(f"What is the yearly salary in PLN of {top[1]}?", top[4] * 12, True),
            Q(
                "Who are the contractors? List their names.",
                [rows[i][1] for i in sorted(contractors)],
                True,
            ),
            Q(
                f"In which department (full name) does {rows[3][1]} work?",
                {"ENG": "engineering", "OPS": "operations", "FIN": "finance"}[
                    rows[3][2]
                ],
                True,
            ),
            Q("How many people are listed?", len(rows), False),
            Q(f"What is `dept` of {rows[6][1]}?", rows[6][2], False),
            Q(f"What is `id` of {rows[9][1]}?", rows[9][0], False),
        ],
        example_question="List the senior people who are employees (not contractors) with their yearly salary in PLN.",
        example_answer=("seniors", [("name", "string"), ("yearly_pln", "number")]),
        example_expected=[
            {"name": r[1], "yearly_pln": r[4] * 12}
            for i, r in enumerate(rows)
            if r[3] == 3 and i not in contractors
        ],
    )


def inventory() -> Annotated:
    names = [
        "cable",
        "mouse",
        "keyboard",
        "dock",
        "headset",
        "monitor",
        "webcam",
        "charger",
        "hub",
        "stand",
        "lamp",
        "mic",
    ]
    rows = []
    for i, n in enumerate(names):
        rows.append((f"SKU-{200 + i}", n, R.randint(0, 40), R.choice([5, 10, 15, 20])))
    discontinued = {1, 8}
    rows[1] = (rows[1][0], rows[1][1], 0, rows[1][3])
    need = [r[0] for i, r in enumerate(rows) if r[2] < r[3] and i not in discontinued]
    return Annotated(
        name="inventory",
        title="Inventory: reorder levels and discontinued items",
        description="min is the reorder level and two items are discontinued (never reordered) — only the metadata explains it.",
        root="items",
        fields=[
            Field("sku", "string", "$required"),
            Field("item", "string"),
            Field("qty", "number", '$unit="pcs"', "pieces in stock"),
            Field(
                "min",
                "number",
                '$role="reorder_level"',
                "reorder level: order more when qty is below it",
            ),
        ],
        rows=rows,
        doc_attrs='$warehouse="WAW-1" $counted="2026-10-28" #stock',
        doc_comment="Stock in warehouse WAW-1. Discontinued items are never reordered.",
        row_attrs={i: "#discontinued" for i in discontinued},
        row_comments={i: "discontinued, do not reorder" for i in discontinued},
        notes=[
            "qty is the number of pieces in stock.",
            "min is the reorder level: order more when qty is below min.",
            f"{', '.join(rows[i][0] for i in sorted(discontinued))} are discontinued and never reordered.",
            "The warehouse is WAW-1.",
        ],
        questions=[
            Q("Which SKUs must be reordered? List them.", need, True),
            Q(
                "Which SKUs are discontinued? List them.",
                [rows[i][0] for i in sorted(discontinued)],
                True,
            ),
            Q("In which warehouse is the stock?", "WAW-1", True),
            Q("How many items are listed?", len(rows), False),
            Q(f"What is `qty` of {rows[4][0]}?", rows[4][2], False),
            Q(f"What is `item` of {rows[10][0]}?", rows[10][1], False),
        ],
        example_question="Which items must be reordered and how many pieces are missing to reach the reorder level?",
        example_answer=("reorder", [("sku", "string"), ("missing", "number")]),
        example_expected=[
            {"sku": r[0], "missing": r[3] - r[2]}
            for i, r in enumerate(rows)
            if r[2] < r[3] and i not in discontinued
        ],
    )


_CACHE: Optional[List[Annotated]] = None


def datasets() -> List[Annotated]:
    """The annotated datasets (deterministic)."""
    global _CACHE, R
    if _CACHE is None:
        R = random.Random(29)
        _CACHE = [orders(), sensors(), staff(), inventory()]
    return _CACHE
