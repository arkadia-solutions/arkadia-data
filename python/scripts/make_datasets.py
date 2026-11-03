"""
Regenerates the datasets bundled with arkadia-data (src/arkadia/bench/datasets).

They are deterministic (fixed seed) and model the payloads agents actually
move around: tool results, tabular records, nested business objects, logs,
retrieval chunks, configuration and time series. Run:

    python scripts/make_datasets.py
"""

import json
import pathlib
import random

OUT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "arkadia"
    / "bench"
    / "datasets"
)
R = random.Random(20261022)

FIRST = [
    "Ada",
    "Alan",
    "Grace",
    "Linus",
    "Margaret",
    "Dennis",
    "Barbara",
    "Ken",
    "Frances",
    "Edsger",
    "Radia",
    "Tim",
    "Katherine",
    "John",
    "Hedy",
    "Donald",
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
    "Allen",
    "Dijkstra",
    "Perlman",
    "Berners-Lee",
    "Johnson",
    "Backus",
    "Lamarr",
    "Knuth",
]
DEPTS = ["Engineering", "Sales", "Marketing", "Support", "Finance", "Research"]
CITIES = ["Warsaw", "Kraków", "Berlin", "London", "Lisbon", "Austin", "Toronto"]


def employees(n=100):
    rows = []
    for i in range(1, n + 1):
        first, last = R.choice(FIRST), R.choice(LAST)
        rows.append(
            {
                "id": i,
                "name": f"{first} {last}",
                "email": f"{first.lower()}.{last.lower().replace('-', '')}{i}@example.com",
                "department": R.choice(DEPTS),
                "city": R.choice(CITIES),
                "salary": R.randrange(48_000, 190_000, 500),
                "active": R.random() > 0.15,
                "hired": f"20{R.randint(12, 26):02d}-{R.randint(1, 12):02d}-{R.randint(1, 28):02d}",
            }
        )
    return {"employees": rows}


def orders(n=40):
    skus = [
        ("KB-01", "Keyboard", 89.0),
        ("MS-02", "Mouse", 39.5),
        ("MN-27", 'Monitor 27"', 319.0),
        ("HD-10", "Headset", 129.9),
        ("CB-USB", "USB-C cable", 12.0),
        ("DK-05", "Dock", 199.0),
    ]
    out = []
    for i in range(1, n + 1):
        items = []
        for sku, title, price in R.sample(skus, R.randint(1, 4)):
            items.append(
                {"sku": sku, "title": title, "qty": R.randint(1, 3), "price": price}
            )
        total = round(sum(it["qty"] * it["price"] for it in items), 2)
        first, last = R.choice(FIRST), R.choice(LAST)
        out.append(
            {
                "id": f"ORD-{1000 + i}",
                "status": R.choice(
                    ["paid", "shipped", "delivered", "refunded", "pending"]
                ),
                "customer": {
                    "id": R.randint(1, 60),
                    "name": f"{first} {last}",
                    "country": R.choice(["PL", "DE", "GB", "PT", "US", "CA"]),
                },
                "items": items,
                "total": total,
                "note": R.choice(
                    [
                        None,
                        None,
                        "Leave at the door",
                        "Gift wrap, please",
                        "Invoice to company",
                    ]
                ),
            }
        )
    return {"orders": out}


def tool_results():
    topics = [
        "vector database",
        "token budget",
        "agent memory",
        "tool calling",
        "context window",
    ]
    results = []
    for i in range(1, 31):
        t = R.choice(topics)
        results.append(
            {
                "rank": i,
                "title": f"How teams manage {t} in production ({2024 + i % 3})",
                "url": f"https://example.org/articles/{t.replace(' ', '-')}-{i}",
                "snippet": f"A practical look at {t}: trade-offs, costs and what changed for agents.",
                "score": round(1 - i * 0.027, 3),
                "published": f"2026-{R.randint(1, 9):02d}-{R.randint(1, 28):02d}",
            }
        )
    return {
        "tool": "web_search",
        "query": "managing context for AI agents",
        "took_ms": 412,
        "results": results,
    }


