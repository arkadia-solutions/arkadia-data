import pathlib

try:
    from arkadia.data import __version__ as LIB_VERSION
except ImportError:
    LIB_VERSION = "0.0.0-dev"

# --- CONFIGURATION ---
DATA_DIR = pathlib.Path("data")
MODEL = "gpt-4o-mini"  # Model used for token counting and AI tests
REPEATS = 50  # Number of repetitions for time measurement
BAR_WIDTH = 25


VERSION = LIB_VERSION
TOOL_CMD = "ak-data / akd"
TOOL_NAME = "Arkadia Data Tool"
DESCRIPTION = "Unified interface for AK Data Format operations (Encoding, Decoding, Benchmarking)."

MET_INFO = {"Model": MODEL, "Repeats": str(REPEATS), "Data Dir": str(DATA_DIR)}
