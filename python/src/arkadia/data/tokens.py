"""
Token counting that never breaks the caller.

tiktoken is optional. Its encodings are downloaded on first use, which fails
offline or behind a strict proxy; in that case (or without tiktoken) counts
fall back to a calibrated character heuristic and are marked approximate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional

# Encodings worth comparing: o200k_base (GPT-4o / GPT-4.1 / GPT-5 / o-series)
# and cl100k_base (GPT-4 / GPT-3.5, and a common proxy for other models).
DEFAULT_ENCODING = "o200k_base"
KNOWN_ENCODINGS = ("o200k_base", "cl100k_base")

_PIECE = re.compile(r" ?[^\W\d_]+| ?\d{1,3}| ?[^\s\w]+[\r\n]*|\s+", re.UNICODE)


@dataclass(frozen=True)
class Tokenizer:
    name: str
    exact: bool
    _count: Callable[[str], int]

    def count(self, text: str) -> int:
        return self._count(text)

    @property
    def label(self) -> str:
        return self.name if self.exact else f"{self.name} (approx.)"


def _approx(text: str) -> int:
    """
    Pre-tokenizer style heuristic (mean error ~5% vs o200k_base on JSON,
    TOON and AK-Data text): a word with its leading space is one token plus
    one per 7 further letters, digits come in groups of three, punctuation
    runs cost one token per 4 characters, each whitespace run one token.
    """
    total = 0
    for piece in _PIECE.findall(text):
        core = piece.lstrip(" ")
        if not core or core[0].isspace() or core[0].isdigit():
            total += 1
        elif core[0].isalpha():
            total += 1 + (len(core) - 1) // 7
        else:
            total += -(-len(core) // 4)
    return total


@lru_cache(maxsize=None)
def get_tokenizer(encoding: str = DEFAULT_ENCODING) -> Tokenizer:
    """
    Returns a tokenizer for `encoding` ("o200k_base", "cl100k_base", a model
    name such as "gpt-4o", or "approx"). Never raises.
    """
    if encoding != "approx":
        try:
            import tiktoken

            try:
                enc = tiktoken.get_encoding(encoding)
            except ValueError:
                enc = tiktoken.encoding_for_model(encoding)
            return Tokenizer(
                enc.name, True, lambda t: len(enc.encode(t, disallowed_special=()))
            )
        except Exception:
            pass
    return Tokenizer(
        encoding if encoding != "approx" else DEFAULT_ENCODING, False, _approx
    )


def count_tokens(text: str, encoding: str = DEFAULT_ENCODING) -> int:
    """Number of tokens in `text` (approximate when tiktoken is unavailable)."""
    return get_tokenizer(encoding).count(text)


def tokenizer_status(encoding: str = DEFAULT_ENCODING) -> Optional[str]:
    """A warning to show the user when counts are approximate, else None."""
    tok = get_tokenizer(encoding)
    if tok.exact:
        return None
    try:
        import tiktoken  # noqa: F401

        return (
            f"tiktoken could not load '{encoding}' (offline?). Token counts are "
            "approximate. Set TIKTOKEN_CACHE_DIR to a folder with cached encodings."
        )
    except ImportError:
        return "tiktoken is not installed (pip install 'arkadia-data[bench]'); token counts are approximate."
