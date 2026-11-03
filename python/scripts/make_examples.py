"""
Builds the ten copy-paste prompt examples.

Writes:
  src/arkadia/bench/examples/NN-slug.json   data, question, answer shape, expected answer
  ../examples/prompts/NN-slug/*.txt         the prompt in JSON, TOON, AK-DATA, AK-DATA COMPACT
  ../examples/prompts/examples.json         everything + token counts (used by the website)
  ../examples/prompts/README.md             index with token counts

Expected answers are computed from the data, so a model's reply can be checked.

    python scripts/make_examples.py
"""

import datetime as dt
import json
import math
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import arkadia.data as akd  # noqa: E402
from arkadia.bench.datasets import bundled  # noqa: E402
from arkadia.bench.prompts import FORMAT_NAMES, example_matrix  # noqa: E402
from arkadia.data import layout  # noqa: E402

PKG_DIR = ROOT / "src" / "arkadia" / "bench" / "examples"
# Bundled into the Rust `ak-data` binary for `ak-data prompt --example N`.
RUST_FILE = ROOT.parent / "rust" / "data" / "examples.json"
OUT_DIR = ROOT.parent / "examples" / "prompts"
R = random.Random(2026)
B = {d.name: d.data for d in bundled()}
FILE_NAMES = {
    "json": "json",
    "toon": "toon",
    "akd": "ak-data",
    "akcd": "ak-data-compact",
}


def ex_employees():
    rows = B["employees"]["employees"][:30]
    acc = {}
    for r in rows:
        if r["active"]:
            acc.setdefault(r["department"], []).append(r["salary"])
    stats = sorted(
        (
            {"department": d, "employees": len(v), "avg_salary": round(sum(v) / len(v))}
            for d, v in acc.items()
        ),
        key=lambda x: -x["avg_salary"],
    )[:3]
    return dict(
        slug="employees-salaries",
        title="HR table: average salary by department",
        description="30 employee records. Aggregation over a filtered table.",
        question=(
            "Among active employees, which 3 departments have the highest average salary? "
            "Give the department, the number of active employees and the average salary "
            "rounded to a whole number."
        ),
        answer={
            "name": "result",
            "fields": [
                ["department", "string"],
                ["employees", "number"],
                ["avg_salary", "number"],
            ],
        },
        expected=stats,
        data={"employees": rows},
    )


def ex_orders():
    orders = B["orders"]["orders"][:15]
    acc = {}
    for o in orders:
        if o["status"] in ("paid", "shipped", "delivered"):
            a = acc.setdefault(o["customer"]["country"], [0, 0.0])
            a[0] += 1
            a[1] += o["total"]
    res = sorted(
        (
            {"country": c, "orders": n, "revenue": round(t, 2)}
            for c, (n, t) in acc.items()
        ),
        key=lambda x: -x["revenue"],
    )
    return dict(
        slug="orders-revenue",
        title="E-commerce: revenue per country (nested orders)",
        description="15 orders with a nested customer and item list. Filter, group, sum.",
        question=(
            "For orders with status paid, shipped or delivered, what is the number of orders "
            "and the total revenue (sum of total) per customer country? Sort by revenue, "
            "highest first."
        ),
        answer={
            "name": "result",
            "fields": [
                ["country", "string"],
                ["orders", "number"],
                ["revenue", "number"],
            ],
        },
        expected=res,
        data={"orders": orders},
    )


def ex_logs():
    logs = B["logs"]["logs"][:60]
    acc = {}
    for e in logs:
        a = acc.setdefault(e["service"], {"errors": 0, "warnings": 0, "lat": []})
        if e["level"] == "ERROR":
            a["errors"] += 1
            a["lat"].append(e["latency_ms"])
        elif e["level"] == "WARN":
            a["warnings"] += 1
    res = sorted(
        (
            {
                "service": s,
                "errors": a["errors"],
                "warnings": a["warnings"],
                "avg_error_latency_ms": round(sum(a["lat"]) / len(a["lat"]))
                if a["lat"]
                else None,
            }
            for s, a in acc.items()
        ),
        key=lambda x: (-x["errors"], x["service"]),
    )
    return dict(
        slug="logs-incidents",
        title="Ops: which service is failing? (logs)",
        description="60 log events. Counting by level and averaging a numeric field.",
        question=(
            "For each service, count the ERROR and WARN events and give the average "
            "latency_ms of its ERROR events (rounded; null if none). Sort by ERROR count, "
            "highest first."
        ),
        answer={
            "name": "result",
            "fields": [
                ["service", "string"],
                ["errors", "number"],
                ["warnings", "number"],
                ["avg_error_latency_ms", "number"],
            ],
        },
        expected=res,
        data={"logs": logs},
    )


