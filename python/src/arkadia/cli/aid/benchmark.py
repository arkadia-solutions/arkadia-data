import sys
import json
import time
import pathlib
import statistics
import os
from typing import List, Dict, Any, Callable

# --- ARKADIA IMPORTS ---
import arkadia.cli as cli
from arkadia.cli.colors import C
from .meta import VERSION, TOOL_NAME

# --- EXTERNAL DEPENDENCIES ---
try:
    import arkadia.ai as ai
except ImportError:
    ai = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

try:
    import toon_format as toon_format
except ImportError:
    toon_format = None



# ==============================================================================
# CONFIG & CONSTANTS
# ==============================================================================

BAR_WIDTH = 25
MODEL_NAME = "gpt-4o-mini" # Used for token counting estimation

class CFORMATS:
    JSON = "\033[38;5;39m"   # Blue
    TOON = "\033[38;5;208m"  # Orange
    AICD = "\033[38;5;118m"  # Bright Green (Compact)
    AID  = "\033[38;5;34m"   # Darker Green (Standard)
    WHITE = "\033[37m"


# ==============================================================================
# HELP & UI
# ==============================================================================

def show_benchmark_help():
    """
    Displays the custom help screen for the Benchmark command.
    """
    cli.print_banner(
        tool_name=f"{TOOL_NAME} BENCHMARK", 
        version=VERSION,
        color=C.YELLOW, 
        description="Runs comprehensive analysis (Visual + Performance) comparing JSON, TOON, AID, and AICD formats."
    )
    
    cli.print_usage("aid ben", "[flags] [directory]", "")

    # 1. Positional Arguments
    args_list = [
        {"flags": "directory", "desc": "Directory containing .json files (default: ./data)"}
    ]
    cli.print_options("Arguments", args_list)

    # 2. Options
    opts = [
        {"flags": "-r, --repeats <n>", "desc": "Number of iterations for timing accuracy (default: 50)"},
        {"flags": "--debug",           "desc": "Show full encoded content in visual step"},
    ]
    cli.print_options("Options", opts)

    # 3. Global
    global_flags = [
        {"flags": "-h, --help", "desc": "Show this help message"}
    ]
    cli.print_options("Global Options", global_flags)


# ==============================================================================
# UTILITIES
# ==============================================================================

def get_tokenizer():
    """Safely retrieves a tokenizer."""
    if not tiktoken:
        return None
    try:
        return tiktoken.encoding_for_model(MODEL_NAME)
    except:
        return tiktoken.get_encoding("cl100k_base")

# Global tokenizer instance
ENC = get_tokenizer()

def count_tokens(text: str) -> int:
    """Returns the number of tokens for a given text."""
    if not ENC: return len(text) // 4  # Rough fallback approximation
    return len(ENC.encode(text))

def separator(title: str = ""):
    """Prints a stylized separator line."""
    line = "-" * 120
    print(f"{C.DIM}{line}{C.RESET}")
    if title:
        print(f"{C.BOLD}{title}{C.RESET}")
        print(f"{C.DIM}{line}{C.RESET}")

def fixed_bar(value, max_value, width=BAR_WIDTH):
    """Generates a visual progress bar string."""
    if max_value == 0: return " " * width
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)

def color_val(val, best, worst, inverse=False):
    """Returns a color code based on value comparison (Green=Good, Red=Bad)."""
    is_best = val == best if not inverse else val == worst
    if is_best: return C.GREEN
    if val == worst and not inverse: return C.RED
    return C.WHITE

def measure_encode(fn: Callable, repeats: int):
    """
    Measures the execution time of a function.
    Returns: (result_of_function, average_time_ms)
    """
    times = []
    result = None
    
    # Warmup run
    try:
        fn()
    except Exception:
        pass 

    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        t1 = time.perf_counter()
        times.append(t1 - t0)
    
    return result, statistics.mean(times) * 1000

def get_formatters(data: Any) -> Dict[str, Callable]:
    """
    Returns a dictionary of lambda functions for each format.
    """
    formatters = {
        "JSON": lambda: json.dumps(data, separators=(",", ":"), ensure_ascii=False),
        "AICD": lambda: ai.data.encode(data, {"compact": True, "escape_new_lines": True}),
        "AID":  lambda: ai.data.encode(data, {"compact": False, "escape_new_lines": False}),
    }

    if toon_format:
        # Standardize TOON formatting for benchmarks
        formatters["TOON"] = lambda: toon_format.encode(data, options={"indent": 2, "delimiter": ",", "lengthMarker": False})
    
    return formatters

def get_files(directory: pathlib.Path) -> List[pathlib.Path]:
    """Retrieves all .json files from the directory."""
    if not directory.exists():
        print(f"{C.RED}Error: Directory '{directory}' does not exist.{C.RESET}")
        return []
    return sorted(list(directory.glob("*.json")))


# ==============================================================================
# COMBINED BENCHMARK ENGINE
# ==============================================================================

