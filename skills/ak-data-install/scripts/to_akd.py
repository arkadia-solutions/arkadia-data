#!/usr/bin/env python3
"""
Convert JSON to AK-DATA (Arkadia Data Format) and report the token change.

    python to_akd.py data.json [--pretty] [--prompt] [--quiet]
    python to_akd.py - < data.json

Requires `pip install arkadia-data` (add `[bench]` for exact token counts).
"""

import argparse
import json
import sys

try:
    import arkadia.data as akd
except ImportError:
    sys.exit("arkadia-data is not installed: pip install arkadia-data")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("path", help="JSON file, or - for stdin")
    p.add_argument("--pretty", action="store_true", help="readable multi-line output")
    p.add_argument(
        "--prompt", action="store_true", help="wrap in a block with the format hint"
    )
    p.add_argument("--quiet", action="store_true", help="print only the AK-DATA")
    args = p.parse_args()

    raw = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
    data = json.loads(raw)
    if args.prompt:
        out = akd.to_prompt(data, compact=not args.pretty)
    else:
        out = akd.encode(data, {"compact": not args.pretty, "escape_new_lines": not args.pretty})
    assert akd.loads(akd.dumps(data)) == data, "round-trip check failed"
    print(out)
    if not args.quiet:
        before = akd.count_tokens(json.dumps(data, ensure_ascii=False, indent=2))
        after = akd.count_tokens(out)
        approx = "" if akd.get_tokenizer().exact else " (approx.)"
        print(
            f"\n# tokens{approx}: JSON {before:,} -> AK-DATA {after:,} "
            f"({(after - before) / max(before, 1) * 100:+.1f}%)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
