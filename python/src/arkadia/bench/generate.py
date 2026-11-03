"""
Randomly generated datasets for the AI benchmark.

The eight bundled datasets give about 80 questions — too few to tell formats
apart (one question is more than one percentage point). `generate(n, seed)`
adds `n` datasets of varied, realistic shapes; each one gets its own
questions (computed from the data), so the sample grows with `n` and a
different `seed` gives a different sample:

    flat       a table of 30–140 records (ids, categories, numbers, dates,
               booleans, some nulls)
    wide       a table with 12–16 columns (long positional records)
    nested     records with a nested record, a list of values and a list of
               records (orders with customer, tags and items)
    irregular  records with optional fields (only some records have them)
    multi      a document with two or three tables and scalar settings
    document   a configuration-like nested document with small lists
    matrix     a table whose records hold lists of numbers

Everything is deterministic for a given seed.
"""

from __future__ import annotations

import datetime as _dt
import random
from typing import Any, Callable, Dict, List

from .datasets import Dataset

FIRST = [
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
    "Frances",
    "Hedy",
    "Katherine",
    "John",
    "Donald",
    "Mary",
    "Tim",
    "Sophie",
    "Niklaus",
    "Shafi",
    "Leslie",
    "Anita",
    "Bjarne",
    "Guido",
]
LAST = [
    "Lovelace",
    "Turing",
    "Hopper",
    "Torvalds",
    "Hamilton",
    "Ritchie",
    "Liskov",
    "Thompson",
    "Perlman",
    "Dijkstra",
    "Allen",
    "Lamarr",
    "Johnson",
    "Backus",
    "Knuth",
    "Kowalski",
    "Nowak",
    "Berners-Lee",
    "Wirth",
    "Goldwasser",
]
CITIES = [
    "Warsaw",
    "Berlin",
    "Paris",
    "Lisbon",
    "Madrid",
    "Prague",
    "Oslo",
    "Vienna",
    "Rome",
    "Dublin",
]
COUNTRIES = ["PL", "DE", "FR", "PT", "ES", "CZ", "NO", "AT", "IT", "IE"]
WORDS = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "nova",
    "orbit",
    "pixel",
    "quartz",
    "river",
    "summit",
    "tango",
    "vector",
    "willow",
    "zenith",
    "ember",
    "harbor",
    "lumen",
]
TAGS = [
    "urgent",
    "vip",
    "gift",
    "b2b",
    "promo",
    "repeat",
    "new",
    "fragile",
    "eco",
    "late",
]


def _name(r: random.Random) -> str:
    return f"{r.choice(FIRST)} {r.choice(LAST)}"


def _date(r: random.Random, year: int = 2026) -> str:
    d = _dt.date(year, 1, 1) + _dt.timedelta(days=r.randrange(0, 300))
    return d.isoformat()


def _time(r: random.Random) -> str:
    return (
        f"{_date(r)}T{r.randrange(24):02d}:{r.randrange(60):02d}:{r.randrange(60):02d}Z"
    )


def _money(r: random.Random, lo: float, hi: float) -> float:
    return round(r.uniform(lo, hi), 2)


def _unique(r: random.Random, make: Callable[[], Any], n: int) -> List[Any]:
    seen, out = set(), []
    while len(out) < n:
        v = make()
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# --------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------


