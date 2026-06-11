import argparse
from collections.abc import Sequence
from pathlib import Path

from . import console
from .core import REGISTRY, TASKFILE
from .errors import (
    InvalidTaskFileError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from .runner import TaskRunner


class CLIArguments(argparse.Namespace):
    tasks: Sequence[str]
    list: bool


class CLIParser(argparse.ArgumentParser):
    def __init__(self) -> None:
        super().__init__(
            prog="harbinger",
            description=f"Run tasks from {TASKFILE}.",
        )
        self.add_argument(
            "--list",
            action="store_true",
            help="list available tasks without running them",
        )
        self.add_argument(
            "tasks",
            metavar="task",
            nargs="*",
            help="tasks to run; runs all tasks when omitted",
        )

    def parse(self, argv: list[str] | None = None) -> CLIArguments:
        return self.parse_args(argv, namespace=CLIArguments())


def list_tasks() -> None:
    tasks = tuple(REGISTRY.tasks())

    if not tasks:
        console.stdout("[dim]No tasks found.[/]")
        return

    width = max(len(task.name) for task in tasks)

    for task in tasks:
        description = task.description or ""
        console.stdout(f"[cyan]{task.name.ljust(width)}[/]  [dim]{description}[/]")


def main(argv: list[str] | None = None) -> int:
    args = CLIParser().parse(argv)
    runner = TaskRunner(Path.cwd() / TASKFILE)

    try:
        runner.load()
        if args.list:
            list_tasks()
        else:
            runner.execute(args.tasks)
    except TaskFileNotFoundError:
        console.error(f"task file not found: {runner.taskfile}")
        return 1
    except InvalidTaskFileError as error:
        source = error.__cause__
        message = f"{source}" if source is not None else f"{error}"
        console.error(f"could not load {runner.taskfile}: {message}")
        return 1
    except UndefinedTaskNameError as error:
        console.error(f"unknown task {error.args[0]!r}")
        return 1
    except TaskError as error:
        source = error.__cause__
        message = f"{source}" if source is not None else "unknown"
        console.error(f"task {error.args[0]!r} failed: {message}")
        return 1

    return 0
