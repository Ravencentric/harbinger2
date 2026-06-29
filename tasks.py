import subprocess
from typing import Literal

from harbinger import task


def uvrun(*args: str) -> None:
    subprocess.run(["uv", "run", *args], check=True)


@task
def lint(*, fix: bool = True) -> None:
    """Run the Ruff linter (optionally applying fixes)."""
    if fix:
        uvrun("ruff", "check", "--fix")
    else:
        uvrun("ruff", "check")


@task
def format(*, check: bool = False) -> None:
    """Format code with Ruff (or verify formatting with --check)."""
    if check:
        uvrun("ruff", "format", ".", "--check")
    else:
        uvrun("ruff", "format", ".")


@task
def typecheck() -> None:
    """Run the Pyrefly type checker."""
    uvrun("pyrefly", "check")


@task
def test() -> None:
    """Run the test suite."""
    uvrun("pytest")


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
    print(sum(args))


@task(default=False)
def ci() -> None:
    """Run all CI checks without modifying the working tree."""
    lint(fix=False)
    format(check=True)
    typecheck()
    test()
