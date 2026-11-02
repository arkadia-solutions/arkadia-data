"""
Writes rust/data/gallery.json: the small, varied snippets of `ak-data example`.

Each snippet shows one part of AK-DATA (flat table, nesting, lists, irregular
records, type overrides, named types, metadata, special names …) and carries a
question for a chat model with the expected answer computed here from the data.
Snippets with `akd` are hand-written AK-DATA (features the encoder does not
produce, e.g. comments or named types); the others are JSON that `ak-data`
encodes itself.

    cd arkadia-data && PYTHONPATH=python/src python3 rust/scripts/make_gallery.py
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter, defaultdict

import arkadia.data as akd

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "gallery.json"


def snippet(slug, title, shows, question, answer, expected, data=None, text=None):
    item = {
        "slug": slug,
        "title": title,
        "shows": shows,
        "question": question,
        "answer": {"name": answer[0], "fields": [list(f) for f in answer[1]]},
        "expected": expected,
    }
    if text is not None:
        item["akd"] = text.strip()
        assert akd.loads(item["akd"]) is not None
    else:
        item["data"] = data
    return item


def users():
    data = {
        "users": [
            {"id": 1, "name": "Ada Lovelace", "email": "ada@example.com", "role": "admin", "active": True},
            {"id": 2, "name": "Alan Turing", "email": "alan@example.com", "role": "user", "active": True},
            {"id": 3, "name": "Grace Hopper", "email": "grace@example.com", "role": "admin", "active": False},
            {"id": 4, "name": "Linus Torvalds", "email": "linus@example.com", "role": "user", "active": True},
            {"id": 5, "name": "Margaret Hamilton", "email": "margaret@example.com", "role": "admin", "active": True},
        ]
    }
    exp = [{"id": u["id"], "name": u["name"]} for u in data["users"] if u["active"] and u["role"] == "admin"]
    return snippet(
        "users-table",
        "Flat table: users",
        "A list of records sharing one header: field names are written once, every record is a (…) tuple in header order.",
        "Which active users are admins?",
        ("admins", [("id", "number"), ("name", "string")]),
        exp,
        data=data,
    )


def orders():
    data = {
        "orders": [
            {"id": "ORD-1001", "status": "paid", "customer": {"id": 7, "name": "Hedy Johnson", "country": "PL"},
             "items": [{"sku": "KB-01", "qty": 2, "price": 89.0}, {"sku": "MS-02", "qty": 1, "price": 39.5}]},
            {"id": "ORD-1002", "status": "pending", "customer": {"id": 9, "name": "Ada Torvalds", "country": "DE"},
             "items": [{"sku": "HD-10", "qty": 1, "price": 129.9}]},
            {"id": "ORD-1003", "status": "paid", "customer": {"id": 7, "name": "Hedy Johnson", "country": "PL"},
             "items": [{"sku": "DK-05", "qty": 1, "price": 199.0}, {"sku": "KB-01", "qty": 1, "price": 89.0}]},
        ]
    }
    exp = []
    for o in data["orders"]:
        if o["status"] == "paid":
            exp.append({"id": o["id"], "total": round(sum(i["qty"] * i["price"] for i in o["items"]), 2)})
    return snippet(
        "nested-orders",
        "Nested records: orders with customer and items",
        "Headers nest: customer is a record <…> inside the record, items a list of records <[…]>; nested values stay positional.",
        "What is the total (qty × price) of every paid order?",
        ("paid", [("id", "string"), ("total", "number")]),
        exp,
        data=data,
    )


def search():
    data = {
        "tool": "web_search",
        "query": "agent memory",
        "results": [
            {"rank": 1, "title": "Agent memory in production", "url": "https://example.org/a", "score": 0.97},
            {"rank": 2, "title": "Token budgets for agents", "url": "https://example.org/b", "score": 0.94},
            {"rank": 3, "title": "Context engineering", "url": "https://example.org/c", "score": 0.88},
            {"rank": 4, "title": "Vector stores compared", "url": "https://example.org/d", "score": 0.71},
        ],
    }
    exp = [{"rank": r["rank"], "url": r["url"]} for r in data["results"] if r["score"] >= 0.9]
    return snippet(
        "tool-result",
        "Agent tool result: web search hits",
        "A record with simple fields and a list of records — the typical tool output an agent puts back into the context.",
        "Which results have a score of at least 0.9?",
        ("hits", [("rank", "number"), ("url", "string")]),
        exp,
        data=data,
    )


def metrics():
    days = [
        ("2026-10-19", 1840, 31, 1290.5), ("2026-10-20", 2210, 44, 1980.0), ("2026-10-21", 1975, 29, 1405.25),
        ("2026-10-22", 2650, 57, 2410.0), ("2026-10-23", 2390, 48, 2005.75), ("2026-10-24", 1210, 12, 640.0),
        ("2026-10-25", 1105, 15, 702.5),
    ]
    data = {"metric": "daily", "days": [{"date": d, "visits": v, "signups": s, "revenue": r} for d, v, s, r in days]}
    best = max(data["days"], key=lambda d: d["signups"])
    return snippet(
        "time-series",
        "Time series: a week of metrics",
        "Numbers stay numbers (no quotes); a time series is just a list of records with a date field.",
        "Which day had the most signups, and what was the revenue that day?",
        ("best", [("date", "string"), ("signups", "number"), ("revenue", "number")]),
        [{"date": best["date"], "signups": best["signups"], "revenue": best["revenue"]}],
        data=data,
    )


def logs():
    events = [
        ("12:00:01", "info", "api", "GET /orders", 42), ("12:00:03", "error", "billing", "card declined", 380),
        ("12:00:04", "warn", "api", "slow query", 1210), ("12:00:07", "error", "billing", "timeout", 5000),
        ("12:00:09", "info", "auth", "login ok", 18), ("12:00:11", "error", "api", "upstream 502", 2210),
        ("12:00:12", "error", "billing", "timeout", 5000), ("12:00:15", "info", "api", "GET /users", 37),
    ]
    data = {"events": [{"ts": t, "level": lv, "service": s, "msg": m, "ms": ms} for t, lv, s, m, ms in events]}
    count = Counter(e["service"] for e in data["events"] if e["level"] == "error")
    exp = [{"service": s, "errors": n} for s, n in count.most_common()]
    return snippet(
        "logs",
        "Logs: which service is failing?",
        "Repeated rows are where AK-DATA saves most: the five field names appear once instead of eight times.",
        "How many errors does each service have? Most errors first.",
        ("errors", [("service", "string"), ("errors", "number")]),
        exp,
        data=data,
    )


def irregular():
    data = {
        "service": "workspace",
        "agents": [
            {"name": "planner", "tools": ["search", "files", "calendar"], "max_steps": 12},
            {"name": "writer", "tools": ["files"], "max_steps": 6},
            {"name": "reviewer", "tools": ["files", "search"], "temperature": 0.2},
        ],
        "limits": {"tokens": 120000, "retries": [1, 5, 30]},
        "storage": None,
    }
    top = max(data["agents"], key=lambda a: len(a["tools"]))
    return snippet(
        "irregular",
        "Irregular data: a record that does not fit the header",
        "The third agent has temperature instead of max_steps, so it is written as <any> {key:value} with its own keys — still lossless.",
        "Which agent can use the most tools, and how many?",
        ("agent", [("name", "string"), ("tools", "number")]),
        [{"name": top["name"], "tools": len(top["tools"])}],
        data=data,
    )


def overrides():
    data = {
        "products": [
            {"sku": "KB-01", "name": "Keyboard", "price": 89.0, "stock": 14},
            {"sku": "MS-02", "name": "Mouse", "price": 39.5, "stock": 0},
            {"sku": 3001, "name": "USB cable", "price": None, "stock": 120},
            {"sku": "HD-10", "name": "Headset", "price": 129.9, "stock": "on order"},
        ]
    }
    exp = [{"name": p["name"]} for p in data["products"] if p["price"] is None or p["stock"] == 0 or isinstance(p["stock"], str)]
    return snippet(
        "type-override",
        "Type overrides: values that differ from the header",
        "When one value has another type than its column, it is prefixed with <type> — <number> 3001, <string> \"on order\"; null fits every type.",
        "Which products cannot be sold right now (no price, no stock, or stock not a number)?",
        ("blocked", [("name", "string")]),
        exp,
        data=data,
    )


def repos():
    rows = [
        ("arkadia-data", 1840, ["llm", "json", "rust", "python"], False),
        ("ak-workspace", 920, ["agents", "electron"], False),
        ("toon-python", 310, ["llm", "python"], True),
        ("star-federation", 75, [], False),
        ("universal-timer", 210, ["rust", "cli"], False),
    ]
    data = {"repositories": [{"name": n, "stars": s, "topics": t, "archived": a} for n, s, t, a in rows]}
    exp = [{"name": r["name"], "stars": r["stars"]} for r in sorted(data["repositories"], key=lambda r: -r["stars"]) if "rust" in r["topics"] and not r["archived"]]
    return snippet(
        "lists-in-records",
        "Lists inside records: repositories with topics",
        "A field can hold a list of values: topics:[string] in the header, [\"llm\",\"rust\"] or [] in the record.",
        "Which repositories that are not archived have the topic rust? Most stars first.",
        ("repos", [("name", "string"), ("stars", "number")]),
        exp,
        data=data,
    )


def matrix():
    data = {"name": "distance (km)", "cities": ["Warsaw", "Kraków", "Gdańsk", "Wrocław"],
            "km": [[0, 293, 340, 344], [293, 0, 591, 269], [340, 591, 0, 482], [344, 269, 482, 0]]}
    pairs = [(data["cities"][i], data["cities"][j], data["km"][i][j]) for i in range(4) for j in range(i + 1, 4)]
    a, b, d = max(pairs, key=lambda p: p[2])
    return snippet(
        "matrix",
        "Lists of lists: a distance matrix",
        "Nested lists need no header beyond [[number]]: rows are plain [ … ] lists.",
        "Which two cities are farthest apart, and how far?",
        ("pair", [("from", "string"), ("to", "string"), ("km", "number")]),
        [{"from": a, "to": b, "km": d}],
        data=data,
    )


def tickets():
    data = {
        "tickets": [
            {"id": 501, "subject": "Invoice is wrong", "priority": "normal", "assignee": {"id": 3, "name": "Ola"}, "tags": ["billing"]},
            {"id": 502, "subject": "Cannot log in", "priority": "urgent", "assignee": None, "tags": ["auth"]},
            {"id": 503, "subject": "Data export fails", "priority": "urgent", "assignee": {"id": 5, "name": "Piotr"}, "tags": ["export", "bug"]},
            {"id": 504, "subject": "App crashes on start", "priority": "urgent", "assignee": None, "tags": ["mobile", "bug"]},
        ]
    }
    exp = [{"id": t["id"], "subject": t["subject"]} for t in data["tickets"] if t["priority"] == "urgent" and t["assignee"] is None]
    return snippet(
        "nulls",
        "Missing values: support tickets",
        "A nested record that is missing is <null> null (or null): the header still describes the record when it is there.",
        "Which urgent tickets have nobody assigned?",
        ("unassigned", [("id", "number"), ("subject", "string")]),
        exp,
        data=data,
    )


def special_keys():
    data = {
        "rows": [
            {"user id": 17, "e-mail": "ada@example.com", "2fa": True, "last login": "2026-10-28"},
            {"user id": 18, "e-mail": "alan@example.com", "2fa": False, "last login": "2026-09-02"},
            {"user id": 19, "e-mail": "grace@example.com", "2fa": False, "last login": "2026-10-27"},
        ]
    }
    exp = [{"user_id": r["user id"], "email": r["e-mail"]} for r in data["rows"] if not r["2fa"]]
    return snippet(
        "special-names",
        "Names with spaces and symbols",
        "Field names that are not simple identifiers go in backticks: `user id`, `e-mail`, `2fa`.",
        "Which users do not have 2FA enabled?",
        ("no_2fa", [("user_id", "number"), ("email", "string")]),
        exp,
        data=data,
    )


NAMED = """
/* Team directory: one type, used three times */
@User<id:number, name:string, email:string>
<team:string, lead:@User, members:[@User]>
(
  "platform",
  (1, "Ada Lovelace", "ada@example.com"),
  [
    (2, "Alan Turing", "alan@example.com"),
    (3, "Grace Hopper", "grace@example.com"),
    (4, "Linus Torvalds", "linus@example.com")
  ]
)
"""

META = """
// $source="crm" $exported="2026-10-29" #snapshot //
<customers:<[
  id:number /* primary key */,
  name:string,
  plan:string $values="free|pro|team",
  mrr:number /* monthly revenue, EUR */
]>>
([
  (1, "Acme", "team", 1200) #enterprise,
  (2, "Globex", "pro", 99),
  (3, "Initech", "free", 0) /* trial ended */,
  (4, "Umbrella", "team", 2400) #enterprise
])
"""


SCHEMA_META = """
// $source="catalogue" $exported="2026-10-30" #snapshot //
/* Product catalogue: one named type with schema metadata */
@Product<[
  /* Schema metadata: rules for every product */
  sku:string $required /* stock keeping unit */,
  name:string $required,
  price:number $unit="EUR" $min=0,
  tags:[string] $maxItems=3
]>
<products:@Product>
([
  /* Instance metadata: facts about one product */
  $verified=true ("PROD-123", "Keyboard", 89.0, ["new", "wireless"]) #featured,
  ("PROD-124", "Mouse", 39.5, []),
  $verified=true ("PROD-125", "Dock", 199.0, ["usb-c"]),
  ("PROD-126", "Cable", 9.99, ["usb-c"]) #discontinued /* sold out, no restock */
])
"""


def schema_meta():
    data = akd.loads(SCHEMA_META)
    return snippet(
        "schema-metadata",
        "Schema and instance metadata",
        "Metadata on the header ($required, $unit, $maxItems, comments) describes every record; metadata on a value ($verified, #featured, #discontinued) describes one record. Both are skipped when decoding — the JSON is the same — but a model reads them.",
        "Which products are verified and not discontinued? Give the sku and the price in EUR.",
        ("verified", [("sku", "string"), ("eur", "number")]),
        [{"sku": p["sku"], "eur": p["price"]} for p in data["products"] if p["sku"] in ("PROD-123", "PROD-125")],
        text=SCHEMA_META,
    )


def named():
    data = akd.loads(NAMED)
    return snippet(
        "named-types",
        "Named types: @User defined once, used three times",
        "@User<…> names a header; lead:@User and members:[@User] reuse it. Hand-written AK-DATA (the encoder writes inline headers).",
        "How many people are in the team, including the lead? Give the team name too.",
        ("team", [("name", "string"), ("people", "number")]),
        [{"name": data["team"], "people": 1 + len(data["members"])}],
        text=NAMED,
    )


def meta():
    data = akd.loads(META)
    paying = [c for c in data["customers"] if c["mrr"] > 0]
    by_plan = defaultdict(int)
    for c in paying:
        by_plan[c["plan"]] += c["mrr"]
    exp = [{"plan": p, "mrr": v} for p, v in sorted(by_plan.items(), key=lambda kv: -kv[1])]
    return snippet(
        "metadata",
        "Comments, attributes and tags",
        "/* comments */, $attr=value, #tags and // … // blocks are notes for the reader: they are skipped when decoding, the data is unchanged.",
        "What is the total monthly revenue (mrr) per plan? Highest first.",
        ("mrr", [("plan", "string"), ("mrr", "number")]),
        exp,
        text=META,
    )


def calendar():
    data = {
        "date": "2026-11-03",
        "people": [
            {"name": "Ada", "busy": [["09:00", "10:30"], ["13:00", "14:00"]]},
            {"name": "Alan", "busy": [["10:00", "11:00"], ["15:00", "16:00"]]},
            {"name": "Grace", "busy": [["09:00", "09:30"], ["11:00", "12:00"]]},
        ],
        "working_hours": ["09:00", "17:00"],
    }
    hours = [f"{h:02d}:00" for h in range(9, 17)]

    def free(person, start):
        s = int(start[:2]) * 60
        e = s + 60
        for a, b in person["busy"]:
            bs, be = int(a[:2]) * 60 + int(a[3:]), int(b[:2]) * 60 + int(b[3:])
            if bs < e and s < be:
                return False
        return True

    exp = [{"start": h} for h in hours if all(free(p, h) for p in data["people"])]
    return snippet(
        "calendar",
        "Calendar: lists of [start, end] pairs",
        "Records can hold lists of lists; the header says busy:[[string]] once for every person.",
        "Which full hours (start on the hour, 60 minutes) are free for everyone?",
        ("free", [("start", "string")]),
        exp,
        data=data,
    )


def main():
    items = [users(), orders(), search(), metrics(), logs(), irregular(), overrides(), repos(),
             matrix(), tickets(), special_keys(), named(), meta(), schema_meta(), calendar()]
    for i, item in enumerate(items, 1):
        item["id"] = i
    OUT.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Written {OUT} ({len(items)} snippets)")


if __name__ == "__main__":
    main()