def ex_search():
    tr = B["tool-results"]
    results = tr["results"][:15]
    best = sorted(
        (r for r in results if "agent memory" in r["title"]), key=lambda r: -r["score"]
    )[:3]
    return dict(
        slug="search-tool-result",
        title="Agent tool result: pick the best search hits",
        description="A web_search tool result with 15 hits, as an agent would receive it.",
        question=(
            "Which 3 results best answer 'how should agents manage memory'? Give the rank, "
            "the url and a one-sentence reason for each."
        ),
        answer={
            "name": "result",
            "fields": [["rank", "number"], ["url", "string"], ["reason", "string"]],
        },
        expected=[{"rank": r["rank"], "url": r["url"]} for r in best],
        expected_note="Reasons are free text; ranks and urls should match the hits about agent memory with the highest scores.",
        data={**{k: v for k, v in tr.items() if k != "results"}, "results": results},
    )


def ex_analytics():
    rows = B["analytics"]["rows"][:28]
    top = sorted(rows, key=lambda r: -r["revenue"])[:3]
    return dict(
        slug="analytics-top-days",
        title="Analytics: best days in a time series",
        description="28 days of metrics. Sorting a time series.",
        question="Which 3 days had the highest revenue? Give the date, revenue, visits and signups.",
        answer={
            "name": "result",
            "fields": [
                ["date", "string"],
                ["revenue", "number"],
                ["visits", "number"],
                ["signups", "number"],
            ],
        },
        expected=[
            {k: r[k] for k in ("date", "revenue", "visits", "signups")} for r in top
        ],
        data={"metric_window": "daily", "rows": rows},
    )


def ex_repos():
    repos = B["repositories"]["repositories"][:30]
    res = sorted(
        (
            {
                "name": r["name"],
                "language": r["language"],
                "stars": r["stars"],
                "license": r["license"],
            }
            for r in repos
            if not r["archived"]
            and r["language"] in ("Python", "Rust")
            and r["stars"] > 10000
        ),
        key=lambda x: -x["stars"],
    )
    return dict(
        slug="repositories-filter",
        title="Developer data: filter repositories",
        description="30 repositories with topic lists. Multi-condition filter and sort.",
        question=(
            "List the repositories that are not archived, are written in Python or Rust and "
            "have more than 10,000 stars, sorted by stars (highest first). Include the license."
        ),
        answer={
            "name": "result",
            "fields": [
                ["name", "string"],
                ["language", "string"],
                ["stars", "number"],
                ["license", "string"],
            ],
        },
        expected=res,
        data={"repositories": repos},
    )


def ex_tickets():
    customers = ["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark", "Wayne"]
    subjects = [
        "Login fails after password reset",
        "Invoice shows wrong VAT",
        "Export to Excel times out",
        "Webhook not delivered",
        "Cannot invite new users",
        "Dashboard is slow",
        "API returns 500 on /orders",
        "Data missing after import",
    ]
    agents = ["Ola", "Piotr", "Kasia", None]
    tickets = []
    start = dt.date(2026, 10, 1)
    for i in range(1, 26):
        tickets.append(
            {
                "id": f"T-{2400 + i}",
                "priority": R.choice(["low", "normal", "normal", "high", "urgent"]),
                "status": R.choice(["open", "open", "pending", "closed"]),
                "customer": R.choice(customers),
                "subject": R.choice(subjects),
                "created": (start + dt.timedelta(days=R.randint(0, 21))).isoformat(),
                "assignee": R.choice(agents),
            }
        )
    res = sorted(
        (
            {k: t[k] for k in ("id", "priority", "customer", "subject", "created")}
            for t in tickets
            if t["status"] == "open"
            and t["priority"] in ("high", "urgent")
            and t["assignee"] is None
        ),
        key=lambda x: (x["created"], x["id"]),
    )
    return dict(
        slug="support-triage",
        title="Support: unassigned urgent tickets",
        description="25 support tickets with nulls. Triage filter.",
        question=(
            "Which open tickets with priority high or urgent have no assignee? Sort them by "
            "created date, oldest first."
        ),
        answer={
            "name": "result",
            "fields": [
                ["id", "string"],
                ["priority", "string"],
                ["customer", "string"],
                ["subject", "string"],
                ["created", "string"],
            ],
        },
        expected=res,
        data={"tickets": tickets},
    )


