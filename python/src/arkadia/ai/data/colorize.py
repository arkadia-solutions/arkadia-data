import re

RESET = "\033[0m"
BOLD = "\033[1m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


def colorize(text: str) -> str:
    """
    Safe syntax highlighter for AI.DATA-FORMAT.
    Only colors constructs that exist in the CURRENT specification.
    """

    # --- Order is important: we highlight in layers ---

    # 1. Multiline strings:  ` ... `
    text = re.sub(
        r"`([^`]*)`",
        lambda m: YELLOW + "`" + m.group(1) + "`" + RESET,
        text,
        flags=re.DOTALL,
    )

    # 2. Quoted strings: "text"
    text = re.sub(
        r"\"([^\"]*)\"", lambda m: YELLOW + '"' + m.group(1) + '"' + RESET, text
    )

    # 3. @TypeName
    text = re.sub(
        r"@([A-Za-z_][A-Za-z0-9_]*)",
        lambda m: BOLD + CYAN + "@" + m.group(1) + RESET,
        text,
    )

    # 4. <schema> brackets
    text = text.replace("<", CYAN + "<" + RESET)
    text = text.replace(">", CYAN + ">" + RESET)

    # 5. Lists and tuples: [] ()
    text = text.replace("[", BLUE + "[" + RESET)
    text = text.replace("]", BLUE + "]" + RESET)
    text = text.replace("(", BLUE + "(" + RESET)
    text = text.replace(")", BLUE + ")" + RESET)

    # 6. Named-record braces: {}
    text = text.replace("{", GREEN + "{" + RESET)
    text = text.replace("}", GREEN + "}" + RESET)

    # 7. Numbers
    text = re.sub(r"\b\d+(\.\d+)?\b", lambda m: MAGENTA + m.group(0) + RESET, text)

    # 8. true / false / null
    text = re.sub(r"\btrue\b", BLUE + "true" + RESET, text)
    text = re.sub(r"\bfalse\b", BLUE + "false" + RESET, text)
    text = re.sub(r"\bnull\b", BLUE + "null" + RESET, text)

    # 9. Comments /.../
    text = re.sub(r"/[^/]+/", lambda m: YELLOW + m.group(0) + RESET, text)

    return text
