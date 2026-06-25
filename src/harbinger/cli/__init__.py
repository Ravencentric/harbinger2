from __future__ import annotations

import sys
from pathlib import Path

from . import console
from ..errors import (
    HarbingerError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from ..registry import TaskRegistry
from .parser import TASKFILE, Invoke, ListTasks, RunAll, RunDefault, RunSelected, Subparser, parse
from .present import render_causes, run, show


def main() -> int:
    command = parse(sys.argv[1:])

    try:
        registry = TaskRegistry.load(Path.cwd() / TASKFILE)
    except TaskFileNotFoundError as error:
        console.error(str(error))
        console.stderr("")
        console.hint("create tasks.py here, or run harbinger from the project root")
        return 1
    except HarbingerError as error:
        console.error(str(error))
        causes = render_causes(error)
        if causes:
            console.stderr(causes)
        return 1

    try:
        match command:
            case RunAll():
                run(registry.tasks())

            case RunDefault():
                run(registry.default())

            case ListTasks():
                show(registry, TASKFILE)

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
        return 1
    except TaskError as error:
        console.error(f"task [cyan]{error.name!r}[/] failed")
        causes = render_causes(error)
        if causes:
            console.stderr(causes)
        return 1
    except HarbingerError as error:
        console.error(str(error))
        causes = render_causes(error)
        if causes:
            console.stderr(causes)
        return 1

    return 0