def ex_inventory():
    cats = {
        "Peripherals": ["Keyboard", "Mouse", "Headset", "Webcam"],
        "Displays": ['Monitor 24"', 'Monitor 27"', "Monitor arm"],
        "Cables": ["USB-C cable", "HDMI cable", "Ethernet cable"],
        "Office": ["Desk lamp", "Notebook", "Chair mat"],
    }
    products = []
    i = 0
    for cat, names in cats.items():
        for name in names:
            for variant in ("", " Pro"):
                i += 1
                if i > 25:
                    break
                reorder = R.choice([10, 20, 30, 50])
                products.append(
                    {
                        "sku": f"{cat[:2].upper()}-{100 + i}",
                        "name": name + variant,
                        "category": cat,
                        "stock": R.randint(0, 80),
                        "reorder_level": reorder,
                        "daily_sales": R.choice([0.5, 1, 1.5, 2, 3, 4]),
                        "supplier": R.choice(
                            ["Nordic Supply", "EuroParts", "TechSource"]
                        ),
                    }
                )
    res = []
    for p in products:
        if p["stock"] < p["reorder_level"]:
            res.append(
                {
                    "sku": p["sku"],
                    "name": p["name"],
                    "stock": p["stock"],
                    "order_qty": max(0, math.ceil(30 * p["daily_sales"] - p["stock"])),
                }
            )
    return dict(
        slug="inventory-reorder",
        title="Inventory: what to reorder and how much",
        description="25 products. Comparison between two fields plus arithmetic.",
        question=(
            "Which products have stock below their reorder_level? For each, suggest an order "
            "quantity that covers 30 days of sales: 30 × daily_sales − stock, rounded up."
        ),
        answer={
            "name": "result",
            "fields": [
                ["sku", "string"],
                ["name", "string"],
                ["stock", "number"],
                ["order_qty", "number"],
            ],
        },
        expected=res,
        data={"products": products},
    )


def ex_calendar():
    people = ["Ada", "Alan", "Grace"]
    days = ["Mon", "Tue", "Wed"]
    titles = [
        "Standup",
        "1:1",
        "Planning",
        "Customer call",
        "Focus time",
        "Review",
        "Lunch",
    ]
    events = []
    for p in people:
        for d in days:
            hours = sorted(R.sample(range(9, 17), 3))
            for h in hours:
                length = R.choice([30, 60, 60, 90])
                start = dt.datetime(2026, 1, 1, h, R.choice([0, 0, 30]))
                end = start + dt.timedelta(minutes=length)
                if end.hour > 17 or (end.hour == 17 and end.minute > 0):
                    end = start.replace(hour=17, minute=0)
                events.append(
                    {
                        "person": p,
                        "day": d,
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M"),
                        "title": R.choice(titles),
                    }
                )

    def busy(h):
        s, e = h * 60, (h + 1) * 60
        for ev in events:
            if ev["day"] != "Tue":
                continue
            a = int(ev["start"][:2]) * 60 + int(ev["start"][3:])
            b = int(ev["end"][:2]) * 60 + int(ev["end"][3:])
            if a < e and b > s:
                return True
        return False

    free = [
        {"day": "Tue", "start": f"{h:02d}:00", "end": f"{h + 1:02d}:00"}
        for h in range(9, 17)
        if not busy(h)
    ]
    return dict(
        slug="calendar-free-slots",
        title="Scheduling: find a common free hour",
        description="Calendar events of three people. Reasoning over time intervals.",
        question=(
            "Working hours are 09:00–17:00. List every 1-hour slot starting on the full hour on "
            "Tue when Ada, Alan and Grace are all free (no event overlaps the slot)."
        ),
        answer={
            "name": "result",
            "fields": [["day", "string"], ["start", "string"], ["end", "string"]],
        },
        expected=free,
        data={"workday": {"start": "09:00", "end": "17:00"}, "events": events},
    )


