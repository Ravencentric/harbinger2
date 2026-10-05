import builtins
from pathlib import Path
from typing import Literal

from harbinger import Cmd, task

uv = Cmd("uv").args("run")


@task(default=True)
def lint(*, fix: bool = True) -> None:
    """Run the Ruff linter (optionally applying fixes)."""
    if fix:
        uv.args(t"ruff check --fix").run()
    else:
        uv.args(t"ruff check").run()


@task(default=True)
def format(*, check: bool = False) -> None:
    """Format code with Ruff (or verify formatting with --check)."""
    if check:
        uv.args(t"ruff format --check").run()
    else:
        uv.args(t"ruff format").run()


@task(default=True)
def typecheck() -> None:
    """Run the Pyrefly type checker."""
    uv.args(t"pyrefly check").run()


@task
def test() -> None:
    """Run the test suite."""
    uv.args(t"pytest").run()


@task
def greet(
    who: str = "world",
    *,
    punctuation: Literal[".", "!"] = "!",
    loud: bool = False,
    times: int = 1,
) -> None:
    """Print a greeting a number of times."""
    for _ in range(times):
        msg = f"hello, {who}{punctuation}"
        print(msg.upper() if loud else msg)


@task
def echo(*args: str) -> None:
    """Echo each positional argument on its own line."""
    print("\n".join(args))


@task
def sum(*args: float) -> None:
    print(builtins.sum(args))


@task
def ci() -> None:
    """Run all CI checks without modifying the working tree."""
    lint(fix=False)
    format(check=True)
    typecheck()
    test()


@task
def cp(*paths: Path, recursive: bool = False) -> None:
    """Copy paths."""
    for p in paths:
        print(p, recursive)
