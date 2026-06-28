from __future__ import annotations

import argparse
import builtins
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from importlib.metadata import version
from typing import Final, TypeAlias

from ..annotation import EmptyType, LiteralType, ScalarType
from ..model import Task
from ..signature import FixedSignature, VariadicSignature

TASKFILE: Final = "tasks.py"


class HarbingerFlag(Enum):
    ALL = auto()
    DEFAULT = auto()
    LIST = auto()


@dataclass(frozen=True, slots=True)
class RunSelected:
    """harbinger <task> [<task> ...]"""

    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Invoke:
    """harbinger <task> -- <args>"""

    name: str
    argv: tuple[str, ...]


Command: TypeAlias = HarbingerFlag | RunSelected | Invoke
ArgsKwargs: TypeAlias = tuple[Sequence[object], Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class Subparser:
    """Builds an argparse.ArgumentParser from a task's function signature.

    Assumes every annotation is concrete and callable: ``anno(val)`` must work.
    ``bool`` uses ``BooleanOptionalAction`` (``--flag`` / ``--no-flag``).
    """

    task: Task

    def parse(self, argv: Sequence[str]) -> ArgsKwargs:
        parser = argparse.ArgumentParser(
            prog=f"harbinger {self.task.name} --",
            description=self.task.description,
        )

        match self.task.signature.kind:
            case VariadicSignature(name, type):
                match type:
                    case ScalarType(scalar):
                        parser.add_argument(name, nargs="*", type=scalar)
                    case EmptyType():
                        parser.add_argument(name, nargs="*")
                ns = parser.parse_args(argv)
                return (getattr(ns, name), {})

            case FixedSignature(parameters=parameters):
                for param in parameters:
                    if param.kind.is_keyword():
                        flag = f"--{param.name}"

                        def arg(**kwargs: object) -> None:
                            if default := param.default:
                                parser.add_argument(
                                    flag,
                                    default=default,
                                    help=f"default: {default}",
                                    **kwargs,
                                )
                            else:
                                parser.add_argument(flag, **kwargs)

                        match param.type:
                            case EmptyType():
                                arg()

                            case ScalarType(builtins.bool):
                                arg(action=argparse.BooleanOptionalAction)

                            case ScalarType(type):
                                arg(type=type)

                            case LiteralType(choices):
                                arg(choices=choices)

                    else:
                        match param.type:
                            case EmptyType():
                                parser.add_argument(
                                    param.name,
                                    nargs="?",
                                    **kw,
                                )

                            case ScalarType(type=scalar):
                                parser.add_argument(
                                    param.name,
                                    type=scalar,
                                    nargs="?",
                                    **kw,
                                )

                            case LiteralType(values=values):
                                parser.add_argument(
                                    param.name,
                                    type=str,
                                    choices=values,
                                    nargs="?",
                                    **kw,
                                )

                ns = parser.parse_args(argv)

                pos: list[object] = []
                kw: dict[str, object] = {}

                for param in parameters:
                    val = getattr(ns, param.name)
                    if param.kind.is_keyword():
                        kw[param.name] = val
                    else:
                        pos.append(val)

                return pos, kw


def command(argv: Sequence[str]) -> Command:
    has_dash = "--" in argv
    if has_dash:
        pivot = argv.index("--")
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
        return HarbingerFlag.ALL

    if args.default:
        return HarbingerFlag.DEFAULT

    if args.list:
        return HarbingerFlag.LIST

    if tail:
        tasks = args.tasks
        if len(tasks) != 1:
            parser.error("exactly one task must precede '--'")
        return Invoke(name=tasks[0], argv=tuple(tail))

    if has_dash and not args.tasks:
        parser.error("no task specified before '--'")

    if args.tasks:
        return RunSelected(names=tuple(args.tasks))

    return HarbingerFlag.LIST
