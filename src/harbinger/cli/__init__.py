from __future__ import annotations

import sys
from pathlib import Path

from ..errors import (
    HarbingerError,
    TaskDefinitionError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from ..registry import TaskRegistry
from . import console
from .fmt import causes_of, diagnostic_for, run, show
from .parser import (
    TASKFILE,
    HarbingerFlag,
    Invoke,
    RunSelected,
    Subparser,
    command,
)


def main() -> int:
    cmd = command(sys.argv[1:])

    try:
        registry = TaskRegistry.load(Path.cwd() / TASKFILE)
    except TaskFileNotFoundError as error:
        console.error(error.msg)
        console.stderr("")
        console.hint(
            "create [cyan]tasks.py[/] here, or run harbinger from the project root"
        )
        return 2

    except TaskDefinitionError as error:
        err, hint = diagnostic_for(error)
        console.error(err)
        console.stderr("")
        console.hint(hint)
        return 1

    except HarbingerError as error:
        console.error(error.msg)
        causes = causes_of(error)
        if causes:
            console.stderr(causes)
        return 1

    try:
        match cmd:
            case HarbingerFlag.ALL:
                run(registry.all())

            case HarbingerFlag.DEFAULT:
                run(registry.default())

            case HarbingerFlag.LIST:
                show(registry.all(), TASKFILE)

            case RunSelected(names=names):
                run(registry.select(names))

            case Invoke(name=name, argv=argv):
                task = registry.get(name)
                pos, kw = Subparser(task).parse(argv)
                task.call(*pos, **kw)

    except UndefinedTaskNameError as error:
        label = "task" if len(error.names) == 1 else "tasks"
        names = ", ".join(f"[yellow]{n!r}[/]" for n in error.names)
        console.error(f"unknown {label} {names}")

        available = registry.names()
        hints = error.suggest(available)

        if hints:
            console.stderr("")
            suggested = ", ".join(f"[cyan]{h}[/]" for h in hints)
            console.hint(f"did you mean {suggested}?")

        elif available:
            console.stderr("")
            avail = ", ".join(f"[cyan]{a!r}[/]" for a in available)
            console.hint(f"available tasks: {avail}")

        return 2

    except TaskError as error:
        console.error(f"task [cyan]{error.name!r}[/] failed")
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
