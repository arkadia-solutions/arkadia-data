#!/usr/bin/env python3
"""Read-only release gate. Never prints a matching secret value."""

from pathlib import Path
import argparse
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|\b(?:ghp_|github_pat_)[A-Za-z0-9_]{25,}|\bAIza[A-Za-z0-9_-]{30,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
)


def forbidden(path):
    parts = Path(path).parts
    return (
        any(
            p in {"private", "@private", ".venv", "node_modules", "__pycache__"}
            for p in parts
        )
        or any(p.startswith(".env") and p != ".env.example" for p in parts)
        or (parts and parts[0] == "reports")
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    errors = []
    paths = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    for path in filter(None, paths):
        if forbidden(path):
            errors.append(f"Forbidden tracked path: {path}")
        staged = subprocess.check_output(["git", "show", ":" + path], cwd=ROOT)
        if SECRET.search(staged):
            errors.append(f"Secret pattern in index: {path}")
        p = ROOT / path
        if p.is_file() and SECRET.search(p.read_bytes()):
            errors.append(f"Secret pattern in working file: {path}")
    if args.history:
        for row in subprocess.check_output(
            ["git", "rev-list", "--objects", "--all"], cwd=ROOT
        ).splitlines():
            pair = row.split(b" ", 1)
            if len(pair) == 2:
                data = subprocess.check_output(
                    ["git", "cat-file", "-p", pair[0]], cwd=ROOT
                )
                if SECRET.search(data):
                    errors.append(
                        "Secret pattern in history: " + pair[1].decode(errors="replace")
                    )
    source = (ROOT / "python/tests/fixtures/conformance.json").read_bytes()
    for language in ["typescript", "rust"]:
        if (ROOT / language / "tests/fixtures/conformance.json").read_bytes() != source:
            errors.append(f"{language}: shared vectors are stale")
    if errors:
        print("\n".join(errors))
        return 1
    print(
        "PASS: tracked release surface, secret patterns and shared vectors. This is not a full confidential-data classifier."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
