from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import version
from typing import Final, TypeAlias

from ..model import Task

TASKFILE: Final = "tasks.py"


@dataclass(frozen=True, slots=True)
class RunAll:
    """harbinger --all"""


@dataclass(frozen=True, slots=True)
class RunDefault:
    """harbinger --default"""


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


Command: TypeAlias = RunAll | RunDefault | ListTasks | RunSelected | Invoke


@dataclass(frozen=True, slots=True)
class Subparser:
    """Builds an argparse.ArgumentParser from a task's function signature.

    Assumes every annotation is concrete and callable: ``anno(val)`` must work.
    ``bool`` uses ``BooleanOptionalAction`` (``--flag`` / ``--no-flag``).
    """

    task: Task

    def parse(
        self, argv: Sequence[str]
    ) -> tuple[tuple[object, ...], dict[str, object]]:
        parser = argparse.ArgumentParser(
            prog=f"harbinger {self.task.name} --",
            description=self.task.description,
        )

        for param in self.task.signature.parameters:
            if param.kind.is_keyword():
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
                        help=f"default: {param.default}",
                    )
            else:
                parser.add_argument(
                    param.name,
                    type=param.converter,
                    nargs="?",
                    default=param.default,
                    help=f"default: {param.default}",
                )

        ns = parser.parse_args(list(argv))

        # Rebuild into ordered (args, kwargs) matching the original signature
        positional: list[object] = []
        keyword: dict[str, object] = {}

        for param in self.task.signature.parameters:
            val = getattr(ns, param.name)
            if param.kind.is_keyword():
                keyword[param.name] = val
            else:
                positional.append(val)

        return tuple(positional), keyword


def parse(argv: Sequence[str]) -> Command:
    has_dash = "--" in argv
    if has_dash:
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
        "-a",
        "--all",
        action="store_true",
        help="run all tasks",
    )
    group.add_argument(
        "-d",
        "--default",
        action="store_true",
        help="run default tasks only",
    )
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
        help="tasks to run; lists tasks when omitted",
    )

    args = parser.parse_args(list(head))

    if args.all:
        return RunAll()

    if args.default:
        return RunDefault()

    if args.list:
        return ListTasks()

    if tail:
        tasks = args.tasks
        if len(tasks) != 1:
            parser.error("exactly one task must precede '--'")
        return Invoke(name=tasks[0], argv=tuple(tail))

    if has_dash and not args.tasks:
        parser.error("no task specified before '--'")

    if args.tasks:
        return RunSelected(names=tuple(args.tasks))

    return ListTasks()