def flat(r: random.Random) -> Dict[str, Any]:
    kind = r.choice(["employees", "products", "tickets", "sensors"])
    n = r.randrange(30, 141)
    rows = []
    if kind == "employees":
        depts = r.sample(
            [
                "Engineering",
                "Sales",
                "Marketing",
                "Finance",
                "Support",
                "Legal",
                "Research",
            ],
            5,
        )
        for i in range(n):
            rows.append(
                {
                    "id": 1000 + i,
                    "name": _name(r),
                    "department": r.choice(depts),
                    "city": r.choice(CITIES[:6]),
                    "salary": r.randrange(3500, 16000, 50),
                    "remote": r.random() < 0.4,
                    "hired": _date(r, r.choice([2019, 2021, 2023, 2025])),
                    "manager_id": None if r.random() < 0.15 else 1000 + r.randrange(n),
                }
            )
        return {"employees": rows}
    if kind == "products":
        cats = r.sample(
            ["audio", "video", "office", "garden", "kitchen", "sport", "toys"], 4
        )
        skus = _unique(
            r,
            lambda: (
                f"{r.choice('ABCDEFGH')}{r.choice('KLMNPRST')}-{r.randrange(100, 999)}"
            ),
            n,
        )
        for i in range(n):
            rows.append(
                {
                    "sku": skus[i],
                    "title": f"{r.choice(WORDS).title()} {r.choice(['Pro', 'Mini', 'Max', 'Air', 'One', 'Plus'])}",
                    "category": r.choice(cats),
                    "price": _money(r, 4, 900),
                    "stock": r.randrange(0, 400),
                    "rating": round(r.uniform(2.5, 5.0), 1),
                    "discontinued": r.random() < 0.1,
                }
            )
        return {"products": rows}
    if kind == "tickets":
        for i in range(n):
            rows.append(
                {
                    "ticket": f"T-{5000 + i}",
                    "priority": r.choice(["low", "normal", "high", "urgent"]),
                    "status": r.choice(["open", "pending", "solved", "closed"]),
                    "assignee": None if r.random() < 0.25 else r.choice(FIRST[:8]),
                    "opened": _time(r),
                    "replies": r.randrange(0, 14),
                    "subject": f"{r.choice(['Cannot', 'How to', 'Error when', 'Question about'])} {r.choice(WORDS)} {r.choice(WORDS)}",
                }
            )
        return {"tickets": rows}
    for i in range(n):
        rows.append(
            {
                "sensor": f"S{r.randrange(1, 13):02d}",
                "ts": _time(r),
                "temp_c": round(r.uniform(-12, 38), 1),
                "humidity": r.randrange(15, 99),
                "battery": r.randrange(5, 101),
                "ok": r.random() < 0.85,
            }
        )
    return {"readings": rows}


def wide(r: random.Random) -> Dict[str, Any]:
    n = r.randrange(25, 70)
    cols = r.randrange(12, 17)
    names = [
        "id",
        "name",
        "segment",
        "country",
        "orders",
        "revenue",
        "refunds",
        "visits",
        "signups",
        "churned",
        "score",
        "plan",
        "seats",
        "mrr",
        "nps",
        "since",
    ]
    rows = []
    for i in range(n):
        full = {
            "id": i + 1,
            "name": f"{r.choice(WORDS).title()} {r.choice(['Ltd', 'GmbH', 'SA', 'Inc', 'sp. z o.o.'])}",
            "segment": r.choice(["smb", "mid", "enterprise"]),
            "country": r.choice(COUNTRIES),
            "orders": r.randrange(0, 500),
            "revenue": _money(r, 0, 90000),
            "refunds": r.randrange(0, 20),
            "visits": r.randrange(100, 30000),
            "signups": r.randrange(0, 900),
            "churned": r.random() < 0.12,
            "score": r.randrange(0, 101),
            "plan": r.choice(["free", "team", "business"]),
            "seats": r.randrange(1, 250),
            "mrr": _money(r, 0, 9000),
            "nps": r.randrange(-100, 101),
            "since": _date(r, r.choice([2020, 2022, 2024])),
        }
        rows.append({k: full[k] for k in names[:cols]})
    return {"accounts": rows}


def nested(r: random.Random) -> Dict[str, Any]:
    n = r.randrange(20, 55)
    catalog = [
        (f"{w[:3].upper()}-{r.randrange(10, 99)}", w.title(), _money(r, 3, 400))
        for w in r.sample(WORDS, 8)
    ]
    orders = []
    for i in range(n):
        items = []
        for sku, title, price in r.sample(catalog, r.randrange(1, 5)):
            items.append(
                {"sku": sku, "title": title, "qty": r.randrange(1, 6), "price": price}
            )
        orders.append(
            {
                "id": f"ORD-{2000 + i}",
                "status": r.choice(["new", "paid", "shipped", "delivered", "returned"]),
                "customer": {
                    "id": r.randrange(1, 90),
                    "name": _name(r),
                    "address": {
                        "city": r.choice(CITIES),
                        "country": r.choice(COUNTRIES),
                    },
                },
                "tags": r.sample(TAGS, r.randrange(0, 4)),
                "items": items,
                "total": round(sum(it["qty"] * it["price"] for it in items), 2),
                "placed": _date(r),
            }
        )
    return {"orders": orders}


def irregular(r: random.Random) -> Dict[str, Any]:
    n = r.randrange(25, 80)
    events = []
    for i in range(n):
        e: Dict[str, Any] = {
            "id": i + 1,
            "ts": _time(r),
            "type": r.choice(["login", "purchase", "error", "logout", "search"]),
            "user": r.choice(FIRST),
        }
        if e["type"] == "purchase" or r.random() < 0.2:
            e["amount"] = _money(r, 5, 600)
        if e["type"] == "error" or r.random() < 0.1:
            e["code"] = r.choice([400, 401, 404, 500, 503])
        if e["type"] == "search" or r.random() < 0.15:
            e["query"] = f"{r.choice(WORDS)} {r.choice(WORDS)}"
        events.append(e)
    return {"events": events}


