
from .colors import C

def print_usage(tool_name: str, command_name: str, args_syntax: str):
    """
    Prints a styled usage line.
    """
    print(f"{C.BOLD}USAGE:{C.RESET}")
    print(f"   {C.AID_MAIN}{tool_name}{C.RESET} {C.BOLD}{command_name}{C.RESET} {args_syntax}\n")