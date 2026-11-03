import json
from pathlib import Path

import arkadia.data as ak


def test_shared_semantic_corpus():
    cases = json.loads(
        (Path(__file__).parent / "fixtures/conformance.json").read_text()
    )["cases"]
    for data in cases:
        for indent in [None, 2]:
            assert ak.loads(ak.dumps(data, indent=indent)) == data
