import os

from harbinger import task


@task
def hello() -> None:
    """Print a small greeting."""
    print("Hello")


@task
def listdir() -> None:
    """List files in the current directory."""
    print(*os.listdir(), sep="\n")


@task
def foo() -> None:
    print("foo")
