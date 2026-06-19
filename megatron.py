import os
from pathlib import Path

from harbinger import task


@task
def hello() -> None:
    """Print a small greeting."""
    print("Hello")


@task
def listdir() -> None:
    """List files in the current directory."""
    print(*os.listdir(), sep="\n")


@task(name="greet", description="Greet someone N times")
def greet(name: str = "World", count: int = 1, *, loud: bool = False) -> None:
    msg = f"Hello, {name}!" if not loud else f"HELLO, {name.upper()}!"
    for _ in range(count):
        print(msg)


@task
def add(a: float = 0.0, b: float = 0.0) -> None:
    """Add two numbers."""
    print(f"{a} + {b} = {a + b}")


@task
def cat(path: Path = Path("README.md"), *, numbered: bool = False) -> None:
    """Print a file's contents."""
    for i, line in enumerate(path.read_text().splitlines(), 1):
        print(f"{i:4d}  {line}" if numbered else line)
