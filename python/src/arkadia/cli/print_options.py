from .colors import C

def print_options(title: str, options: list[dict]):
    """
    Prints a formatted list of options with auto-alignment.
    
    Args:
        title: Section header (e.g., "FLAGS").
        options: List of dicts: {'flags': str, 'desc': str, 'default': str (optional)}.
    """
    if not options:
        return

    # 1. Section Header
    print(f"{C.YELLOW}{title.upper()}:{C.RESET}")

    # 2. Calculate column width
    max_flag_len = 0
    for opt in options:
        length = len(opt.get('flags', ''))
        if length > max_flag_len:
            max_flag_len = length
    
    col_width = max_flag_len + 4

    # 3. Print rows
    for opt in options:
        flags = opt.get('flags', '')
        desc = opt.get('desc', '')
        default = opt.get('default', None)

        # Color logic: Flags starting with '-' are Green, positional args are Cyan
        if flags.startswith("-"):
            colored_flags = f"{C.GREEN}{flags}{C.RESET}"
        else:
            colored_flags = f"{C.CYAN}{flags}{C.RESET}"

        # Padding calculation (excluding ANSI codes from length)
        padding = " " * (col_width - len(flags))

        line = f"   {colored_flags}{padding}{C.WHITE}{desc}{C.RESET}"
        
        if default is not None:
            line += f" {C.DIM}[default: {default}]{C.RESET}"

        print(line)
    print("") # Empty line after section