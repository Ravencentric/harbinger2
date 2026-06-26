from __future__ import annotations

import os
import sys
from enum import IntEnum
from functools import cache


class Style(IntEnum):
    """
    Based on <https://en.wikipedia.org/wiki/ANSI_escape_code#Colors>
    """

    RESET = 0
    YELLOW = 33
    CYAN = 36
    RED = 31
    GREEN = 32
    MAGENTA = 35
    DIM = 90

    @property
    def marker(self) -> str:
        match self:
            case Style.RESET:
                return "[/]"
            case _:
                return f"[{self.name.lower()}]"

    def to_ansi(self) -> str:
        return f"\033[{self.value}m"

    def __str__(self) -> str:
        return self.to_ansi()


@cache
def can_colorize() -> bool:
    """Check env vars and for tty/dumb terminal"""

    if os.environ.get("ANSI_COLORS_DISABLED"):
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True

    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "fileno"):
        return False

    try:
        return os.isatty(sys.stdout.fileno())
    except OSError:
        return sys.stdout.isatty()


def render(s: str) -> str:
    color = can_colorize()

    for style in Style:
        if color:
            s = s.replace(style.marker, style.to_ansi())
        else:
            s = s.replace(style.marker, "")

    return s


def stdout(s: str, /) -> None:
    print(render(s), file=sys.stdout)


def stderr(s: str, /) -> None:
    print(render(s), file=sys.stderr)


def error(s: str, /) -> None:
    stderr(f"[red]error:[/] {s}")


def hint(s: str, /) -> None:
    stderr(f"[green]tip:[/] {s}")
