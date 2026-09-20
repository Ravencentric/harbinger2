from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from ..errors import (
    HarbingerError,
    InvalidTaskIdError,
    TaskDefinitionError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskIdError,
)
from ..model import TaskId
from ..registry import TaskRegistry
from . import console
from .fmt import causes_of, diagnostic_for, run, show
from .parser import (
    TASKFILE,
    Command,
    HarbingerFlag,
    Invoke,
    RunSelected,
    TaskParser,
    command,
)


def hint_missing_separator(cmd: Command, tasks: Sequence[TaskId], /) -> None:
    # Assuming someone tried running "harbinger greet Alice"
    # where we can tell that that the first one is a real task, but the latter aren't
    # it's possible that the user meant to pass args to the first task but forgot the
    # seperator "--"
    # We can provide a nice hint here
    match cmd:
        case RunSelected(names=[first, *rest]) if rest:
            first = TaskId.new(first)
            rest = (TaskId.new(task) for task in rest)
            if (
                first is not None
                and first in tasks
                and all(task is None or task not in tasks for task in rest)
            ):
                console.stderr("")
                console.hint(
                    f"if the values after {first!r} are arguments, use '--': "
                    f"[cyan]harbinger {first} -- <args>[/]"
                )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return cli(argv)
    except KeyboardInterrupt:
        console.error("interrupted")
        return 130


def cli(argv: Sequence[str] | None = None) -> int:
    cmd = command(sys.argv[1:] if argv is None else argv)

    try:
        registry = TaskRegistry.load(Path.cwd() / TASKFILE)
    except TaskFileNotFoundError as error:
        console.error_with_hint(
            error.msg,
            "create [cyan]tasks.py[/] here, or run harbinger from the project root",
        )
        return 2

    except TaskDefinitionError as error:
        err, hint = diagnostic_for(error)
        console.error_with_hint(err, hint)
        return 1

    except HarbingerError as error:
        console.error(error.msg)
        causes = causes_of(error)
        if causes:
            console.stderr(causes)
        return 1

    return execute(cmd, registry)


def execute(cmd: Command, registry: TaskRegistry, /) -> int:
    try:
        match cmd:
            case HarbingerFlag.ALL:
                tasks = registry.all()
                if not tasks:
                    console.error("no tasks found")
                    return 2
                run(tasks)

            case HarbingerFlag.DEFAULT:
                tasks = registry.default()
                if not tasks:
                    console.error("no default tasks")
                    return 2
                run(tasks)

            case HarbingerFlag.LIST:
                show(registry.all(), registry.file.name)

            case RunSelected(names=names):
                run(registry.select(names))

            case Invoke(name=name, argv=argv):
                task = registry.get(name)
                pos, kw = TaskParser(task).parse(argv)
                task.call(*pos, **kw)

    # Raised by registry.select() or registry.get()
    except InvalidTaskIdError as error:
        err, hint = diagnostic_for(error)
        console.error_with_hint(err, hint)
        hint_missing_separator(cmd, registry.ids())
        return 2

    # Raised by registry.select() or registry.get()
    except UndefinedTaskIdError as error:
        label = "task" if len(error.ids) == 1 else "tasks"
        names = ", ".join(f"[yellow]{n!r}[/]" for n in error.ids)
        console.error(f"unknown {label} {names}")

        available = registry.ids()
        hints = error.suggest(available)

        if hints:
            console.stderr("")
            suggested = ", ".join(f"[cyan]{h}[/]" for h in hints)
            console.hint(f"did you mean {suggested}?")

        elif available:
            console.stderr("")
            avail = ", ".join(f"[cyan]{a!r}[/]" for a in available)
            console.hint(f"available tasks: {avail}")

        hint_missing_separator(cmd, registry.ids())

        return 2

    except TaskError as error:
        console.error(f"task [cyan]{error.id!r}[/] failed")
        causes = causes_of(error)
        if causes:
            console.stderr(causes)
        return 1

    except HarbingerError as error:
        console.error(str(error))
        causes = causes_of(error)
        if causes:
            console.stderr(causes)
        return 1

    return 0