def multi(r: random.Random) -> Dict[str, Any]:
    teams = []
    people = _unique(r, lambda: _name(r), r.randrange(15, 40))
    for i, name in enumerate(people):
        teams.append(
            {
                "member": name,
                "team": r.choice(["core", "web", "mobile", "data", "infra"]),
                "role": r.choice(["engineer", "lead", "designer", "analyst"]),
                "level": r.randrange(1, 6),
            }
        )
    projects = []
    for i in range(r.randrange(8, 20)):
        projects.append(
            {
                "code": f"P{100 + i}",
                "name": f"{r.choice(WORDS).title()} {r.choice(WORDS).title()}",
                "owner": r.choice(people),
                "budget": r.randrange(5, 400) * 1000,
                "done": r.random() < 0.3,
                "deadline": _date(r),
            }
        )
    doc: Dict[str, Any] = {
        "company": f"{r.choice(WORDS).title()} Labs",
        "fiscal_year": 2026,
        "currency": r.choice(["EUR", "PLN", "USD"]),
        "people": teams,
        "projects": projects,
    }
    if r.random() < 0.5:
        doc["offices"] = [
            {"city": c, "desks": r.randrange(10, 200), "open": r.random() < 0.9}
            for c in r.sample(CITIES, r.randrange(3, 7))
        ]
    return doc


def document(r: random.Random) -> Dict[str, Any]:
    return {
        "service": f"{r.choice(WORDS)}-{r.choice(WORDS)}",
        "version": f"{r.randrange(1, 6)}.{r.randrange(0, 20)}.{r.randrange(0, 30)}",
        "debug": r.random() < 0.3,
        "server": {
            "host": f"{r.choice(WORDS)}.internal",
            "port": r.choice([80, 443, 8080, 8443, 9000]),
            "tls": {
                "enabled": r.random() < 0.8,
                "min_version": r.choice(["1.2", "1.3"]),
            },
        },
        "database": {
            "engine": r.choice(["postgres", "mysql", "sqlite"]),
            "pool": {"min": r.randrange(1, 5), "max": r.randrange(10, 60)},
            "replicas": [f"db-{i}.internal" for i in range(r.randrange(1, 4))],
        },
        "features": {w: r.random() < 0.5 for w in r.sample(WORDS, 5)},
        "limits": {
            "rps": r.randrange(50, 5000),
            "burst": r.randrange(10, 500),
            "timeout_ms": r.randrange(100, 30000, 100),
        },
        "workers": [
            {
                "name": w,
                "threads": r.randrange(1, 17),
                "queues": r.sample(
                    ["mail", "pdf", "sync", "index", "billing"], r.randrange(1, 4)
                ),
            }
            for w in r.sample(WORDS, r.randrange(3, 7))
        ],
    }


def matrix(r: random.Random) -> Dict[str, Any]:
    n = r.randrange(12, 36)
    rows = []
    for i in range(n):
        rows.append(
            {
                "store": f"{r.choice(CITIES)}-{i + 1}",
                "region": r.choice(["north", "south", "east", "west"]),
                "weekly_sales": [r.randrange(0, 900) for _ in range(7)],
                "open": r.random() < 0.9,
            }
        )
    return {"week": f"2026-W{r.randrange(1, 52):02d}", "stores": rows}


SHAPES: Dict[str, Callable[[random.Random], Dict[str, Any]]] = {
    "flat": flat,
    "wide": wide,
    "nested": nested,
    "irregular": irregular,
    "multi": multi,
    "document": document,
    "matrix": matrix,
}

DESCRIPTIONS = {
    "flat": "random flat table",
    "wide": "random wide table (12–16 columns)",
    "nested": "random orders with nested customer, tags and items",
    "irregular": "random events with optional fields",
    "multi": "random document with several tables",
    "document": "random nested configuration",
    "matrix": "random records holding lists of numbers",
}


def generate(n: int, seed: int = 7) -> List[Dataset]:
    """`n` random datasets, cycling through the shapes in a shuffled order."""
    r = random.Random(f"arkadia-bench:{seed}")
    shapes = list(SHAPES)
    out: List[Dataset] = []
    order: List[str] = []
    while len(order) < n:
        block = shapes[:]
        r.shuffle(block)
        order += block
    for i, shape in enumerate(order[:n], 1):
        data = SHAPES[shape](r)
        out.append(
            Dataset(
                name=f"rnd-{i:02d}-{shape}",
                data=data,
                source=f"generated (seed {seed})",
                description=DESCRIPTIONS[shape],
            )
        )
    return out
