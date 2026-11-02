"""
Datasets bundled with arkadia-data, and loading of user directories.

The bundled set (see scripts/make_datasets.py) models what agents move
around: tabular records, nested business objects, tool results, retrieval
chunks, logs, configuration and time series.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any, List, Optional

BUNDLED_DIR = pathlib.Path(__file__).resolve().parent / "datasets"

DESCRIPTIONS = {
    "employees": "100 flat records (tabular)",
    "orders": "40 orders with nested customer and item lists",
    "tool-results": "web search tool output with 30 results",
    "rag-chunks": "24 retrieval chunks with long text",
    "logs": "150 log events (tabular)",
    "repositories": "50 repositories with topic lists",
    "config": "irregular nested configuration",
    "analytics": "90 days of metrics (time series)",
}


@dataclass
class Dataset:
    name: str
    data: Any
    source: str
    description: str = ""
    reference: Optional[str] = None  # hand-written .ak-data next to the JSON


def bundled() -> List[Dataset]:
    return load_dir(BUNDLED_DIR, bundled_set=True)


def load_dir(directory: pathlib.Path, bundled_set: bool = False) -> List[Dataset]:
    """
    Every *.json file in `directory` (not recursive). A file named like the
    JSON but ending in .ak-data or .akd is kept as a decode reference.
    """
    directory = pathlib.Path(directory).expanduser()
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")
    out = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path.name}: not valid JSON ({exc})") from exc
        ref = None
        for ext in (".ak-data", ".akd"):
            candidate = path.with_suffix(ext)
            if candidate.exists():
                ref = candidate.read_text(encoding="utf-8")
                break
        out.append(
            Dataset(
                name=path.stem,
                data=data,
                source="bundled" if bundled_set else str(path),
                description=DESCRIPTIONS.get(path.stem, "") if bundled_set else "",
                reference=ref,
            )
        )
    return out


def resolve(directory: Optional[str]) -> List[Dataset]:
    """Datasets for a benchmark: the user's directory, or the bundled set."""
    if directory:
        sets = load_dir(pathlib.Path(directory))
        if not sets:
            raise FileNotFoundError(f"No *.json files in {directory}")
        return sets
    return bundled()