def run_benchmark(files: List[pathlib.Path], repeats: int, debug: bool):
    """
    Runs the benchmark in a SINGLE pass.
    1. Iterates files -> Measures & Visualizes.
    2. Aggregates stats.
    3. Prints Final Table & Summary.
    """
    
    # --- INITIALIZATION ---
    results = []
    keys = ["JSON", "AICD", "AID"]
    if toon_format: keys.append("TOON")
    
    totals = {k: {"tokens": 0, "time": 0} for k in keys}

    print(f"\n{C.BOLD}STARTING BENCHMARK{C.RESET}")
    print(f"Files: {len(files)} | Repeats: {repeats} | Model: {MODEL_NAME}\n")

    # --- MAIN LOOP (PER FILE) ---
    for file in files:
        # 1. Load Data
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check for reference AID file for decode check
        aid_file = file.with_suffix(".aid")
        has_aid_file = aid_file.exists()
        aid_content_ref = ""
        if has_aid_file:
            with open(aid_file, "r", encoding="utf-8") as f:
                aid_content_ref = f.read()

        formatters = get_formatters(data)
        
        # 2. Visual Header
        separator(f"FILE: {file.name}")

        # 3. DEBUG: Show Content (Optional)
        if debug:
            for fmt_name, func in formatters.items():
                txt, _ = measure_encode(func, 1) # Single run for display
                tok = count_tokens(txt)
                color = getattr(CFORMATS, fmt_name, CFORMATS.WHITE)
                if fmt_name == "AID":
                    txt = ai.data.encode(data, {"compact": False, "escape_new_lines": False, "colorize": True})
                print(f"{C.WHITE}{C.BOLD}[{fmt_name}] ({tok} tok){C.RESET}\n{color}{txt}{C.RESET}\n")

        # 4. MEASURE (The heavy lifting - done ONLY ONCE)
        # Dictionary to store stats for this specific file
        file_stats = {"file": file.name} 
        
        # Temp storage for bar charts
        bar_data = {} 

        for name in keys:
            func = formatters.get(name)
            if not func: continue

            text, ms = measure_encode(func, repeats=repeats)
            tok = count_tokens(text)
            
            # Store for final table
            file_stats[name] = (tok, ms)
            
            # Store for visuals
            bar_data[name] = {"tokens": tok, "time": ms}

            # Update globals
            totals[name]["tokens"] += tok
            totals[name]["time"] += ms

        # 5. VISUALIZE (Bar Charts)
        # Calculate limits for this file
        vals_tok = [s["tokens"] for s in bar_data.values()]
        vals_time = [s["time"] for s in bar_data.values()]
        min_tok, max_tok = min(vals_tok), max(vals_tok)
        min_time, max_time = min(vals_time), max(vals_time)

        for name in keys:
            s = bar_data[name]
            
            t_col = color_val(s["tokens"], min_tok, max_tok)
            tm_col = color_val(s["time"], min_time, max_time)
            
            t_bar = fixed_bar(s["tokens"], max_tok)
            tm_bar = fixed_bar(s["time"], max_time)

            print(f"{name:5} {t_col}{t_bar}{C.RESET} {s['tokens']:5} tok   {tm_col}{tm_bar}{C.RESET} {s['time']:6.3f} ms")

        # 6. DECODE CHECK (Validation)
        if has_aid_file:
            def run_decode(): return ai.data.decode(aid_content_ref)
            try:
                decoded_tuple, decode_ms = measure_encode(run_decode, repeats=repeats)
                decode_result = decoded_tuple # ai.data.decode returns (Node, Errors)
                errors = decode_result.errors

                valid = len(errors) == 0
                status = f"{C.GREEN}OK{C.RESET}" if valid else f"{C.RED}FAIL ({len(errors)}){C.RESET}"
                
                print(f"       Decode Check: {status} ({decode_ms:.3f} ms)")
                if not valid:
                    for err in errors: print(f"       - {err}")
            except Exception as e:
                print(f"       {C.RED}Decode Crash: {e}{C.RESET}")
        
        print("") # Spacing between files
        
        # Add to global results list
        results.append(file_stats)

    # --- END OF LOOP ---

    # ==========================================================================
    # FINAL REPORT GENERATION
    # ==========================================================================
    
    print(f"\n{C.BOLD}GLOBAL PERFORMANCE REPORT{C.RESET}")
    
    # ---  DETAILED TABLE
    header = f"{'FILE':28} "
    for k in keys:
        header += f"{k:>15} "
    header += f"{'SAVINGS (AICD)':>20}"
    
    print(header)
    separator()

    for r in results:
        line = f"{r['file'][:30]:30} "
        
        # Calculate row min/max for coloring table cells
        row_toks = [r[k][0] for k in keys]
        
        # Safe min/max (handle identical values)
        min_t, max_t = min(row_toks), max(row_toks)

        for k in keys:
            tok, ms = r[k]
            c_tok = color_val(tok, min_t, max_t)
            # Format: 1234t/12.5ms
            line += f"{c_tok}{tok:5}t{C.RESET}/{ms:4.1f}ms   "

        # Savings % (AICD vs JSON)
        base = r["JSON"][0]
        curr = r["AICD"][0]
        diff = ((curr - base) / base) * 100 if base > 0 else 0
        c_diff = C.GREEN if diff < 0 else C.RED
        line += f"{c_diff}{diff:>+10.1f}%{C.RESET}"

        print(line)

    separator()

    print(f"\n{C.BOLD}BENCHMARK SUMMARY:{C.RESET}\n\n")
    
    # --- 1. GLOBAL VISUAL CHART ---

    # Calculate global min/max for scaling
    all_toks = [totals[k]["tokens"] for k in keys]
    all_times = [totals[k]["time"] for k in keys]
    
    # Avoid division by zero
    g_min_t, g_max_t = (min(all_toks), max(all_toks)) if all_toks else (0, 0)
    g_min_ms, g_max_ms = (min(all_times), max(all_times)) if all_times else (0, 0)

    for k in keys:
        t = totals[k]["tokens"]
        ms = totals[k]["time"]
        
        # Colors
        c_t = color_val(t, g_min_t, g_max_t)
        c_ms = color_val(ms, g_min_ms, g_max_ms)
        
        # Bars
        b_t = fixed_bar(t, g_max_t)
        b_ms = fixed_bar(ms, g_max_ms)
        
        print(f"   {k:5} {c_t}{b_t}{C.RESET} {t:8} tok   {c_ms}{b_ms}{C.RESET} {ms:8.2f} ms")

    print(f"\n")
    
    # --- 3. SUMMARY DASHBOARD
    print(f"   {'FORMAT':<10} {'TOKENS':<12} {'TIME (Total)':<15} {'AVG TIME/FILE':<15} {'VS JSON':<10}")
    print(f"   {'-'*70}")

    json_tot = totals["JSON"]["tokens"]
    file_count = len(files)

    # Sort keys by token count (Leaderboard order)
    sorted_keys = sorted(keys, key=lambda k: totals[k]["tokens"])

    for k in sorted_keys:
        tot_tok = totals[k]["tokens"]
        tot_time = totals[k]["time"]
        avg_time = tot_time / file_count if file_count > 0 else 0
        
        # Calculate percentage difference vs JSON
        if json_tot > 0:
            saving_pct = ((tot_tok - json_tot) / json_tot) * 100
        else:
            saving_pct = 0.0

        # Formatting
        c_fmt = C.WHITE
        if k == "AICD": c_fmt = C.GREEN
        elif k == "JSON": c_fmt = C.CYAN
        
        pct_str = f"{saving_pct:+.1f}%"
        if saving_pct < 0:
            pct_str = f"{C.GREEN}{pct_str}{C.RESET}"
        elif saving_pct > 0:
            pct_str = f"{C.RED}{pct_str}{C.RESET}"
        else:
            pct_str = f"{C.DIM}{pct_str}{C.RESET}"

        print(f"   {c_fmt}{k:<10}{C.RESET} {tot_tok:<12} {tot_time:8.2f} ms    {avg_time:8.2f} ms    {pct_str}")

    print("\n")
    
    # 3. CONCLUSION
    aicd_saved = json_tot - totals["AICD"]["tokens"]
    if aicd_saved > 0:
        percent_saved = (aicd_saved / json_tot) * 100
        print(f"{C.BOLD}CONCLUSION:{C.RESET} Switching to {C.GREEN}AICD{C.RESET} saves {C.GREEN}{aicd_saved}{C.RESET} tokens "
              f"({percent_saved:.1f}%) compared to JSON.")
    else:
        print(f"{C.BOLD}CONCLUSION:{C.RESET} JSON appears to be the most efficient format for this dataset.")


# ==============================================================================
# MAIN RUNNER
# ==============================================================================

def run(args):
    """
    Main execution entry point for the Benchmark command.
    """
    # 1. Setup
    target_dir = pathlib.Path(args.directory) if args.directory else pathlib.Path("data")
    repeats = int(args.repeats)

    if not tiktoken:
        print(f"{C.YELLOW}Warning: 'tiktoken' not found. Token counts will be approximate.{C.RESET}")

    # 2. Get Files
    files = get_files(target_dir)
    if not files:
        sys.exit(0)

    # 3. Execution
    try:
        run_benchmark(files, repeats, args.debug)
            
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Benchmark cancelled.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Benchmark Error:{C.RESET} {e}")
        if args.debug:
            import traceback
            traceback.print_exc()


# ==============================================================================
# ARGUMENT REGISTRATION
# ==============================================================================

def register_arguments(parser):
    """Registers arguments for the 'benchmark' command."""
    parser.add_argument("directory", nargs="?", default="data", help="Data directory")
    parser.add_argument("-r", "--repeats", type=int, default=50, help="Iterations per file")
    parser.add_argument("--debug", action="store_true", help="Show verbose output")