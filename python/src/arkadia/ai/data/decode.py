from .Decoder import Decoder, DecodeResult
from .Node import Node

# =============================================================
# PUBLIC API
# =============================================================


def decode(
    text: str,
    schema: str = "",
    *,
    remove_ansi_colors: bool = False,
    debug: bool = False,
) -> DecodeResult:
    decoder = Decoder(text, schema, remove_ansi_colors, debug)
    return decoder.decode()