def ex_extraction():
    rows = [
        ("Marta Nowak", "Keyboard", 3, "2026-11-04"),
        ("Jan Kowalski", 'Monitor 27"', 1, "2026-11-06"),
        ("Acme Sp. z o.o.", "USB-C cable", 25, "2026-11-03"),
        ("Ola Wiśniewska", "Headset", 2, "2026-11-10"),
    ]
    bodies = [
        "Hi, please send 3 keyboards to our Kraków office. We need them by 4 November 2026. Thanks, Marta Nowak",
        "Hello — Jan Kowalski here. I'd like to order one 27-inch monitor (Monitor 27\"), delivery on 2026-11-06 if possible.",
        "Order from Acme Sp. z o.o.: 25 × USB-C cable. Delivery: 3rd of November 2026. Invoice to the usual address.",
        "Could you ship two headsets for Ola Wiśniewska? Delivery date: Nov 10, 2026. Thank you!",
    ]
    emails = [
        {
            "from": f"customer{i + 1}@example.com",
            "subject": f"Order request #{i + 1}",
            "body": b,
        }
        for i, b in enumerate(bodies)
    ]
    return dict(
        slug="email-extraction",
        title="Extraction: emails to structured orders (output format)",
        description="Free text in, structured data out. Shows the answer format saving output tokens.",
        question=(
            "Extract every order from these emails: the customer name, the product (as named "
            'in our catalogue: Keyboard, Monitor 27", USB-C cable, Headset), the quantity and '
            "the delivery date as YYYY-MM-DD."
        ),
        answer={
            "name": "orders",
            "fields": [
                ["customer", "string"],
                ["product", "string"],
                ["quantity", "number"],
                ["delivery_date", "string"],
            ],
        },
        expected=[
            {"customer": c, "product": p, "quantity": q, "delivery_date": d}
            for c, p, q, d in rows
        ],
        data={"emails": emails},
    )


BUILDERS = [
    ex_employees,
    ex_orders,
    ex_logs,
    ex_search,
    ex_analytics,
    ex_repos,
    ex_tickets,
    ex_inventory,
    ex_calendar,
    ex_extraction,
]


