import sys
import json
import pathlib
from typing import Any, Dict

# --- ARKADIA IMPORTS ---
import arkadia.cli as cli
from arkadia.cli.colors import C
from arkadia.cli.aid.meta import VERSION, TOOL_NAME

# Try importing Arkadia AI core
try:
    import arkadia.ai as ai
except ImportError:
    ai = None

# Try importing optional format parsers
try:
    import yaml
except ImportError:
    yaml = None

try:
    import toon_format as toon
except ImportError:
    toon = None


# ==============================================================================
# HELP & UI
# ==============================================================================

def show_encode_help():
    """
    Displays the custom help screen for the Encode command.
    """
    # Header with Cyan/Accent color instead of Red
    cli.print_banner(
        tool_name=f"{TOOL_NAME} ENCODER", 
        version=VERSION,
        color=C.CYAN, 
        description="Converts structured data (JSON, YAML, TOON, AID) into Arkadia AI Data Format (AID)."
    )
    
    cli.print_usage("aid enc", "[flags] [input_file]", "")

    # 1. Positional Arguments
    args_list = [
        {"flags": "input_file", "desc": "Path to source file (.json, .yaml, .yml, .toon .aid) or '-' for JSON stdin."}
    ]
    cli.print_options("Arguments", args_list)

    # 2. Output & Format Options
    io_flags = [
        {"flags": "-o, --output <file>", "desc": "Write output to file instead of stdout"},
        {"flags": "-c, --compact",       "desc": "Enable compact mode (minified, no whitespace)"},
        # {"flags": "--colorize",          "desc": "Force syntax highlighting in terminal output"},
    ]
    cli.print_options("I/O Options", io_flags)


    color_flags = [
        {"flags": "--colorize",          "desc": "Force syntax highlighting (even in files)"},
        {"flags": "--no-color",          "desc": "Disable syntax highlighting (even in terminal)"},
    ]
    cli.print_options("Color Control", color_flags)

    # 3. Encoder Configuration (Advanced)
    enc_flags = [
        {"flags": "--indent <int>",           "desc": "Indentation level", "default": "2"},
        {"flags": "--start-indent <int>",     "desc": "Initial base indentation", "default": "0"},
        {"flags": "--escape-newlines",        "desc": "Escape \\n characters in strings"},
        {"flags": "--no-comments",            "desc": "Do not include comments (if supported)"},
        {"flags": "--include-array-size",     "desc": "Add @size=N annotation to lists"},
        {"flags": "--no-schema",              "desc": "Disable inline schema headers (<...>)"},
        {"flags": "--no-type",                "desc": "Disable type annotations in schema"},
        {"flags": "--no-meta",                "desc": "Disable metadata blocks (/ ... /)"},
        {"flags": "--prompt-output",          "desc": "Optimize output format for LLM prompting"},
    ]
    cli.print_options("Encoder Configuration", enc_flags)

    # 4. Global
    global_flags = [
        {"flags": "-h, --help", "desc": "Show this help message"}
    ]
    cli.print_options("Global Options", global_flags)


# ==============================================================================
# LOGIC HANDLERS
# ==============================================================================

def determine_color_mode(args) -> bool:
    """
    Determines if output should be colorized based on flags and context.
    Priority:
    1. --no-color (Force OFF)
    2. --colorize (Force ON)
    3. Auto: ON if output is stdout, OFF if output is file.
    """
    if args.no_color:
        return False
    if args.colorize:
        return True
    
    # Auto Mode:
    # If writing to a file via -o, default to False.
    # If writing to stdout, default to True.
    return False if args.output else True

def load_data(file_path: pathlib.Path) -> Any:
    """
    Detects file extension and loads data using the appropriate parser.
    """
    ext = file_path.suffix.lower()

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # 1. JSON
    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # 2. YAML
    elif ext in [".yaml", ".yml"]:
        if yaml is None:
            raise ImportError("PyYAML is not installed. Install it with: pip install pyyaml")
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # 2. aid
    elif ext in [".aid"]:
        if ai is None:
            raise ImportError("AI is not installed. Install it with: pip install arkadia-ai-data")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            result = ai.data.decode(content)
            data = result.node
            errors = result.errors
            if errors:
                print(f"\n{C.RED}aid has some errors {len(errors)} Errors:{C.RESET}", file=sys.stderr)
                for i, err in enumerate(errors):
                    pos = getattr(err, 'position', '?')
                    msg = getattr(err, 'message', str(err))
                    ctx = getattr(err, 'context', None)
                    
                    print(f"  {i+1}. [Pos {pos}] {msg}", file=sys.stderr)
                    if ctx:
                        print(f"     Context: {C.YELLOW}{ctx.strip()}{C.RESET}", file=sys.stderr)
            if data is None:
                raise ValueError("Failed to decode aid data.")
            return data


    # 3. TOON
    elif ext == ".toon":
        if toon is None:
            raise ImportError("toon_format is not installed.")
        with open(file_path, "r", encoding="utf-8") as f:
            # Assuming toon.load or toon.decode exists
            content = f.read()
            return toon.decode(content) if hasattr(toon, 'decode') else toon.load(f)

    else:
        raise ValueError(f"Unsupported file extension: {ext}")


