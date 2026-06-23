import subprocess

from harbinger import task

base = ["uv", "run"]


@task
def lint() -> None:
    """Run the ruff linter."""
    subprocess.run(base + ["ruff", "check", "."], check=True)


@task
def format(*, check: bool = False) -> None:
    """Format code with ruff."""
    cmd = ["ruff", "format", "."]
    if check:
        cmd.append("--check")
    subprocess.run(base + cmd, check=True)


@task
def typecheck() -> None:
    """Run the pyrefly type checker."""
    subprocess.run(base + ["pyrefly", "check"], check=True)


@task
def test() -> None:
    """Run the test suite."""
    subprocess.run(base + ["pytest"], check=True)


@task(default=False)
def check() -> None:
    """Run all static gates (lint, format-check, typecheck, test)."""
    lint()
    format(check=True)
    typecheck()
    test()