def main():
    from arkadia.bench import catalog

    PKG_DIR.mkdir(parents=True, exist_ok=True)
    for old in PKG_DIR.glob("*.json"):
        old.unlink()
    base = []
    for build in BUILDERS:
        ex = {"expected_note": "", **build()}
        assert akd.loads(akd.dumps(ex["data"])) == ex["data"]
        base.append(ex)
    keys = (
        "id",
        "slug",
        "title",
        "description",
        "tags",
        "needs_meta",
        "question",
        "answer",
        "expected",
        "expected_note",
    )
    for ex in catalog.catalogue(base):
        meta = ex.pop("meta")
        ex["akd_meta"] = catalog.annotate(ex["data"], meta) if meta else None
        ex["notes"] = catalog.notes(ex["data"], meta)
        ordered = {k: ex[k] for k in keys}
        ordered.update({k: ex[k] for k in ("notes", "akd_meta", "data")})
        (PKG_DIR / f"{ex['id']:02d}-{ex['slug']}.json").write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # Feature examples: the gallery snippets (one part of the format each).
    gallery = json.loads(
        (RUST_FILE.parent / "gallery.json").read_text(encoding="utf-8")
    )
    slugs = {p.stem.split("-", 1)[1] for p in PKG_DIR.glob("*.json")}
    next_id = len(slugs) + 1
    for g in gallery:
        source = g.get("akd")
        data = g["data"] if "data" in g else akd.loads(source)
        notes = (
            catalog.notes_from_text(source)
            if source
            else {"comments": [], "attributes": []}
        )
        has_meta = bool(notes["comments"] or notes["attributes"])
        slug = g["slug"] if g["slug"] not in slugs else f"feature-{g['slug']}"
        ex = {
            "id": next_id,
            "slug": slug,
            "title": g["title"],
            "description": g["shows"],
            "tags": ["feature"] + (["metadata"] if has_meta else []),
            "needs_meta": False,
            "question": g["question"],
            "answer": g["answer"],
            "expected": g["expected"],
            "expected_note": "",
            "notes": notes,
            "akd_meta": layout.compact(source) if has_meta else None,
            "akd": layout.compact(source) if source else None,
            "data": data,
        }
        (PKG_DIR / f"{next_id:02d}-{slug}.json").write_text(
            json.dumps(ex, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        next_id += 1

    RUST_FILE.parent.mkdir(parents=True, exist_ok=True)
    bundled_examples = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(PKG_DIR.glob("*.json"))
    ]
    RUST_FILE.write_text(
        json.dumps(bundled_examples, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )

    matrix = example_matrix()
    index, details = matrix["index"], matrix["details"]
    if OUT_DIR.exists():
        for old in list(OUT_DIR.glob("*/*.txt")) + list(OUT_DIR.glob("*/*.json")):
            old.unlink()
        for d in sorted(OUT_DIR.glob("*")):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "examples.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    n_meta = sum(1 for e in index["examples"] if "metadata" in e["tags"])
    n_needs = sum(1 for e in index["examples"] if "needs metadata" in e["tags"])
    lines = [
        "# Copy-paste prompt examples",
        "",
        f"{len(details)} prompts with data, a question and the expected answer, in JSON, TOON,",
        "AK-DATA and AK-DATA COMPACT. Paste one into ChatGPT, Gemini, Claude or any chat",
        "model and compare the answers and the token counts. Every AK-DATA prompt contains",
        "the format definition, so no setup is needed.",
        "",
        f"{n_meta} examples carry **metadata** — the same facts as `$attributes`/`#tags` and as",
        "`/* comments */` (for JSON and TOON: notes before the data). Each prompt can be",
        "built with attributes, with comments, with both or without:",
        "`ak-data prompt --example 11 --attributes --comments`. In",
        f"{n_needs} of them the question can only be answered with the metadata (*needs",
        "metadata*): what a code means, a unit, which records are tests.",
        "",
        "Each folder has the prompt in every format (`json.txt`, `toon.txt`, `ak-data.txt`,",
        "`ak-data-compact.txt`; with attributes and comments: `*.meta.txt`), the expected",
        "answer and `prompts.json` with every combination. Regenerate with `make examples`.",
        "",
        f"Prompt tokens ({index['tokenizer']}, format definition included):",
        "",
        "| # | example | tags | "
        + " | ".join(FORMAT_NAMES[k] for k in index["formats"])
        + " | AK-DATA COMPACT + metadata |",
        "|---|---|---|" + "---:|" * (len(index["formats"]) + 1),
    ]
    for d in details:
        folder = OUT_DIR / f"{d['id']:02d}-{d['slug']}"
        folder.mkdir(exist_ok=True)
        for k, by_combo in d["prompts"].items():
            (folder / f"{FILE_NAMES[k]}.txt").write_text(
                by_combo["none"], encoding="utf-8"
            )
            if "both" in by_combo:
                (folder / f"{FILE_NAMES[k]}.meta.txt").write_text(
                    by_combo["both"], encoding="utf-8"
                )
        (folder / "expected.json").write_text(
            d["expected_answers"]["json"] + "\n", encoding="utf-8"
        )
        (folder / "expected.ak-data.txt").write_text(
            d["expected_answers"]["akcd"] + "\n", encoding="utf-8"
        )
        (folder / "prompts.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        t = d["tokens"]
        meta = f"{t['akcd']['both']:,}" if "both" in t["akcd"] else "–"
        lines.append(
            f"| {d['id']} | [{d['title']}]({folder.name}/) | {', '.join(d['tags'])} | "
            + " | ".join(f"{t[k]['none']:,}" for k in index["formats"])
            + f" | {meta} |"
        )
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-6:]))


if __name__ == "__main__":
    main()
