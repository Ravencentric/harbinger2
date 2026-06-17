from __future__ import annotations

import argparse
import inspect
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
from .runner import TaskRunner
from .typs import Task

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
    args: tuple[object, ...]
    kwargs: dict[str, object]


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

        sig = self.task.sig

        for name, param in sig.parameters.items():
            anno = (
                param.annotation
                if param.annotation is not inspect.Parameter.empty
                else str
            )
            has_default = param.default is not inspect.Parameter.empty
            is_keyword = (
                param.kind
                in (
                    inspect.Parameter.KEYWORD_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and has_default
            )

            if is_keyword or param.kind is inspect.Parameter.KEYWORD_ONLY:
                flag = f"--{name.replace('_', '-')}"
                if anno is bool:
                    if has_default:
                        parser.add_argument(
                            flag,
                            action=argparse.BooleanOptionalAction,
                            default=param.default,
                        )
                    else:
                        parser.add_argument(flag, action=argparse.BooleanOptionalAction)
                elif has_default:
                    parser.add_argument(flag, type=anno, default=param.default)
                else:
                    parser.add_argument(flag, type=anno)
            else:
                # ponytail: positional — no bool handling, bool positionals are weird anyway
                parser.add_argument(name, type=anno)

        ns = parser.parse_args(list(argv))

        # Rebuild into ordered (args, kwargs) matching the original signature
        positional: list[object] = []
        keyword: dict[str, object] = {}

        for name, param in sig.parameters.items():
            val = getattr(ns, name.replace("-", "_"))
            has_default = param.default is not inspect.Parameter.empty
            is_keyword = (
                param.kind
                in (
                    inspect.Parameter.KEYWORD_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and has_default
            ) or param.kind is inspect.Parameter.KEYWORD_ONLY

            if is_keyword:
                keyword[name] = val
            else:
                positional.append(val)

        return tuple(positional), keyword


# ── Parser ────────────────────────────────────────────────────────


def parse(argv: Sequence[str], runner: TaskRunner) -> Command:
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
        name = tasks[0]
        task = REGISTRY.get(name)
        pos, kw = Subparser(task).parse(tail)
        return Invoke(name=name, args=pos, kwargs=kw)

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
    console.stdout(
        f"{TASKFILE}: [dim]{n} {'task' if n == 1 else 'tasks'} (* = default)[/]"
    )
    console.stdout("")

    width = max(len(t.name) for t in tasks)

    for task in tasks:
        marker = "[green]*[/]" if not task.requires_args else " "
        desc = f"  [dim]{task.description}[/]" if task.description else ""
        console.stdout(f"  {marker} [cyan]{task.name.ljust(width)}[/]{desc}")


# ── Entrypoint ────────────────────────────────────────────────────


def main() -> int:
    try:
        runner = TaskRunner(Path.cwd() / TASKFILE)
        command = parse(sys.argv[1:], runner)

        match command:
            case RunAll():
                runner.run()
            case ListTasks():
                list_tasks()
            case RunSelected(names=names):
                runner.run(names)
            case Invoke(name=name, args=args, kwargs=kwargs):
                runner.invoke(name, args=args, kwargs=kwargs)

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
