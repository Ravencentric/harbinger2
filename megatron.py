import os

from harbinger import task


@task
def hello(name: str, baz: bool, /, *, qux: int) -> None:
    """Print a small greeting."""
    print(f"Hello {name =}! {baz =}")


@task
def listdir() -> None:
    """List files in the current directory."""
    print(*os.listdir(), sep="\n")


@task
def foo() -> None:
    print("foo")