def rag_chunks():
    words = (
        "agent context token schema record field model prompt retrieval memory tool "
        "result format compact header value list nested type answer source"
    ).split()
    chunks = []
    for i in range(1, 25):
        text = (
            " ".join(R.choice(words) for _ in range(R.randint(40, 70))).capitalize()
            + "."
        )
        chunks.append(
            {
                "doc_id": f"doc-{R.randint(1, 6)}",
                "chunk": i,
                "page": R.randint(1, 40),
                "score": round(R.uniform(0.55, 0.97), 3),
                "text": text,
            }
        )
    return {"query": "How should an agent store tool results?", "chunks": chunks}


def logs(n=150):
    services = ["api", "auth", "billing", "search", "worker"]
    levels = ["INFO"] * 7 + ["WARN"] * 2 + ["ERROR"]
    msgs = {
        "INFO": "request completed",
        "WARN": "slow response",
        "ERROR": "upstream timeout",
    }
    out = []
    for i in range(n):
        lvl = R.choice(levels)
        out.append(
            {
                "ts": f"2026-10-22T{8 + i // 30:02d}:{(i * 7) % 60:02d}:{(i * 13) % 60:02d}Z",
                "level": lvl,
                "service": R.choice(services),
                "message": msgs[lvl],
                "latency_ms": R.randint(4, 90)
                if lvl == "INFO"
                else R.randint(400, 4000),
                "status": 200 if lvl != "ERROR" else 504,
            }
        )
    return {"logs": out}


def repos(n=50):
    langs = ["Python", "TypeScript", "Rust", "Go", "Java", "C++"]
    tags = [
        "ai",
        "agents",
        "llm",
        "parser",
        "cli",
        "database",
        "web",
        "tooling",
        "security",
    ]
    out = []
    for i in range(1, n + 1):
        out.append(
            {
                "name": f"{R.choice(['open', 'fast', 'tiny', 'deep', 'smart'])}-{R.choice(['agent', 'parser', 'store', 'kit', 'flow'])}-{i}",
                "stars": R.randint(10, 90_000),
                "forks": R.randint(0, 9_000),
                "language": R.choice(langs),
                "license": R.choice(["MIT", "Apache-2.0", "GPL-3.0", None]),
                "topics": R.sample(tags, R.randint(1, 4)),
                "archived": R.random() < 0.08,
            }
        )
    return {"repositories": out}


def config():
    return {
        "service": "arkadia-workspace",
        "version": "2.4.1",
        "features": {
            "ai": True,
            "office": True,
            "sync": {"enabled": True, "interval_s": 30},
        },
        "agents": [
            {
                "name": "planner",
                "model": "large",
                "tools": ["search", "files", "calendar"],
                "max_steps": 12,
            },
            {
                "name": "writer",
                "model": "medium",
                "tools": ["files"],
                "temperature": 0.4,
            },
            {
                "name": "reviewer",
                "model": "large",
                "tools": [],
                "policy": {"require_sources": True},
            },
        ],
        "limits": {
            "tokens_per_task": 120000,
            "parallel_tasks": 4,
            "retries": [1, 5, 30],
        },
        "storage": {
            "path": "~/.arkadia",
            "ignore": [".git", "node_modules", "*.tmp"],
            "encryption": None,
        },
    }


def analytics(days=90):
    import datetime

    start = datetime.date(2026, 7, 1)
    out = []
    for d in range(days):
        visits = R.randint(800, 4000)
        out.append(
            {
                "date": (start + datetime.timedelta(days=d)).isoformat(),
                "visits": visits,
                "signups": R.randint(5, visits // 40),
                "revenue": round(R.uniform(200, 6000), 2),
                "bounce_rate": round(R.uniform(0.25, 0.7), 3),
            }
        )
    return {"metric_window": "daily", "rows": out}


DATASETS = {
    "employees": employees,
    "orders": orders,
    "tool-results": tool_results,
    "rag-chunks": rag_chunks,
    "logs": logs,
    "repositories": repos,
    "config": config,
    "analytics": analytics,
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in DATASETS.items():
        path = OUT / f"{name}.json"
        path.write_text(
            json.dumps(fn(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            "wrote",
            path.relative_to(OUT.parent.parent.parent),
            path.stat().st_size,
            "bytes",
        )
