import pytest
from arkadia.ai.data.decode import decode
from arkadia.ai.data.encode import encode
from arkadia.ai.data.Node import Node


# ==================================================================================
# 4. ROUND TRIP (Encode -> Decode)
# ==================================================================================


def test_decode_error_on_unstripped_ansi():
    """
    Validates that the Decoder handles ANSI codes gracefully.
    """
    original_data = [{"id": 1, "active": True}, {"id": 2, "active": False}]

    # 1. Encode WITH colors
    encoded_text = encode(
        original_data,
        config={
            "compact": True,
            "include_schema": True,
            "colorize": True,
        },
    )

    # 2. Decode WITHOUT stripping colors (simulate user error)
    res = decode(encoded_text, remove_ansi_colors=False, debug=True)

    # 3. Assertions
    assert len(res.errors) > 0, "Decoder should report errors on raw ANSI codes"
    
    # Optional: Verify error content
    msgs = [e.message for e in res.errors]
    assert any("Unexpected character" in m for m in msgs)






# ==================================================================================
# 5. ERROR HANDLING
# ==================================================================================


def test_error_unclosed_list():
    """Ensures parsing fails for malformed lists."""
    text = "[1, 2, 3"  # Missing closing bracket
    res = decode(text, debug=True)
    assert len(res.errors) > 0
    msg = res.errors[0].message
    assert "Expected" in msg or "got" in msg or "EOF" in msg


def test_error_unexpected_char():
    """Ensures parsing fails for illegal characters."""
    text = "(1, ?)"
    res = decode(text, debug=True)
    assert len(res.errors) > 0
    assert "Unexpected character" in res.errors[0].message
