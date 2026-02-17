import sys
import json
import time
import re
import pathlib
from typing import Any, Dict, List

# --- ARKADIA IMPORTS ---
import arkadia.cli as cli
from arkadia.cli.colors import C
from arkadia.cli.aid.meta import VERSION, TOOL_NAME

# Try importing Arkadia AI core
try:
    import arkadia.ai as ai
except ImportError:
    ai = None

# Optional imports for other formats
try:
    import yaml
except ImportError:
    yaml = None

try:
    import toon_format as toon_format
except ImportError:
    toon_format = None


# ==============================================================================
# HELP & UI
# ==============================================================================

def show_decode_help():
    """
    Displays the custom help screen for the Decode command.
    """
    cli.print_banner(
        tool_name=f"{TOOL_NAME} DECODER", 
        version=VERSION,
        color=C.MAGENTA, 
        description="Parses Arkadia AI Data Format (.aid) files and converts them to JSON, YAML, TOON or re-formatted AID."
    )
    
    cli.print_usage("aid dec", "[flags] [input_file]", "")

    # 1. Positional Arguments
    args_list = [
        {"flags": "input_file", "desc": "Path to source file (.aid) or '-' for stdin. Reads from stdin if omitted."}
    ]
    cli.print_options("Arguments", args_list)

    # 2. I/O & Formats
    io_flags = [
        {"flags": "-o, --output <file>", "desc": "Write output to file instead of stdout"},
        {"flags": "-f, --format <fmt>",  "desc": "Output format: json, yaml, toon, aid", "default": "json"},
        {"flags": "--only-data",         "desc": "Output raw data only (suppress stats/logs)"},
    ]
    cli.print_options("I/O Options", io_flags)

    # 3. Formatting (Applies to JSON & AID output)
    fmt_flags = [
        {"flags": "--indent <int>",           "desc": "Indentation level", "default": "2"},
        {"flags": "--compact",                "desc": "Compact mode (minified)"},

        # TOON Specific
        {"flags": "--delimiter <char>",       "desc": "[TOON] Array delimiter (default: comma)"},
        {"flags": "--length-marker",          "desc": "[TOON] Add length marker (#) to arrays"},

        # AID Specific
        {"flags": "--start-indent <int>",     "desc": "[AID] Initial base indentation", "default": "0"},
        {"flags": "--escape-newlines",        "desc": "[AID] Escape \\n characters"},
        {"flags": "--no-comments",            "desc": "[AID] Do not include comments"},
        {"flags": "--include-array-size",     "desc": "[AID] Add @size=N annotation"},
        {"flags": "--no-schema",              "desc": "[AID] Disable inline schema headers"},
        {"flags": "--no-type",                "desc": "[AID] Disable type annotations"},
        {"flags": "--prompt-output",          "desc": "[AID] Optimize for LLM prompting"},
    ]
    cli.print_options("Formatting Options", fmt_flags)

    # 4. Debugging & Color
    debug_flags = [
        {"flags": "--debug",             "desc": "Enable verbose parser logging"},
        {"flags": "--colorize",          "desc": "Force syntax highlighting"},
        {"flags": "--no-color",          "desc": "Disable syntax highlighting"},
    ]
    cli.print_options("Debugging", debug_flags)

    # 5. Global
    global_flags = [
        {"flags": "-h, --help", "desc": "Show this help message"}
    ]
    cli.print_options("Global Options", global_flags)


# ==============================================================================
# LOGIC HANDLERS
# ==============================================================================

def determine_color_mode(args) -> bool:
    """
    Determines if output should be colorized.
    """
    if args.no_color:
        return False
    if args.colorize:
        return True
    # Default to color enabled for stdout, disabled for file output
    return False if args.output else True


