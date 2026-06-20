from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import TypeAlias

from . import console
from .core import REGISTRY, TASKFILE
from .errors import (
    InvalidTaskFileError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from .registry import load
from .typs import ParameterKind, Task

# ── Command sum type ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RunAll:
    """harbinger"""


@dataclass(frozen=True, slots=True)
class ListTasks:
    """harbinger --list"""


@dataclass(frozen=True, slots=True)
class RunSelected:
    """harbinger <task> [<task> ...]"""

    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Invoke:
    """harbinger <task> -- <args>"""

    name: str
    argv: tuple[str, ...]


Command: TypeAlias = RunAll | ListTasks | RunSelected | Invoke

# ── Subparser ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Subparser:
    """Builds an argparse.ArgumentParser from a task's function signature.

    Assumes every annotation is concrete and callable: ``anno(val)`` must work.
    ``bool`` uses ``BooleanOptionalAction`` (``--flag`` / ``--no-flag``).
    """

    task: Task[..., object]

    def parse(
        self, argv: Sequence[str]
    ) -> tuple[tuple[object, ...], dict[str, object]]:
        parser = argparse.ArgumentParser(
            prog=f"harbinger {self.task.name} --",
            description=self.task.description,
        )

        for param in self.task.signature.parameters:
            is_keyword = param.kind is ParameterKind.KEYWORD

            if is_keyword:
                flag = f"--{param.name.replace('_', '-')}"
                # ponytail: the one piece of presentation logic in the consumer.
                # Signature stays presentation-agnostic; a future non-CLI
                # consumer isn't forced into flag semantics.
                if param.converter is bool:
                    parser.add_argument(
                        flag,
                        action=argparse.BooleanOptionalAction,
                        default=param.default,
                        help=f"default: {param.default}",
                    )
                else:
                    parser.add_argument(
                        flag,
                        type=param.converter,
                        default=param.default,
                        help=f"default: {param.default!r}",
                    )
            else:
                # ponytail: positional — no bool handling, bool positionals are weird anyway
                parser.add_argument(
                    param.name,
                    type=param.converter,
                    nargs="?",
                    default=param.default,
                    help=f"default: {param.default!r}",
                )

        ns = parser.parse_args(list(argv))

        # Rebuild into ordered (args, kwargs) matching the original signature
        positional: list[object] = []
        keyword: dict[str, object] = {}

        for param in self.task.signature.parameters:
            val = getattr(ns, param.name)
            if param.kind is ParameterKind.KEYWORD:
                keyword[param.name] = val
            else:
                positional.append(val)

        return tuple(positional), keyword


# ── Parser ────────────────────────────────────────────────────────


def parse(argv: Sequence[str]) -> Command:
    if "--" in argv:
        pivot = list(argv).index("--")
        head, tail = argv[:pivot], argv[pivot + 1 :]
    else:
        head, tail = argv, ()

    parser = argparse.ArgumentParser(
        prog="harbinger",
        description=f"Run tasks from {TASKFILE}",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="list available tasks without running them",
    )
    group.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version('harbinger')}",
    )
    group.add_argument(
        "tasks",
        metavar="<task>",
        nargs="*",
        help="tasks to run; runs all tasks when omitted",
    )

    args = parser.parse_args(list(head))

    if args.list:
        return ListTasks()

    if tail:
        tasks = args.tasks
        if len(tasks) != 1:
            parser.error("exactly one task must precede '--'")
        return Invoke(name=tasks[0], argv=tuple(tail))

    if args.tasks:
        return RunSelected(names=tuple(args.tasks))

    return RunAll()


# ── Display ───────────────────────────────────────────────────────


def list_tasks() -> None:
    tasks = tuple(REGISTRY.tasks())

    if not tasks:
        console.stdout("[dim]No tasks found.[/]")
        return

    n = len(tasks)
    console.stdout(f"{TASKFILE}: [dim]{n} {'task' if n == 1 else 'tasks'}[/]")
    console.stdout("")

    width = max(len(t.name) for t in tasks)

    for task in tasks:
        desc = f"  [dim]{task.description}[/]" if task.description else ""
        console.stdout(f"  [cyan]{task.name.ljust(width)}[/]{desc}")


# ── Entrypoint ────────────────────────────────────────────────────


def main() -> int:
    try:
        command = parse(sys.argv[1:])

        load(Path.cwd() / TASKFILE)

        match command:
            case RunAll():
                for task in REGISTRY.tasks():
                    task.call()
            case ListTasks():
                list_tasks()
            case RunSelected(names=names):
                for name in names:
                    REGISTRY.run(name)
            case Invoke(name=name, argv=argv):
                task = REGISTRY.get(name)
                pos, kw = Subparser(task).parse(argv)
                task.call(*pos, **kw)

    except TaskFileNotFoundError:
        console.error(f"task file not found: {TASKFILE}")
        return 1
    except InvalidTaskFileError as error:
        source = error.__cause__
        message = f"{source}" if source is not None else f"{error}"
        console.error(f"could not load {TASKFILE}: {message}")
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
