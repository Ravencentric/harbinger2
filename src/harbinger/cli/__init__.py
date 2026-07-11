from __future__ import annotations

import sys
from pathlib import Path

from ..errors import (
    HarbingerError,
    InvalidTaskIdError,
    TaskDefinitionError,
    TaskError,
    TaskFileNotFoundError,
    UndefinedTaskIdError,
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

    try:
        match cmd:
            case HarbingerFlag.ALL:
                run(registry.all())

            case HarbingerFlag.DEFAULT:
                run(registry.default())

            case HarbingerFlag.LIST:
                show(registry.all(), str(registry.file))

            case RunSelected(names=names):
                run(registry.select(names))

            case Invoke(name=name, argv=argv):
                task = registry.get(name)
                pos, kw = Subparser(task).parse(argv)
                task.call(*pos, **kw)

    # Raised by registry.select() or registry.get()
    except InvalidTaskIdError as error:
        err, hint = diagnostic_for(error)
        console.error_with_hint(err, hint)
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

        # Assuming someone tried running "harbinger greet Alice"
        # where we can tell that that the first one is a real task, but the latter aren't
        # it's possible that the user meant to pass args to the first task but forgot the
        # seperator "--"
        # We can provide a nice hint here
        if (
            # Atleast two names: greet Alice
            len(error.ids) >= 2
            # greet is a Task
            and error.ids[0] in available
            # The remaining aren't a task
            and all(id not in available for id in error.ids[1:])
        ):
            console.stderr("")
            console.hint(
                "to pass arguments to a task, use '--': "
                "[cyan]harbinger <task> -- <args>[/]"
            )

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