def highlight_output(text: str, fmt: str) -> str:
    """
    Simple regex-based syntax highlighter for terminal output.
    """
    if fmt == "json":
        # Keys
        text = re.sub(r'(".*?")(\s*:)', f'{C.CYAN}\\1{C.RESET}\\2', text)
        # Strings values
        text = re.sub(r':\s*(".*?")', f': {C.GREEN}\\1{C.RESET}', text)
        # Numbers/Bool/Null
        text = re.sub(r':\s*(-?\d+\.?\d*|true|false|null)', f': {C.BLUE}\\1{C.RESET}', text)
        return text
    
    elif fmt == "yaml":
        # Keys
        text = re.sub(r'(^[\s-]*)([\w_]+)(:)', f'\\1{C.CYAN}\\2{C.RESET}\\3', text, flags=re.MULTILINE)
        return text

    elif fmt == "toon":
        # Keys in headers
        text = re.sub(r'([\w_]+)(:)', f'{C.CYAN}\\1{C.RESET}\\2', text)
        return text

    return text


def run(args):
    """
    Main execution entry point for the Decode command.
    """
    content = ""
    source_label = "STDIN"

    # 1. Input Resolution (File vs Stdin)
    # Check if input arg is provided and is NOT "-" (which explicitly means stdin)
    if args.input and args.input != "-":
        input_path = pathlib.Path(args.input)
        if not input_path.exists():
            print(f"{C.RED}Error: File not found: {input_path}{C.RESET}", file=sys.stderr)
            sys.exit(1)
        
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()
            source_label = str(input_path)
        except Exception as e:
            print(f"{C.RED}Error reading file:{C.RESET} {e}", file=sys.stderr)
            sys.exit(1)
    
    # Handle Stdin (explicit '-' or implicit pipe)
    else:
        # Check if data is actually being piped or if '-' was used
        if not sys.stdin.isatty() or args.input == "-":
            try:
                content = sys.stdin.read()
            except Exception as e:
                print(f"{C.RED}Error reading stdin:{C.RESET} {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # No file provided and no piped data -> Show Help
            print(f"{C.RED}Error: Input required (file or stdin).{C.RESET}", file=sys.stderr)
            show_decode_help()
            sys.exit(1)

    if not content:
        print(f"{C.RED}Error: Input is empty.{C.RESET}", file=sys.stderr)
        sys.exit(1)

    # 3. Decode (AID -> Node)
    if ai is None:
        print(f"{C.RED}Critical Error: arkadia.ai module not found.{C.RESET}", file=sys.stderr)
        sys.exit(1)

    start_time = time.perf_counter()
    
    try:
        result = ai.data.decode(content, debug=args.debug)
        node = result.node
        errors = result.errors
    except Exception as e:
        print(f"{C.RED}Critical Parser Exception:{C.RESET} {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    duration = (time.perf_counter() - start_time) * 1000

    # 4. Handle Errors
    if errors:
        print(f"\n{C.RED}Decoding Failed with {len(errors)} Errors:{C.RESET}", file=sys.stderr)
        for i, err in enumerate(errors):
            pos = getattr(err, 'position', '?')
            msg = getattr(err, 'message', str(err))
            ctx = getattr(err, 'context', None)
            
            print(f"  {i+1}. [Pos {pos}] {msg}", file=sys.stderr)
            if ctx:
                print(f"     Context: {C.YELLOW}{ctx.strip()}{C.RESET}", file=sys.stderr)
        sys.exit(1)


    # 5. Format Output
    output_text = ""
    fmt = args.format.lower()


    # 6. Convert Node to Standard Python Structure
    try:
        if fmt != "aid":
            py_data = node.dict()
        else:
            py_data = node  # Keep as Node for re-encoding
    except Exception as e:
        print(f"{C.RED}Error converting Node to Python object:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)

    # Determine color usage
    use_color = determine_color_mode(args)

    try:
        if fmt == "json":
            output_text = json.dumps(py_data, indent=args.indent if not args.compact else None, ensure_ascii=False)
            if use_color:
                output_text = highlight_output(output_text, "json")

        elif fmt == "yaml":
            if yaml is None:
                raise ImportError("PyYAML not installed. Run: pip install pyyaml")
            output_text = yaml.dump(py_data, sort_keys=False, indent=args.indent)
            if use_color:
                output_text = highlight_output(output_text, "yaml")

        elif fmt == "toon":
            if toon_format is None:
                raise ImportError("toon_format not installed.")
            # Prepare TOON options
            toon_options = {
                "indent": args.indent,
                "delimiter": args.delimiter,  # Passed from CLI or default ','
                "lengthMarker": "#" if args.length_marker else False
            }
            output_text = toon_format.encode(py_data, options=toon_options)
            if use_color:
                output_text = highlight_output(output_text, "toon")

        elif fmt == "aid":
            # Re-encode back to AID with specific parameters
            config = {
                "indent": args.indent,
                "start_indent": args.start_indent,
                "compact": args.compact,
                "escape_new_lines": args.escape_newlines,
                "colorize": use_color,
                "include_comments": not args.no_comments,
                "include_array_size": args.include_array_size,
                "include_schema": not args.no_schema,
                "include_type": not args.no_type,
                "prompt_output": args.prompt_output
            }
            output_text = ai.data.encode(py_data, config)

        else:
            print(f"{C.RED}Unknown format: {fmt}{C.RESET}", file=sys.stderr)
            sys.exit(1)

    except ImportError as e:
        print(f"{C.RED}Format Error:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{C.RED}Serialization Error:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)

    # 7. Output Handling
    if args.output:
        try:
            out_path = pathlib.Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output_text)
            
            # Print stats only if NOT in data-only mode
            if not args.only_data:
                print(f"{C.GREEN}Success!{C.RESET} Decoded {fmt.upper()} saved to: {C.BOLD}{out_path}{C.RESET}")
                print(f"{C.DIM}Time: {duration:.2f}ms{C.RESET}")
            
        except Exception as e:
            print(f"{C.RED}Error writing output:{C.RESET} {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Print to stdout
        print(output_text)
        
        # Print summary to stderr (so it doesn't pollute piped output)
        if not args.only_data:
            print(f"\n{C.DIM}Decoded in {duration:.2f}ms{C.RESET}", file=sys.stderr)


# ==============================================================================
# ARGUMENT REGISTRATION
# ==============================================================================

def register_arguments(parser):
    """
    Registers arguments for the 'dec' command.
    """
    # Positional
    parser.add_argument("input", nargs="?", help="Input file path")

    # I/O
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-f", "--format", default="json", choices=["json", "yaml", "toon", "aid"], help="Output format")
    parser.add_argument("--only-data", action="store_true", help="Suppress stats")

    # Formatting (Applies to AID re-encoding and JSON)
    parser.add_argument("--indent", type=int, default=2, help="Indentation")
    parser.add_argument("--start-indent", type=int, default=0, help="Start indentation")
    parser.add_argument("-c", "--compact", action="store_true", help="Compact mode")

    # TOON Specific
    parser.add_argument("--delimiter", default=",", help="[TOON] Array delimiter (default: ,)")
    parser.add_argument("--length-marker", action="store_true", help="[TOON] Add length marker (#)")
    parser.add_argument("--escape-newlines", action="store_true", help="[AID] Escape \\n")
    parser.add_argument("--no-comments", action="store_true", help="[AID] Do not include comments")
    parser.add_argument("--include-array-size", action="store_true", help="[AID] Add @size")
    parser.add_argument("--no-schema", action="store_true", help="[AID] Disable schema")
    parser.add_argument("--no-type", action="store_true", help="[AID] Disable types")
    parser.add_argument("--prompt-output", action="store_true", help="[AID] LLM Optimized")

    # Debug / Colors
    parser.add_argument("--debug", action="store_true", help="Verbose debug")
    
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument("--colorize", action="store_true", help="Force colors")
    color_group.add_argument("--no-color", action="store_true", help="Disable colors")