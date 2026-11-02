"""
The copy-paste example catalogue (with `scripts/make_examples.py`).

Every example has data, a question, the answer shape and the expected answer
computed from the data. Most also carry metadata — the same facts written as
`$attributes` / `#tags` and as `/* comments */` — so each prompt can be built
with attributes, with comments, with both or with neither:

    meta = {
        "doc": ('$source="shop" #snapshot', "Orders of the EU shop."),
        "fields": {"orders.st": ('$enum="1=new,2=paid"', "status: 1 new, 2 paid")},
        "records": {"orders": {3: ("#test", "test order, not a real sale")}},
    }

`annotate()` inserts them into the encoder's compact text (header fields by
path, records of a top-level list by index); `layout.strip_meta()` removes
them again, so every variant decodes to the same JSON. For JSON and TOON the
same facts are written as notes before the data (`notes()`).

When an example's question depends on the metadata (`needs_meta`), the
variants without it cannot be answered correctly — which is the point of
comparing them.
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, Tuple

import arkadia.data as akd
from arkadia.data import layout
from arkadia.data.layout import _Atom, _Group, _layout, _parse

Meta = Dict[str, Any]


# ---------------------------------------------------------------------------
# Metadata in AK-DATA text and as notes
# ---------------------------------------------------------------------------


def _field_name(item) -> Optional[str]:
    first = item[0] if item else None
    if not isinstance(first, _Atom) or ":" not in first.text:
        return None
    name = first.text.split(":", 1)[0]
    return name[1:-1] if name.startswith("`") else name


def _record_fields(group: _Group):
    """The field items of a header group: <a:t,…> or <[a:t,…]>."""
    if len(group.items) == 1 and len(group.items[0]) == 1:
        inner = group.items[0][0]
        if isinstance(inner, _Group) and inner.open == "[":
            return inner.items, True
    return group.items, False


def _meta_atoms(attrs: str, comment: str, comments: bool, attributes: bool):
    out = []
    if attributes and attrs:
        out += [_Atom(a, True) for a in attrs.split(" ") if a]
    if comments and comment:
        out.append(_Atom(f"/* {comment} */", True))
    return out


def _annotate_header(
    group: _Group, prefix: str, fields: Dict[str, Tuple[str, str]], c: bool, a: bool
):
    items, _ = _record_fields(group)
    for item in items:
        name = _field_name(item)
        if name is None:
            continue
        path = f"{prefix}{name}"
        if path in fields:
            item.extend(_meta_atoms(*fields[path], c, a))
        for n in item[1:]:
            if isinstance(n, _Group) and n.open == "<":
                _annotate_header(n, f"{path}.", fields, c, a)


def header_paths(data: Any) -> List[str]:
    """Every field path of the header the encoder writes for `data`."""
    nodes = _parse(akd.encode(data, {"compact": True}))
    out: List[str] = []

    def walk(group: _Group, prefix: str) -> None:
        items, _ = _record_fields(group)
        for item in items:
            name = _field_name(item)
            if name is None:
                continue
            out.append(prefix + name)
            for n in item[1:]:
                if isinstance(n, _Group) and n.open == "<":
                    walk(n, f"{prefix}{name}.")

    if nodes and isinstance(nodes[0], _Group) and nodes[0].open == "<":
        walk(nodes[0], "")
    return out


def annotate(
    data: Any, meta: Meta, comments: bool = True, attributes: bool = True
) -> str:
    """The compact AK-DATA of `data` with the chosen metadata."""
    text = akd.encode(data, {"compact": True})
    nodes = _parse(text)
    if (
        not meta
        or len(nodes) < 2
        or not (isinstance(nodes[0], _Group) and nodes[0].open == "<")
    ):
        return text
    header, value = nodes[0], nodes[1]
    _annotate_header(header, "", meta.get("fields", {}), comments, attributes)
    items, is_list = _record_fields(header)
    for path, rows in meta.get("records", {}).items():
        target = None
        if is_list and path == "":
            target = value
        elif not is_list and isinstance(value, _Group) and value.open == "(":
            names = [_field_name(it) for it in items]
            if path in names:
                seq = value.items[names.index(path)]
                target = (
                    seq[-1]
                    if seq and isinstance(seq[-1], _Group) and seq[-1].open == "["
                    else None
                )
        if target is None:
            raise ValueError(f"no top-level list '{path}' to annotate")
        for idx, (attrs, comment) in rows.items():
            target.items[idx].extend(_meta_atoms(attrs, comment, comments, attributes))
    doc_attrs, doc_comment = meta.get("doc", ("", ""))
    head = []
    if attributes and doc_attrs:
        head.append(_Atom(f"// {doc_attrs} //", False))
    if comments and doc_comment:
        head.append(_Atom(f"/* {doc_comment} */", True))
    return _layout(head + nodes, 10**9, False, True)


def _record_label(data: Any, path: str, idx: int) -> str:
    rows = data if path == "" else data[path]
    row = rows[idx]
    key = next(iter(row))
    return f"{path or 'item'} {key}={json.dumps(row[key], ensure_ascii=False)}"


def notes(data: Any, meta: Meta) -> Dict[str, List[str]]:
    """The metadata as notes for formats without comments (JSON, TOON)."""
    if not meta:
        return {"comments": [], "attributes": []}
    com: List[str] = []
    att: List[str] = []
    doc_attrs, doc_comment = meta.get("doc", ("", ""))
    if doc_comment:
        com.append(doc_comment)
    if doc_attrs:
        att.append(f"document: {doc_attrs}")
    for path, (attrs, comment) in meta.get("fields", {}).items():
        if comment:
            com.append(f"`{path}`: {comment}")
        if attrs:
            att.append(f"`{path}`: {attrs}")
    for path, rows in meta.get("records", {}).items():
        for idx, (attrs, comment) in rows.items():
            label = _record_label(data, path, idx)
            if comment:
                com.append(f"{label}: {comment}")
            if attrs:
                att.append(f"{label}: {attrs}")
    return {"comments": com, "attributes": att}


def notes_block(n: Dict[str, List[str]], comments: bool, attributes: bool) -> str:
    parts = []
    if comments and n["comments"]:
        parts.append(
            "Notes about the data:\n" + "\n".join(f"- {x}" for x in n["comments"])
        )
    if attributes and n["attributes"]:
        parts.append(
            "Attributes of the data:\n" + "\n".join(f"- {x}" for x in n["attributes"])
        )
    return "\n\n".join(parts)


def variant_text(akd_meta: str, comments: bool, attributes: bool) -> str:
    """Compact AK-DATA with the chosen metadata, from the fully annotated text."""
    if comments and attributes:
        return layout.compact(akd_meta)
    return layout.strip_meta(akd_meta, comments, attributes)


def notes_from_text(akd_text: str) -> Dict[str, List[str]]:
    """Comments and attributes written in hand-made AK-DATA, as notes."""
    comments: List[str] = []
    attributes: List[str] = []

    def walk(nodes):
        for n in nodes:
            if isinstance(n, layout._Group):
                for item in n.items:
                    walk(item)
            elif layout._is_comment(n):
                comments.append(n.text[2:-2].strip())
            elif layout._is_meta(n):
                text = n.text.strip("/ ").strip() if n.text.startswith("//") else n.text
                if text:
                    attributes.append(text)

    walk(layout._parse(akd_text))
    return {"comments": comments, "attributes": attributes}


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------


def ex(
    slug,
    title,
    description,
    data,
    question,
    answer,
    expected,
    meta=None,
    needs_meta=False,
    note="",
):
    return dict(
        slug=slug,
        title=title,
        description=description,
        question=question,
        answer={"name": answer[0], "fields": [list(f) for f in answer[1]]},
        expected=expected,
        expected_note=note,
        data=data,
        meta=meta or {},
        needs_meta=needs_meta,
    )


def rnd(slug: str) -> random.Random:
    return random.Random(f"akd-examples:{slug}")


NAMES = [
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
    "Katherine",
    "John",
    "Frances",
    "Donald",
]
CITIES = [
    "Warsaw",
    "Kraków",
    "Gdańsk",
    "Wrocław",
    "Poznań",
    "Berlin",
    "Lisbon",
    "Prague",
]
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
    "Cyberdyne",
    "Vandelay",
]


def invoices():
    r = rnd("invoices")
    rows = []
    for i in range(14):
        rows.append(
            {
                "no": f"FV/{i + 1:03d}/2026",
                "client": COMPANIES[i % 12],
                "gross": r.randrange(200, 9000) * 100 + r.choice([0, 50]),
                "due": f"2026-10-{r.randint(1, 28):02d}",
                "st": r.choice([0, 1, 1, 2]),
            }
        )
    today = "2026-10-20"
    exp = [
        {"no": x["no"], "pln": x["gross"] / 100}
        for x in rows
        if x["st"] == 0 and x["due"] < today
    ]
    return ex(
        "invoices-overdue",
        "Invoices: overdue and unpaid",
        "Amounts in grosze and status codes 0/1/2 — explained only in the metadata.",
        {"invoices": rows},
        f"Which invoices are unpaid and overdue on {today}? Give the number and the gross amount in PLN.",
        ("overdue", [("no", "string"), ("pln", "number")]),
        exp,
        meta={
            "doc": (
                '$currency="PLN" $as_of="2026-10-20" #ledger',
                "Sales invoices. Amounts are in grosze (1/100 PLN).",
            ),
            "fields": {
                "invoices.gross": (
                    '$unit="grosze"',
                    "gross amount in grosze (12350 = 123.50 PLN)",
                ),
                "invoices.st": (
                    '$enum="0=unpaid,1=paid,2=cancelled"',
                    "status: 0 unpaid, 1 paid, 2 cancelled",
                ),
                "invoices.due": ('$format="YYYY-MM-DD"', "payment due date"),
            },
        },
        needs_meta=True,
    )


def flights():
    r = rnd("flights")
    codes = ["LO", "LH", "FR", "W6", "KL"]
    rows = []
    for i in range(16):
        rows.append(
            {
                "flight": f"{r.choice(codes)}{r.randint(100, 999)}",
                "to": r.choice(["FRA", "AMS", "LHR", "CDG", "OSL", "VIE"]),
                "sched": f"{6 + i}:{r.choice(['00', '15', '30', '45'])}",
                "delay": r.choice([0, 0, 5, 12, 25, 40, 75, 130]),
            }
        )
    exp = [
        {"flight": x["flight"], "delay": x["delay"]}
        for x in sorted(rows, key=lambda x: -x["delay"])
        if x["delay"] > 30
    ]
    return ex(
        "flights-delays",
        "Departures: delayed flights",
        "Delay is in minutes and times are UTC.",
        {"departures": rows},
        "Which flights are delayed by more than 30 minutes? Longest delay first.",
        ("delayed", [("flight", "string"), ("delay", "number")]),
        exp,
        meta={
            "doc": (
                '$airport="WAW" $date="2026-10-30" #live',
                "Departures board of Warsaw Chopin airport.",
            ),
            "fields": {
                "departures.sched": ('$tz="UTC"', "scheduled departure, UTC"),
                "departures.delay": ('$unit="min"', "delay in minutes"),
            },
        },
    )


def grades():
    r = rnd("grades")
    rows = []
    for i, n in enumerate(NAMES[:14]):
        rows.append(
            {
                "student": n,
                "class": "3A" if i % 2 == 0 else "3B",
                "math": r.choice([2, 3, 3, 4, 4, 5, 6]),
                "pl": r.choice([3, 4, 4, 5, 5, 6]),
                "eng": r.choice([2, 3, 4, 5, 6]),
            }
        )
    exp = []
    for c in ("3A", "3B"):
        g = [x for x in rows if x["class"] == c]
        exp.append(
            {"class": c, "avg_math": round(sum(x["math"] for x in g) / len(g), 2)}
        )
    return ex(
        "grades-classes",
        "School grades: average per class",
        "Polish 1–6 grade scale (6 is the best) — said in the metadata.",
        {"students": rows},
        "What is the average math grade in each class, rounded to 2 decimals?",
        ("classes", [("class", "string"), ("avg_math", "number")]),
        exp,
        meta={
            "doc": (
                '$term="2026/27-1" #school',
                "Grades on the Polish scale: 1 (fail) to 6 (excellent).",
            ),
            "fields": {
                "students.math": ('$scale="1-6"', "mathematics"),
                "students.pl": ('$scale="1-6"', "Polish language"),
                "students.eng": ('$scale="1-6"', "English"),
            },
        },
    )


def crypto():
    r = rnd("crypto")
    coins = ["BTC", "ETH", "SOL", "ADA", "DOT", "XRP", "LTC", "AVAX", "LINK", "ATOM"]
    rows = [
        {
            "sym": s,
            "price": round(r.uniform(0.3, 60000), 2),
            "chg": r.randint(-1200, 1500),
        }
        for s in coins
    ]
    top = sorted(rows, key=lambda x: -x["chg"])[:3]
    exp = [{"sym": x["sym"], "change_pct": x["chg"] / 100} for x in top]
    return ex(
        "crypto-movers",
        "Crypto prices: top movers",
        "24h change is in basis points (1/100 of a percent) — only the metadata says so.",
        {"coins": rows},
        "Which 3 coins rose the most in 24 hours? Give the change in percent.",
        ("movers", [("sym", "string"), ("change_pct", "number")]),
        exp,
        meta={
            "doc": (
                '$quote="USD" $window="24h"',
                "Prices in USD, change over the last 24 hours.",
            ),
            "fields": {
                "coins.price": ('$unit="USD"', "price in US dollars"),
                "coins.chg": (
                    '$unit="bp"',
                    "24h change in basis points (125 = +1.25 %)",
                ),
            },
        },
        needs_meta=True,
    )


def forecast():
    r = rnd("forecast")
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    rows = [
        {
            "day": d,
            "hi": r.randint(38, 62),
            "lo": r.randint(28, 45),
            "rain": r.choice([0, 10, 30, 60, 90]),
        }
        for d in days
    ]
    exp = [
        {"day": x["day"], "hi_c": round((x["hi"] - 32) * 5 / 9, 1)}
        for x in rows
        if (x["hi"] - 32) * 5 / 9 < 10
    ]
    return ex(
        "forecast-fahrenheit",
        "Weather: Fahrenheit forecast",
        "Temperatures are in °F; the question asks about °C.",
        {"forecast": rows},
        "On which days will the high stay below 10 °C? Give the high in °C, rounded to 1 decimal.",
        ("cold", [("day", "string"), ("hi_c", "number")]),
        exp,
        meta={
            "doc": ('$city="Chicago" $source="nws"', "7-day forecast for Chicago."),
            "fields": {
                "forecast.hi": ('$unit="F"', "daily high in degrees Fahrenheit"),
                "forecast.lo": ('$unit="F"', "daily low in degrees Fahrenheit"),
                "forecast.rain": ('$unit="%"', "chance of rain in percent"),
            },
        },
        needs_meta=True,
    )


def bank():
    r = rnd("bank")
    cats = ["food", "rent", "transport", "salary", "fun", "food", "transport"]
    rows = []
    for i in range(18):
        c = r.choice(cats)
        amt = (
            r.randint(1500, 9000) * 100
            if c == "salary"
            else -r.randint(5, 600) * 100 - r.choice([0, 49, 99])
        )
        rows.append({"date": f"2026-10-{i + 1:02d}", "cat": c, "amt": amt})
    spend: Dict[str, int] = {}
    for x in rows:
        if x["amt"] < 0:
            spend[x["cat"]] = spend.get(x["cat"], 0) - x["amt"]
    exp = [
        {"cat": k, "spent": v / 100}
        for k, v in sorted(spend.items(), key=lambda kv: -kv[1])
    ]
    return ex(
        "bank-spending",
        "Bank account: spending per category",
        "Negative amounts are spending, in cents.",
        {"transactions": rows},
        "How much was spent in each category (money going out), in PLN? Most first.",
        ("spending", [("cat", "string"), ("spent", "number")]),
        exp,
        meta={
            "doc": (
                '$account="PL61…0001" $currency="PLN" #statement',
                "October statement of a personal account.",
            ),
            "fields": {
                "transactions.amt": (
                    '$unit="grosze" $sign="negative=debit"',
                    "amount in grosze; negative means money going out",
                )
            },
        },
        needs_meta=True,
    )


def servers():
    r = rnd("servers")
    rows = [
        {
            "host": f"web-{i + 1:02d}",
            "dc": r.choice(["waw", "fra", "ams"]),
            "cpu": r.randint(80, 990),
            "mem": r.randint(200, 980),
        }
        for i in range(14)
    ]
    exp = [
        {"host": x["host"], "cpu_pct": x["cpu"] / 10}
        for x in sorted(rows, key=lambda x: -x["cpu"])
        if x["cpu"] > 800
    ]
    return ex(
        "servers-cpu",
        "Servers: CPU above 80 %",
        "Load is in per mille (‰), not percent.",
        {"hosts": rows},
        "Which hosts use more than 80 % CPU? Give the CPU in percent, highest first.",
        ("hot", [("host", "string"), ("cpu_pct", "number")]),
        exp,
        meta={
            "doc": (
                '$cluster="prod-eu" $sampled="5m"',
                "Average load over the last 5 minutes.",
            ),
            "fields": {
                "hosts.cpu": (
                    '$unit="permille"',
                    "CPU usage in per mille (850 = 85 %)",
                ),
                "hosts.mem": ('$unit="permille"', "memory usage in per mille"),
            },
        },
        needs_meta=True,
    )


def vitals():
    r = rnd("vitals")
    pages = [
        "/",
        "/pricing",
        "/docs",
        "/blog",
        "/login",
        "/signup",
        "/akdata",
        "/contact",
        "/about",
        "/careers",
    ]
    rows = [
        {
            "page": p,
            "lcp": r.randint(900, 4200),
            "cls": round(r.uniform(0, 0.3), 3),
            "inp": r.randint(40, 450),
        }
        for p in pages
    ]
    exp = [
        {"page": x["page"], "lcp": x["lcp"]}
        for x in sorted(rows, key=lambda x: -x["lcp"])
        if x["lcp"] > 2500
    ]
    return ex(
        "web-vitals",
        "Web vitals: slow pages",
        "Largest Contentful Paint in milliseconds, budget 2.5 s.",
        {"pages": rows},
        "Which pages have an LCP worse than 2500 ms? Slowest first.",
        ("slow", [("page", "string"), ("lcp", "number")]),
        exp,
        meta={
            "doc": (
                '$site="arkadia.solutions" $percentile=75',
                "Core Web Vitals, 75th percentile, last 28 days.",
            ),
            "fields": {
                "pages.lcp": (
                    '$unit="ms" $budget=2500',
                    "Largest Contentful Paint in ms; good below 2500",
                ),
                "pages.inp": ('$unit="ms"', "Interaction to Next Paint in ms"),
            },
        },
    )


def leads():
    r = rnd("leads")
    rows = [
        {
            "lead": f"L-{300 + i}",
            "company": COMPANIES[i % 12],
            "score": r.randint(10, 99),
            "stage": r.choice([1, 2, 2, 3, 3, 4]),
            "owner": r.choice(NAMES[:5]),
        }
        for i in range(15)
    ]
    exp = [
        {"lead": x["lead"], "company": x["company"]}
        for x in sorted(rows, key=lambda x: -x["score"])
        if x["stage"] == 3
    ]
    return ex(
        "crm-leads",
        "CRM: leads in the proposal stage",
        "Stage is a code 1–4.",
        {"leads": rows},
        "Which leads are in the proposal stage? Highest score first.",
        ("proposal", [("lead", "string"), ("company", "string")]),
        exp,
        meta={
            "fields": {
                "leads.stage": (
                    '$enum="1=new,2=qualified,3=proposal,4=won"',
                    "pipeline stage: 1 new, 2 qualified, 3 proposal, 4 won",
                ),
                "leads.score": ('$range="0-100"', "lead score, higher is better"),
            }
        },
        needs_meta=True,
    )


def shipments():
    r = rnd("shipments")
    rows = [
        {
            "id": f"SH-{i + 1:03d}",
            "carrier": r.choice(["DHL", "UPS", "InPost", "DPD"]),
            "w": r.randint(150, 24000),
        }
        for i in range(16)
    ]
    tot: Dict[str, int] = {}
    for x in rows:
        tot[x["carrier"]] = tot.get(x["carrier"], 0) + x["w"]
    exp = [
        {"carrier": k, "kg": round(v / 1000, 3)}
        for k, v in sorted(tot.items(), key=lambda kv: -kv[1])
    ]
    return ex(
        "shipments-weight",
        "Shipments: weight per carrier",
        "Weight is in grams.",
        {"shipments": rows},
        "What is the total weight in kilograms per carrier? Heaviest first.",
        ("weight", [("carrier", "string"), ("kg", "number")]),
        exp,
        meta={"fields": {"shipments.w": ('$unit="g"', "parcel weight in grams")}},
        needs_meta=True,
    )


def recipes():
    data = {
        "recipes": [
            {
                "name": "Pierogi",
                "minutes": 90,
                "ingredients": ["flour", "potatoes", "cheese", "onion"],
            },
            {
                "name": "Pesto pasta",
                "minutes": 20,
                "ingredients": ["pasta", "basil", "pine nuts", "parmesan"],
            },
            {
                "name": "Tomato soup",
                "minutes": 35,
                "ingredients": ["tomatoes", "onion", "cream"],
            },
            {
                "name": "Granola",
                "minutes": 40,
                "ingredients": ["oats", "honey", "almonds", "walnuts"],
            },
            {
                "name": "Omelette",
                "minutes": 10,
                "ingredients": ["eggs", "butter", "chives"],
            },
            {
                "name": "Satay",
                "minutes": 45,
                "ingredients": ["chicken", "peanuts", "soy sauce", "lime"],
            },
            {
                "name": "Ratatouille",
                "minutes": 60,
                "ingredients": ["eggplant", "zucchini", "tomatoes", "pepper"],
            },
        ]
    }
    nuts = ("nuts", "almonds", "walnuts", "peanuts")
    exp = [
        {"name": x["name"], "minutes": x["minutes"]}
        for x in data["recipes"]
        if not any(any(n in i for n in nuts) for i in x["ingredients"])
        and x["minutes"] <= 45
    ]
    return ex(
        "recipes-nut-free",
        "Recipes: nut-free and quick",
        "Lists inside records.",
        data,
        "Which recipes contain no nuts of any kind and take at most 45 minutes?",
        ("recipes", [("name", "string"), ("minutes", "number")]),
        exp,
        meta={
            "fields": {"recipes.minutes": ('$unit="min"', "total time in minutes")},
            "records": {"recipes": {3: ("#breakfast", ""), 4: ("#breakfast", "")}},
        },
    )


def movies():
    r = rnd("movies")
    titles = [
        "Solaris",
        "Stalker",
        "Ida",
        "Cold War",
        "Decalogue",
        "Blind Chance",
        "The Pianist",
        "Knife in the Water",
        "Ashes and Diamonds",
        "Man of Marble",
        "Corpus Christi",
        "EO",
    ]
    rows = [
        {
            "title": t,
            "year": r.randint(1958, 2022),
            "rating": round(r.uniform(6.2, 8.9), 1),
            "genres": r.sample(["drama", "war", "sci-fi", "thriller", "history"], 2),
        }
        for t in titles
    ]
    best = max((x for x in rows if "drama" in x["genres"]), key=lambda x: x["rating"])
    return ex(
        "movies-best-drama",
        "Films: best-rated drama",
        "Genre lists inside records.",
        {"films": rows},
        "Which film tagged drama has the highest rating? Give the title, year and rating.",
        ("best", [("title", "string"), ("year", "number"), ("rating", "number")]),
        [{k: best[k] for k in ("title", "year", "rating")}],
        meta={
            "fields": {
                "films.rating": (
                    '$scale="1-10" $source="imdb"',
                    "average user rating, 1–10",
                )
            }
        },
    )


def commits():
    r = rnd("commits")
    rows = [
        {
            "sha": f"{r.getrandbits(28):07x}",
            "author": r.choice(NAMES[:6]),
            "files": r.randint(1, 14),
            "msg": r.choice(
                [
                    "fix: decoder",
                    "feat: layout",
                    "docs: readme",
                    "test: fuzz",
                    "refactor: parser",
                    "chore: deps",
                ]
            ),
        }
        for _ in range(20)
    ]
    cnt: Dict[str, int] = {}
    for x in rows:
        cnt[x["author"]] = cnt.get(x["author"], 0) + 1
    top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    exp = [{"author": a, "commits": n} for a, n in top]
    return ex(
        "git-commits",
        "Git log: most active authors",
        "Twenty commits.",
        {"commits": rows},
        "Which 3 authors made the most commits? Ties alphabetically.",
        ("authors", [("author", "string"), ("commits", "number")]),
        exp,
        meta={
            "doc": ('$repo="arkadia-data" $branch="main"', "Last 20 commits on main.")
        },
    )


def hotel():
    r = rnd("hotel")
    rows = [
        {
            "booking": f"B{700 + i}",
            "room": r.choice(["single", "double", "suite"]),
            "nights": r.randint(1, 6),
            "rate": r.choice([240, 320, 390, 650, 880]),
        }
        for i in range(14)
    ]
    rev: Dict[str, int] = {}
    for x in rows:
        rev[x["room"]] = rev.get(x["room"], 0) + x["nights"] * x["rate"]
    exp = [
        {"room": k, "revenue": v} for k, v in sorted(rev.items(), key=lambda kv: -kv[1])
    ]
    return ex(
        "hotel-revenue",
        "Hotel: revenue per room type",
        "Nights × nightly rate.",
        {"bookings": rows},
        "What is the revenue (nights × rate) per room type? Highest first.",
        ("revenue", [("room", "string"), ("revenue", "number")]),
        exp,
        meta={
            "fields": {
                "bookings.rate": ('$unit="PLN" $per="night"', "price per night in PLN")
            }
        },
    )


def leave():
    r = rnd("leave")
    rows = [
        {
            "req": f"LV-{50 + i}",
            "who": r.choice(NAMES[:6]),
            "days": r.randint(1, 10),
            "st": r.choice(["A", "P", "R", "A"]),
        }
        for i in range(15)
    ]
    tot: Dict[str, int] = {}
    for x in rows:
        if x["st"] == "A":
            tot[x["who"]] = tot.get(x["who"], 0) + x["days"]
    exp = [
        {"who": k, "days": v}
        for k, v in sorted(tot.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return ex(
        "hr-leave",
        "HR: approved leave per person",
        "Status is a one-letter code.",
        {"requests": rows},
        "How many days of approved leave does each person have? Most first.",
        ("approved", [("who", "string"), ("days", "number")]),
        exp,
        meta={
            "fields": {
                "requests.st": (
                    '$enum="A=approved,P=pending,R=rejected"',
                    "status: A approved, P pending, R rejected",
                ),
                "requests.days": ('$unit="working days"', "working days"),
            }
        },
        needs_meta=True,
    )


def batteries():
    r = rnd("batteries")
    rows = [
        {
            "device": f"TAG-{i + 1:02d}",
            "zone": r.choice(["dock", "hall", "yard"]),
            "batt": r.randint(2900, 4150),
            "rssi": -r.randint(40, 95),
        }
        for i in range(14)
    ]
    exp = [
        {"device": x["device"], "volts": x["batt"] / 1000}
        for x in sorted(rows, key=lambda x: x["batt"])
        if x["batt"] < 3300
    ]
    return ex(
        "iot-batteries",
        "IoT tags: low battery",
        "Battery is in millivolts.",
        {"tags": rows},
        "Which devices have a battery below 3.3 V? Give the voltage in volts, lowest first.",
        ("low", [("device", "string"), ("volts", "number")]),
        exp,
        meta={
            "fields": {
                "tags.batt": ('$unit="mV"', "battery voltage in millivolts"),
                "tags.rssi": ('$unit="dBm"', "signal strength in dBm"),
            }
        },
        needs_meta=True,
    )


def latency():
    r = rnd("latency")
    eps = [
        "GET /orders",
        "POST /orders",
        "GET /users/:id",
        "GET /search",
        "POST /login",
        "GET /health",
        "PUT /cart",
        "GET /products",
        "POST /pay",
        "GET /reports",
    ]
    rows = [
        {"endpoint": e, "p95": r.randint(9000, 640000), "rpm": r.randint(10, 9000)}
        for e in eps
    ]
    exp = [
        {"endpoint": x["endpoint"], "p95_ms": round(x["p95"] / 1000, 1)}
        for x in sorted(rows, key=lambda x: -x["p95"])
        if x["p95"] > 200000
    ]
    return ex(
        "api-latency",
        "API: slow endpoints",
        "p95 latency in microseconds.",
        {"endpoints": rows},
        "Which endpoints have a p95 latency above 200 ms? Give it in ms (1 decimal), slowest first.",
        ("slow", [("endpoint", "string"), ("p95_ms", "number")]),
        exp,
        meta={
            "fields": {
                "endpoints.p95": (
                    '$unit="us" $percentile=95',
                    "95th percentile latency in microseconds",
                ),
                "endpoints.rpm": ('$unit="req/min"', "requests per minute"),
            }
        },
        needs_meta=True,
    )


def menu():
    rows = [
        {"dish": "Hummus plate", "price": 2400, "tags": ["vegan", "gluten-free"]},
        {"dish": "Pierogi ruskie", "price": 3200, "tags": ["vegetarian"]},
        {"dish": "Falafel wrap", "price": 1900, "tags": ["vegan"]},
        {"dish": "Beef burger", "price": 4200, "tags": []},
        {"dish": "Lentil soup", "price": 1600, "tags": ["vegan", "gluten-free"]},
        {"dish": "Caesar salad", "price": 2900, "tags": []},
        {"dish": "Tofu curry", "price": 3100, "tags": ["vegan"]},
        {"dish": "Fries", "price": 1200, "tags": ["vegan"]},
    ]
    exp = [
        {"dish": x["dish"], "pln": x["price"] / 100}
        for x in rows
        if "vegan" in x["tags"] and x["price"] < 2500
    ]
    return ex(
        "menu-vegan",
        "Menu: vegan dishes under 25 PLN",
        "Prices are in grosze.",
        {"menu": rows},
        "Which vegan dishes cost less than 25 PLN? Give the price in PLN.",
        ("vegan", [("dish", "string"), ("pln", "number")]),
        exp,
        meta={
            "doc": ('$restaurant="Bistro 42" $valid_from="2026-10-01"', "Autumn menu."),
            "fields": {
                "menu.price": ('$unit="grosze"', "price in grosze (1990 = 19.90 PLN)")
            },
        },
        needs_meta=True,
    )


def library():
    r = rnd("library")
    titles = [
        "Solaris",
        "Quo Vadis",
        "The Doll",
        "Ferdydurke",
        "Pan Tadeusz",
        "The Witcher",
        "Flights",
        "Drive Your Plow",
        "The Peasants",
        "Faraon",
    ]
    rows = [
        {
            "book": t,
            "reader": r.choice(NAMES[:7]),
            "due": f"2026-{r.choice(['09', '10', '11'])}-{r.randint(1, 28):02d}",
        }
        for t in titles
    ]
    today = "2026-10-15"
    exp = [
        {"book": x["book"], "reader": x["reader"]}
        for x in sorted(rows, key=lambda x: x["due"])
        if x["due"] < today
    ]
    return ex(
        "library-overdue",
        "Library: overdue loans",
        "Dates as text.",
        {"loans": rows},
        f"Which loans are overdue on {today}? Oldest due date first.",
        ("overdue", [("book", "string"), ("reader", "string")]),
        exp,
    )


def fleet():
    r = rnd("fleet")
    rows = [
        {
            "car": f"WX {r.randint(1000, 9999)}",
            "model": r.choice(["Octavia", "Corolla", "Model 3", "Golf"]),
            "km": r.randint(20000, 160000),
            "last_service_km": 0,
        }
        for _ in range(12)
    ]
    for x in rows:
        x["last_service_km"] = x["km"] - r.randint(2000, 24000)
    exp = [
        {"car": x["car"], "since": x["km"] - x["last_service_km"]}
        for x in sorted(rows, key=lambda x: -(x["km"] - x["last_service_km"]))
        if x["km"] - x["last_service_km"] > 15000
    ]
    return ex(
        "fleet-service",
        "Company cars: service due",
        "Odometer and last service.",
        {"cars": rows},
        "Which cars have driven more than 15,000 km since the last service? Most first; give the distance.",
        ("due", [("car", "string"), ("since", "number")]),
        exp,
        meta={
            "fields": {
                "cars.km": ('$unit="km"', "odometer"),
                "cars.last_service_km": ('$unit="km"', "odometer at the last service"),
            }
        },
    )


def cart():
    items = [
        {"sku": "KB-01", "qty": 2, "price": 8900, "disc": 1000},
        {"sku": "MS-02", "qty": 1, "price": 3950, "disc": 0},
        {"sku": "HD-10", "qty": 1, "price": 12990, "disc": 2500},
        {"sku": "CB-03", "qty": 3, "price": 990, "disc": 0},
    ]
    total = sum(round(i["qty"] * i["price"] * (1 - i["disc"] / 10000)) for i in items)
    data = {"cart": {"customer": "Ada", "currency": "PLN", "items": items}}
    return ex(
        "cart-total",
        "Shopping cart: total after discounts",
        "Prices in grosze, discounts in basis points.",
        data,
        "What is the cart total in PLN after the per-item discounts?",
        ("total", [("pln", "number")]),
        [{"pln": total / 100}],
        meta={
            "fields": {
                "cart.items.price": ('$unit="grosze"', "unit price in grosze"),
                "cart.items.disc": (
                    '$unit="bp"',
                    "discount in basis points (1000 = 10 %)",
                ),
            }
        },
        needs_meta=True,
    )


def survey():
    r = rnd("survey")
    qs = [
        "The app is easy to use",
        "Support answers quickly",
        "Prices are fair",
        "I would recommend it",
        "Docs are clear",
    ]
    rows = [
        {"q": q, "answers": [r.choice([1, 2, 3, 4, 5, 4, 5]) for _ in range(12)]}
        for q in qs
    ]
    exp = [
        {
            "q": x["q"],
            "agree_pct": round(
                sum(1 for a in x["answers"] if a >= 4) / len(x["answers"]) * 100
            ),
        }
        for x in rows
    ]
    return ex(
        "survey-agree",
        "Survey: share of agreement",
        "Likert answers 1–5 as numbers.",
        {"questions": rows},
        "For each statement, what percent of answers agree (agree or strongly agree)? Round to whole percent.",
        ("agree", [("q", "string"), ("agree_pct", "number")]),
        exp,
        meta={
            "fields": {
                "questions.answers": (
                    '$enum="1=strongly disagree,2=disagree,3=neutral,4=agree,5=strongly agree"',
                    "Likert scale: 1 strongly disagree … 5 strongly agree",
                )
            }
        },
        needs_meta=True,
    )


def football():
    r = rnd("football")
    teams = ["Lech", "Legia", "Raków", "Pogoń", "Jagiellonia", "Górnik"]
    rows = []
    for i in range(12):
        h, a = r.sample(teams, 2)
        rows.append({"home": h, "away": a, "score": [r.randint(0, 4), r.randint(0, 3)]})
    goals: Dict[str, int] = {}
    for m in rows:
        goals[m["home"]] = goals.get(m["home"], 0) + m["score"][0]
        goals[m["away"]] = goals.get(m["away"], 0) + m["score"][1]
    best = sorted(goals.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return ex(
        "football-goals",
        "Football: most goals scored",
        "Score as [home, away].",
        {"matches": rows},
        "Which team scored the most goals in these matches, and how many?",
        ("top", [("team", "string"), ("goals", "number")]),
        [{"team": best[0], "goals": best[1]}],
        meta={"fields": {"matches.score": ("", "goals as [home, away]")}},
    )


def energy():
    r = rnd("energy")
    rows = [
        {"day": f"2026-10-{d:02d}", "hour": h, "wh": r.randint(150, 2200)}
        for d in (27, 28)
        for h in range(0, 24, 3)
    ]
    tot: Dict[str, int] = {}
    for x in rows:
        tot[x["day"]] = tot.get(x["day"], 0) + x["wh"]
    exp = [{"day": k, "kwh": round(v / 1000, 2)} for k, v in sorted(tot.items())]
    return ex(
        "energy-kwh",
        "Energy meter: kWh per day",
        "Readings in watt-hours.",
        {"readings": rows},
        "What is the total energy per day in kWh (2 decimals)?",
        ("daily", [("day", "string"), ("kwh", "number")]),
        exp,
        meta={
            "doc": ('$meter="PL-WAW-77" #smart_meter', "3-hourly energy readings."),
            "fields": {
                "readings.wh": (
                    '$unit="Wh"',
                    "energy in watt-hours over the 3-hour slot",
                )
            },
        },
        needs_meta=True,
    )


def jobs():
    r = rnd("jobs")
    roles = [
        "Rust engineer",
        "Data analyst",
        "Product designer",
        "Python developer",
        "DevOps",
        "QA engineer",
        "Tech writer",
        "ML engineer",
        "Frontend dev",
        "Support lead",
    ]
    rows = [
        {
            "role": x,
            "remote": r.choice([True, False]),
            "min": r.randrange(9, 20) * 1000,
            "max": 0,
            "city": r.choice(CITIES[:5]),
        }
        for x in roles
    ]
    for x in rows:
        x["max"] = x["min"] + r.randrange(3, 10) * 1000
    exp = [
        {"role": x["role"], "max": x["max"]}
        for x in sorted(rows, key=lambda x: -x["max"])
        if x["remote"] and x["max"] >= 20000
    ]
    return ex(
        "jobs-remote",
        "Job board: remote and well paid",
        "Salary ranges per month.",
        {"jobs": rows},
        "Which remote jobs pay at least 20,000 at the top of the range? Highest first.",
        ("jobs", [("role", "string"), ("max", "number")]),
        exp,
        meta={
            "fields": {
                "jobs.min": (
                    '$unit="PLN" $period="month" $gross=true',
                    "monthly gross, PLN",
                ),
                "jobs.max": (
                    '$unit="PLN" $period="month" $gross=true',
                    "monthly gross, PLN",
                ),
            }
        },
    )


def issues():
    r = rnd("issues")
    rows = [
        {
            "n": 100 + i,
            "title": r.choice(
                [
                    "Crash on start",
                    "Typo in docs",
                    "Slow decode",
                    "Add Go port",
                    "Wrong token count",
                    "Header parse error",
                    "Dark mode",
                ]
            ),
            "state": r.choice(["open", "open", "closed"]),
            "labels": r.sample(
                ["bug", "docs", "perf", "enhancement", "good first issue"],
                r.randint(0, 2),
            ),
        }
        for i in range(16)
    ]
    exp = [
        {"n": x["n"], "title": x["title"]}
        for x in rows
        if x["state"] == "open" and "bug" in x["labels"]
    ]
    return ex(
        "github-bugs",
        "GitHub: open bugs",
        "Label lists per issue.",
        {"issues": rows},
        "Which issues are open and labelled bug?",
        ("bugs", [("n", "number"), ("title", "string")]),
        exp,
    )


def sla():
    r = rnd("sla")
    rows = [
        {
            "ticket": f"T-{900 + i}",
            "prio": r.choice(["P1", "P2", "P3", "P4"]),
            "open_h": r.randint(1, 120),
        }
        for i in range(16)
    ]
    limit = {"P1": 4, "P2": 24, "P3": 72, "P4": 168}
    exp = [
        {"ticket": x["ticket"], "over_h": x["open_h"] - limit[x["prio"]]}
        for x in rows
        if x["open_h"] > limit[x["prio"]]
    ]
    return ex(
        "support-sla",
        "Support: SLA breaches",
        "SLA limits per priority are in the metadata.",
        {"tickets": rows},
        "Which tickets have breached their SLA, and by how many hours?",
        ("breached", [("ticket", "string"), ("over_h", "number")]),
        exp,
        meta={
            "fields": {
                "tickets.prio": (
                    '$sla_hours="P1=4,P2=24,P3=72,P4=168"',
                    "SLA to resolve: P1 4 h, P2 24 h, P3 72 h, P4 168 h",
                ),
                "tickets.open_h": ('$unit="h"', "hours since the ticket was opened"),
            }
        },
        needs_meta=True,
    )


def rates():
    data = {
        "base": "EUR",
        "date": "2026-10-29",
        "rates": [
            {"ccy": "PLN", "rate": 4.2675},
            {"ccy": "USD", "rate": 1.0812},
            {"ccy": "GBP", "rate": 0.8423},
            {"ccy": "CHF", "rate": 0.9411},
            {"ccy": "CZK", "rate": 25.08},
        ],
    }
    eur = 500
    exp = [
        {"ccy": x["ccy"], "amount": round(eur * x["rate"], 2)} for x in data["rates"]
    ]
    return ex(
        "fx-rates",
        "Exchange rates: convert 500 EUR",
        "One base currency, a list of rates.",
        data,
        "How much is 500 EUR in each currency (2 decimals)?",
        ("converted", [("ccy", "string"), ("amount", "number")]),
        exp,
        meta={
            "doc": (
                '$source="ECB" #reference_rates',
                "ECB reference rates: units of currency per 1 EUR.",
            )
        },
    )


def reviews():
    r = rnd("reviews")
    rows = [
        {
            "id": i + 1,
            "stars": r.choice([1, 2, 3, 4, 5, 5, 4]),
            "text": r.choice(
                [
                    "Great!",
                    "Broke after a week",
                    "Okay",
                    "Love it",
                    "Too expensive",
                    "Fast delivery",
                ]
            ),
        }
        for i in range(14)
    ]
    verified = {0, 2, 3, 6, 9, 12}
    v = [rows[i]["stars"] for i in sorted(verified)]
    return ex(
        "reviews-verified",
        "Reviews: rating of verified buyers",
        "Verified purchases are tagged — only in the metadata.",
        {"reviews": rows},
        "What is the average star rating of verified purchases only (2 decimals)?",
        ("rating", [("avg_stars", "number")]),
        [{"avg_stars": round(sum(v) / len(v), 2)}],
        meta={
            "fields": {"reviews.stars": ('$scale="1-5"', "1 to 5 stars")},
            "records": {
                "reviews": {
                    i: ("#verified", "verified purchase") for i in sorted(verified)
                }
            },
        },
        needs_meta=True,
    )


def rooms():
    data = {
        "rooms": [
            {"room": "Aurora", "floor": 2, "seats": 6, "equipment": ["tv"]},
            {
                "room": "Borealis",
                "floor": 2,
                "seats": 10,
                "equipment": ["projector", "whiteboard"],
            },
            {
                "room": "Cirrus",
                "floor": 3,
                "seats": 8,
                "equipment": ["projector", "tv"],
            },
            {"room": "Delta", "floor": 3, "seats": 4, "equipment": []},
            {
                "room": "Echo",
                "floor": 4,
                "seats": 14,
                "equipment": ["projector", "camera"],
            },
            {"room": "Fjord", "floor": 4, "seats": 8, "equipment": ["whiteboard"]},
        ]
    }
    exp = [
        {"room": x["room"], "seats": x["seats"]}
        for x in data["rooms"]
        if x["seats"] >= 8 and "projector" in x["equipment"]
    ]
    return ex(
        "meeting-rooms",
        "Office: rooms for 8 with a projector",
        "Equipment lists.",
        data,
        "Which rooms seat at least 8 people and have a projector?",
        ("rooms", [("room", "string"), ("seats", "number")]),
        exp,
        meta={"records": {"rooms": {4: ("#needs_booking", "book via the front desk")}}},
    )


def portfolio():
    rows = [
        {"ticker": "CDR", "qty": 40, "avg": 112.5, "last": 131.2, "ccy": "PLN"},
        {"ticker": "PKN", "qty": 120, "avg": 58.1, "last": 61.4, "ccy": "PLN"},
        {"ticker": "AAPL", "qty": 10, "avg": 172.0, "last": 189.3, "ccy": "USD"},
        {"ticker": "ALE", "qty": 200, "avg": 31.2, "last": 27.9, "ccy": "PLN"},
        {"ticker": "MSFT", "qty": 6, "avg": 330.0, "last": 402.1, "ccy": "USD"},
    ]
    exp = [
        {"ticker": x["ticker"], "pnl": round((x["last"] - x["avg"]) * x["qty"], 2)}
        for x in rows
        if x["ccy"] == "PLN"
    ]
    return ex(
        "portfolio-pnl",
        "Portfolio: profit per position",
        "Average buy price vs last price.",
        {"positions": rows},
        "What is the profit or loss of each PLN position (qty × (last − avg), 2 decimals)?",
        ("pnl", [("ticker", "string"), ("pnl", "number")]),
        exp,
        meta={
            "fields": {
                "positions.avg": ("", "average buy price per share"),
                "positions.last": ("", "last traded price per share"),
            }
        },
    )


def parking():
    r = rnd("parking")
    rows = [
        {"spot": f"{lvl}-{n:02d}", "level": lvl, "occ": r.choice([0, 1, 1])}
        for lvl in ("P1", "P2", "P3")
        for n in range(1, 7)
    ]
    free: Dict[str, int] = {}
    for x in rows:
        free[x["level"]] = free.get(x["level"], 0) + (1 - x["occ"])
    exp = [{"level": k, "free": v} for k, v in sorted(free.items())]
    return ex(
        "parking-free",
        "Parking: free spots per level",
        "Occupancy as 0/1.",
        {"spots": rows},
        "How many spots are free on each level?",
        ("free", [("level", "string"), ("free", "number")]),
        exp,
        meta={
            "fields": {"spots.occ": ('$enum="0=free,1=occupied"', "0 free, 1 occupied")}
        },
        needs_meta=True,
    )


def newsletter():
    r = rnd("newsletter")
    rows = [
        {
            "campaign": f"NL-{i + 1:02d}",
            "sent": r.randint(2000, 9000),
            "open": r.randint(120, 420),
            "click": r.randint(5, 90),
        }
        for i in range(10)
    ]
    exp = [
        {"campaign": x["campaign"], "open_pct": x["open"] / 10}
        for x in sorted(rows, key=lambda x: -x["open"])
        if x["open"] > 250
    ]
    return ex(
        "newsletter-opens",
        "Newsletter: campaigns above 25 % opens",
        "Open and click rates in per mille.",
        {"campaigns": rows},
        "Which campaigns have an open rate above 25 %? Give the rate in percent, highest first.",
        ("good", [("campaign", "string"), ("open_pct", "number")]),
        exp,
        meta={
            "fields": {
                "campaigns.open": (
                    '$unit="permille"',
                    "open rate in per mille (312 = 31.2 %)",
                ),
                "campaigns.click": ('$unit="permille"', "click rate in per mille"),
            }
        },
        needs_meta=True,
    )


def dns():
    rows = [
        {"name": "@", "type": "A", "value": "203.0.113.10", "ttl": 3600},
        {"name": "www", "type": "CNAME", "value": "arkadia.solutions.", "ttl": 3600},
        {"name": "api", "type": "A", "value": "203.0.113.22", "ttl": 60},
        {"name": "@", "type": "MX", "value": "10 mail.example.net.", "ttl": 14400},
        {"name": "status", "type": "CNAME", "value": "status.example.io.", "ttl": 120},
        {"name": "_dmarc", "type": "TXT", "value": "v=DMARC1; p=none", "ttl": 300},
    ]
    exp = [
        {"name": x["name"], "type": x["type"], "ttl": x["ttl"]}
        for x in rows
        if x["ttl"] < 300
    ]
    return ex(
        "dns-ttl",
        "DNS zone: short TTLs",
        "TTL in seconds; documentation IP ranges.",
        {"records": rows},
        "Which records have a TTL below 300 seconds?",
        ("short", [("name", "string"), ("type", "string"), ("ttl", "number")]),
        exp,
        meta={
            "doc": ('$zone="arkadia.solutions"', ""),
            "fields": {"records.ttl": ('$unit="s"', "time to live in seconds")},
        },
    )


def timesheets():
    r = rnd("timesheets")
    rows = [
        {
            "who": r.choice(NAMES[:4]),
            "project": r.choice(["akd", "landing", "cli"]),
            "mins": r.choice([30, 45, 60, 90, 120, 240]),
        }
        for _ in range(18)
    ]
    tot: Dict[str, int] = {}
    for x in rows:
        tot[x["project"]] = tot.get(x["project"], 0) + x["mins"]
    exp = [
        {"project": k, "hours": round(v / 60, 2)}
        for k, v in sorted(tot.items(), key=lambda kv: -kv[1])
    ]
    return ex(
        "timesheets-hours",
        "Timesheets: hours per project",
        "Time logged in minutes.",
        {"entries": rows},
        "How many hours were logged per project (2 decimals)? Most first.",
        ("hours", [("project", "string"), ("hours", "number")]),
        exp,
        meta={"fields": {"entries.mins": ('$unit="min"', "time logged in minutes")}},
        needs_meta=True,
    )


def ci_runs():
    r = rnd("ci")
    rows = [
        {
            "run": 4000 + i,
            "branch": r.choice(["main", "dev", "feat/layout", "fix/meta"]),
            "st": r.choice([0, 0, 0, 1, 2]),
            "secs": r.randint(60, 900),
        }
        for i in range(18)
    ]
    fails: Dict[str, int] = {}
    for x in rows:
        if x["st"] == 1:
            fails[x["branch"]] = fails.get(x["branch"], 0) + 1
    exp = [
        {"branch": k, "failed": v}
        for k, v in sorted(fails.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return ex(
        "ci-failures",
        "CI: failed runs per branch",
        "Status is an exit-code-like number.",
        {"runs": rows},
        "How many runs failed on each branch? Most first.",
        ("failures", [("branch", "string"), ("failed", "number")]),
        exp,
        meta={
            "fields": {
                "runs.st": (
                    '$enum="0=passed,1=failed,2=cancelled"',
                    "0 passed, 1 failed, 2 cancelled",
                ),
                "runs.secs": ('$unit="s"', "duration in seconds"),
            }
        },
        needs_meta=True,
    )


def nutrition():
    rows = [
        {"food": "Oats", "protein": 13.2, "portion": 50},
        {"food": "Chicken breast", "protein": 31.0, "portion": 150},
        {"food": "Tofu", "protein": 12.0, "portion": 120},
        {"food": "Lentils (cooked)", "protein": 9.0, "portion": 200},
        {"food": "Greek yogurt", "protein": 10.0, "portion": 170},
        {"food": "Almonds", "protein": 21.2, "portion": 30},
    ]
    exp = [
        {"food": x["food"], "grams": round(x["protein"] * x["portion"] / 100, 1)}
        for x in sorted(rows, key=lambda x: -x["protein"] * x["portion"])
    ][:3]
    return ex(
        "nutrition-protein",
        "Nutrition: protein per portion",
        "Values per 100 g, portions in grams.",
        {"foods": rows},
        "Which 3 foods give the most protein per portion? Give grams of protein (1 decimal).",
        ("protein", [("food", "string"), ("grams", "number")]),
        exp,
        meta={
            "fields": {
                "foods.protein": (
                    '$unit="g" $per="100 g"',
                    "grams of protein per 100 g",
                ),
                "foods.portion": ('$unit="g"', "portion size in grams"),
            }
        },
        needs_meta=True,
    )


def from_annotated() -> List[dict]:
    """The four datasets of the metadata benchmark, as examples."""
    from .annotated import datasets

    out = []
    for d in datasets():
        meta = {
            "doc": (d.doc_attrs, d.doc_comment),
            "fields": {
                f"{d.root}.{f.name}": (f.attrs, f.comment)
                for f in d.fields
                if f.attrs or f.comment
            },
            "records": {
                d.root: {
                    i: (d.row_attrs.get(i, ""), d.row_comments.get(i, ""))
                    for i in sorted(set(d.row_attrs) | set(d.row_comments))
                }
            },
        }
        out.append(
            ex(
                f"{d.name}-meta",
                d.title,
                d.description,
                d.data,
                d.example_question,
                d.example_answer,
                d.example_expected,
                meta=meta,
                needs_meta=True,
            )
        )
    return out


NEW = [
    invoices,
    flights,
    grades,
    crypto,
    forecast,
    bank,
    servers,
    vitals,
    leads,
    shipments,
    recipes,
    movies,
    commits,
    hotel,
    leave,
    batteries,
    latency,
    menu,
    library,
    fleet,
    cart,
    survey,
    football,
    energy,
    jobs,
    issues,
    sla,
    rates,
    reviews,
    rooms,
    portfolio,
    parking,
    newsletter,
    dns,
    timesheets,
    ci_runs,
    nutrition,
]

# Metadata for the ten original examples (by slug): explanations a reader
# would want; their questions do not depend on it.
BASE_META: Dict[str, Meta] = {
    "employees-salaries": {
        "doc": (
            '$source="hr" $as_of="2026-10-01" #confidential',
            "Employee list exported from HR.",
        ),
        "fields": {
            "employees.salary": (
                '$unit="EUR" $period="year"',
                "gross yearly salary in EUR",
            ),
            "employees.active": ("", "false = left the company"),
        },
    },
    "logs-incidents": {
        "doc": ('$env="prod" #incident', "Application logs from production."),
        "fields": {
            "logs.latency_ms": ('$unit="ms"', "request latency in milliseconds"),
            "logs.status": ("", "HTTP status code"),
        },
    },
    "search-tool-result": {
        "doc": (
            '$tool="web_search" $engine="brave"',
            "Raw result of the web_search tool.",
        )
    },
    "analytics-top-days": {
        "doc": ('$site="shop" $tz="UTC"', "Daily traffic and sales.")
    },
    "inventory-reorder": {
        "doc": ('$warehouse="WAW-1" #stock', "Stock levels in warehouse WAW-1.")
    },
    "calendar-free-slots": {
        "doc": ('$tz="Europe/Warsaw" #calendar', "Busy slots, local time.")
    },
}


def catalogue(base: List[dict]) -> List[dict]:
    """The ten original examples (with metadata where useful), the new ones and the annotated ones."""
    out = []
    for b in base:
        m = BASE_META.get(b["slug"], {})
        if m:
            b = dict(b, meta=m, needs_meta=False)
        else:
            b = dict(b, meta={}, needs_meta=False)
        out.append(b)
    out += [build() for build in NEW]
    out += from_annotated()
    for i, e in enumerate(out, 1):
        e["id"] = i
        paths = set(header_paths(e["data"]))
        missing = [p for p in e["meta"].get("fields", {}) if p not in paths]
        if missing:
            raise ValueError(
                f"{e['slug']}: no header field {missing} (fields: {sorted(paths)})"
            )
        e["tags"] = (["metadata"] if e["meta"] else []) + (
            ["needs metadata"] if e["needs_meta"] else []
        )
    return out
