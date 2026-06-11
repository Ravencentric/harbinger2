import argparse
import importlib.util
from collections.abc import Sequence
from pathlib import Path

from . import console
from .core import REGISTRY, TASKFILE
from .errors import TaskError, UndefinedTaskNameError


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
            "tasks",
            metavar="task",
            nargs="*",
            help="tasks to run; runs all tasks when omitted",
        )

    def parse(self, argv: list[str] | None = None) -> CLIArguments:
        return self.parse_args(argv, namespace=CLIArguments())


def import_taskfile(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    # If these fail, then we can't do anything about it
    # so we can just assert these away
    assert spec
    assert spec.loader

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def execute_tasks(names: Sequence[str]) -> int:
    for name in names:
        try:
            REGISTRY.call(name)
        except UndefinedTaskNameError:
            console.error(f"unknown task {name!r}")
            return 1
        except TaskError as error:
            source = error.__cause__
            message = f"{source}" if source is not None else "unknown"
            console.error(f"task {name!r} failed: {message}")
            return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    args = CLIParser().parse(argv)
    path = Path.cwd() / TASKFILE

    if not path.is_file():
        console.error(f"task file not found: {path}")
        return 1

    try:
        import_taskfile(path)
    except Exception as error:
        console.error(f"could not load {path}: {error}")
        return 1

    names = args.tasks or [task.name for task in REGISTRY.tasks()]
    return execute_tasks(names)