def run(args):
    """
    Main execution entry point for the Encode command.
    Expects 'args' to be a namespace from argparse.
    """
    # 1. Validation
    data = None
    # 1. Input Resolution (File vs Stdin)
    if args.input and args.input != "-":
        input_path = pathlib.Path(args.input)
        if not input_path.exists():
            print(f"{C.RED}Error: File not found: {input_path}{C.RESET}", file=sys.stderr)
            sys.exit(1)
        
        try:
            data = load_data(input_path)
        except Exception as e:
            print(f"{C.RED}Error loading file:{C.RESET} {e}", file=sys.stderr)
            sys.exit(1)
    # Handle Stdin (explicit '-' or implicit pipe)
    else:
        # Check if data is actually being piped or if '-' was used
        if not sys.stdin.isatty() or args.input == "-":
            try:
                content = sys.stdin.read()
                data = json.loads(content)  # Assuming stdin is JSON; could add format detection if needed
            except Exception as e:
                print(f"{C.RED}Error reading stdin:{C.RESET} {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # No file provided and no piped data -> Show Help
            print(f"{C.RED}Error: Input required (file or stdin).{C.RESET}", file=sys.stderr)
            sys.exit(1)

    if not data:
        print(f"{C.RED}Error: Input is empty.{C.RESET}", file=sys.stderr)
        sys.exit(1)


    # 3. Prepare Configuration
    # Mapping CLI flags to EncoderConfig dictionary
    config = {
        "indent": args.indent,
        "start_indent": args.start_indent,
        "compact": args.compact,
        "escape_new_lines": args.escape_newlines,
        "colorize": determine_color_mode(args),
        "include_comments": not args.no_comments, # Argument is negative flag
        "include_array_size": args.include_array_size,
        "include_schema": not args.no_schema,  # Argument is negative flag
        "include_type": not args.no_type,      # Argument is negative flag
        "include_meta": not args.no_meta,      # Argument is negative flag
        "prompt_output": args.prompt_output
    }

    # 4. Encode
    try:
        if ai is None:
            print(f"{C.RED}Critical Error: arkadia.ai module not found.{C.RESET}")
            sys.exit(1)

        # Calling the core library function
        result = ai.data.encode(data, config)

    except Exception as e:
        print(f"{C.RED}Encoding failed:{C.RESET} {e}")
        sys.exit(1)

    # 5. Output Handling
    if args.output:
        try:
            out_path = pathlib.Path(args.output)
            # Create parent directories if missing
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result)
            
            print(f"{C.GREEN}Success!{C.RESET} Encoded data saved to: {C.BOLD}{out_path}{C.RESET}")
        except Exception as e:
            print(f"{C.RED}Error writing output:{C.RESET} {e}")
            sys.exit(1)
    else:
        # Print to console
        print(result)


# ==============================================================================
# ARGUMENT REGISTRATION
# ==============================================================================

def register_arguments(parser):
    """
    Registers arguments for the 'enc' command.
    Used by the main aid.py dispatcher if using subparsers, 
    or can be used manually to parse known args.
    """
    # Positional
    parser.add_argument("input", nargs="?", help="Path to source file (.json, .yaml, .yml, .toon .aid)")

    # I/O
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-c", "--compact", action="store_true", help="Compact mode")

    # Color Group (Mutually Exclusive)
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument("--colorize", action="store_true", help="Force syntax highlighting")
    color_group.add_argument("--no-color", action="store_true", help="Disable syntax highlighting")

    # Encoder Config
    parser.add_argument("--indent", type=int, default=2, help="Indentation spaces")
    parser.add_argument("--start-indent", type=int, default=0, help="Start indentation")
    parser.add_argument("--escape-newlines", action="store_true", help="Escape \\n")
    parser.add_argument("--no-comments", action="store_true", help="Do not include comments")
    parser.add_argument("--include-array-size", action="store_true", help="Add @size annotation")
    
    # Negative flags (default True in logic)
    parser.add_argument("--no-schema", action="store_true", help="Disable schema header")
    parser.add_argument("--no-type", action="store_true", help="Disable type annotation")
    parser.add_argument("--no-meta", action="store_true", help="Disable metadata blocks")

    parser.add_argument("--prompt-output", action="store_true", help="LLM prompt optimized")