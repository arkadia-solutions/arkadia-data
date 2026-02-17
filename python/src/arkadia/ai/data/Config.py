from typing import TypedDict

class Config(TypedDict, total=False):
    prompt_output: bool
    """Embed schema directly inside sample data.
    [
        (name: string /name of the user/, age: number /age of the user/),
    ]
    """

    indent: int
    """Number of spaces used for indentation."""

    start_indent: int
    """Initial indentation offset."""

    compact: bool
    """Enable compact formatting. Remove not nececcary spaces"""

    escape_new_lines: bool
    """Escape newline characters as literal \\n and \\r."""

    colorize: bool
    """Enable ANSI colorized output."""

    include_comments: bool
    """Include comments in output."""

    include_array_size: bool
    """Include array size information."""

    include_schema: bool
    """Include schema header informat."""

    include_meta: bool
    """Include meta header informat."""

    include_type: bool
    """Include type after each name True: <name: string>, false: <name>."""
