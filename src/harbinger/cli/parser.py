from __future__ import annotations

import argparse
import builtins
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from importlib.metadata import version
from typing import Final, TypeAlias

from ..annotation import IntLiteralType, ScalarType, StringLiteralType, Untyped
from ..model import Task
from ..signature import FixedSignature, Parameter, VariadicSignature

TASKFILE: Final = "tasks.py"


class HarbingerFlag(Enum):
    ALL = auto()
    DEFAULT = auto()
    LIST = auto()


@dataclass(frozen=True, slots=True)
class RunSelected:
    """harbinger <task> [<task> ...]"""

    names: Sequence[str]


@dataclass(frozen=True, slots=True)
class Invoke:
    """harbinger <task> -- <args>"""

    name: str
    argv: Sequence[str]


Command: TypeAlias = HarbingerFlag | RunSelected | Invoke
ArgsKwargs: TypeAlias = tuple[Sequence[object], Mapping[str, object]]


@dataclass(slots=True)
class TaskParser:
    task: Task
    parser: argparse.ArgumentParser

    def __init__(self, task: Task, /) -> None:
        self.task = task
        self.parser = argparse.ArgumentParser(
            prog=f"harbinger {task.id} --",
            description=task.description,
        )

    def parse(self, argv: Sequence[str]) -> ArgsKwargs:
        match self.task.signature:
            case VariadicSignature(name, type, keywords):
                for param in keywords:
                    self.add_kwarg(param)
                match type:
                    case ScalarType(scalar):
                        self.parser.add_argument(name, nargs="*", type=scalar)
                    case Untyped():
                        self.parser.add_argument(name, nargs="*")
                ns = self.parser.parse_args(argv)
                kwargs = {param.name: getattr(ns, param.name) for param in keywords}
                return (getattr(ns, name), kwargs)

            case FixedSignature(parameters=parameters):
                for param in parameters:
                    if param.is_keyword:
                        self.add_kwarg(param)
                    else:
                        self.add_arg(param)
                ns = self.parser.parse_args(argv)
                args: list[object] = []
                kwargs: dict[str, object] = {}
                for param in parameters:
                    val = getattr(ns, param.name)
                    if param.is_keyword:
                        kwargs[param.name] = val
                    else:
                        args.append(val)
                return args, kwargs

    def add_kwarg(self, param: Parameter) -> None:
        flag = f"--{param.name}"
        match param.type:
            case Untyped():
                self.parser.add_argument(
                    flag,
                    default=param.default,
                    help=f"default: {param.default}",
                )
            case ScalarType(builtins.bool):
                self.parser.add_argument(
                    flag,
                    action=argparse.BooleanOptionalAction,
                    default=param.default,
                    help=f"default: {param.default}",
                )
            case ScalarType(type):
                self.parser.add_argument(
                    flag,
                    type=type,
                    default=param.default,
                    help=f"default: {param.default}",
                )
            case StringLiteralType(values) | IntLiteralType(values) as lit:
                self.parser.add_argument(
                    flag,
                    type=lit.type,
                    choices=values,
                    default=param.default,
                    # The default metavar for choices doesn't do spaces after comma
                    # so we have to intervene.
                    metavar=f"{{{', '.join(str(v) for v in values)}}}",
                    help=f"default: {param.default}",
                )

    def add_arg(self, param: Parameter) -> None:
        match param.type:
            case Untyped():
                self.parser.add_argument(
                    param.name,
                    nargs="?",
                    default=param.default,
                    help=f"default: {param.default}",
                )
            case ScalarType(type):
                self.parser.add_argument(
                    param.name,
                    type=type,
                    nargs="?",
                    default=param.default,
                    help=f"default: {param.default}",
                )
            case StringLiteralType(values) | IntLiteralType(values) as literal:
                self.parser.add_argument(
                    param.name,
                    type=literal.type,
                    choices=values,
                    nargs="?",
                    default=param.default,
                    # The default metavar for choices doesn't do spaces after comma
                    # so we have to intervene.
                    metavar=f"{{{', '.join(str(v) for v in values)}}}",
                    help=f"default: {param.default}",
                )


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

    args = parser.parse_args(head)

    if args.all:
        return HarbingerFlag.ALL

    if args.default:
        return HarbingerFlag.DEFAULT

    if args.list:
        return HarbingerFlag.LIST

    if tail:
        match args.tasks:
            case [name]:
                return Invoke(name=name, argv=tail)
            case []:
                parser.error("no task specified before '--'")
            case _:
                parser.error("exactly one task must precede '--'")

    if args.tasks:
        return RunSelected(names=args.tasks)

    return HarbingerFlag.LIST
