import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from . import console
from .core import REGISTRY, TASKFILE
from .errors import (
    InvalidTaskFileError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from .runner import TaskRunner


@dataclass
class CommandLine:
    tasks: Sequence[str]
    list: bool

    @classmethod
    def parse(cls) -> Self:
        parser = argparse.ArgumentParser(
            prog="harbinger",
            description=f"Run tasks from {TASKFILE}",
        )
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="list available tasks without running them",
        )
        group.add_argument(
            "tasks",
            metavar="<task>",
            nargs="*",
            help="tasks to run; runs all tasks when omitted",
        )
        args = parser.parse_args()
        print(args)
        return cls(tasks=args.tasks, list=args.list)


def list_tasks() -> None:
    tasks = tuple(REGISTRY.tasks())

    if not tasks:
        console.stdout("[dim]No tasks found.[/]")
        return

    width = max(len(task.name) for task in tasks)

    for task in tasks:
        description = task.description or ""
        console.stdout(f"[cyan]{task.name.ljust(width)}[/]  [dim]{description}[/]")


def main() -> int:
    args = CommandLine.parse()
    runner = TaskRunner(Path.cwd() / TASKFILE)

    try:
        if args.list:
            list_tasks()
        else:
            runner.run(args.tasks)
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
