# tests/utils.py
from typing import Union
from arkadia.ai.data.decode import decode
from arkadia.ai.data.encode import encode
from arkadia.ai.data import Node

def assert_roundtrip(source: Union[str, Node], expected_output: str, debug: bool = True) -> Node:
    """
    Validates encoding consistency (Round-Trip):
    1. If source is text -> decode it to a Node.
    2. Encode Node -> check if it matches expected_output.
    3. Decode the result (encoded_txt) -> check if it remains a valid Node.
    4. Re-encode -> check if the result is stable (idempotent).
    
    Returns the Node so that further logical assertions (field checking) can be performed.
    """
    
    # 1. Prepare Node (if input is raw text)
    if isinstance(source, str):
        res = decode(source, debug=debug)
        assert not res.errors, f"Input decoding errors: {res.errors}"
        node = res.node
    else:
        node = source
    
    # 2. First Encoding
    encoded_1 = encode(node, {"compact": True})
    
    # Debug print to visualize differences in case of failure
    if encoded_1 != expected_output:
        print(f"\n[ROUNDTRIP] Mismatch Pass 1:")
        print(f"EXPECTED: {expected_output}")
        print(f"ACTUAL:   {encoded_1}")

    assert encoded_1 == expected_output

    # 3. Round Trip (Decode the result of the encoding)
    res_2 = decode(encoded_1, debug=debug)
    assert not res_2.errors, f"Re-decoding errors: {res_2.errors}"
    
    # 4. Second Encoding (Idempotency Check)
    encoded_2 = encode(res_2.node, {"compact": True})
    
    if encoded_2 != expected_output:
        print(f"\n[ROUNDTRIP] Mismatch Pass 2 (Consistency):")
        print(f"EXPECTED: {expected_output}")
        print(f"ACTUAL:   {encoded_2}")

    assert encoded_2 == expected_output
    
    return node