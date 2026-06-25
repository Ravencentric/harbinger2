from __future__ import annotations

import os
import traceback
from collections.abc import Sequence
from pathlib import Path

from . import console
from ..errors import HarbingerError
from ..model import Task
from ..registry import TaskRegistry


def location_of(exc: BaseException) -> str | None:
    if exc.__traceback__ is None:
        return None
    cwd = Path.cwd()
    # extract_tb returns FrameSummary objects; reversed walks innermost-first.
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename.startswith("<"):
            continue
        filename = os.path.relpath(frame.filename, start=cwd)
        # FrameSummary.colno is 0-based; editors/IDEs expect 1-based.
        col = f":{frame.colno + 1}" if frame.colno is not None else ""
        return f"in [cyan]{frame.name}()[/] at [cyan]{filename}:{frame.lineno}{col}[/]"
    return None


def render_causes(error: HarbingerError) -> str:
    causes = error.causes()
    if not causes:
        return ""
    lines = ["", "[yellow]caused by:[/]"]
    for i, cause in enumerate(causes):
        type_name = type(cause).__name__
        message = str(cause)
        if message:
            lines.append(f"    [yellow]{i}:[/] [magenta]{type_name}[/]: {message}")
        else:
            lines.append(f"    [yellow]{i}:[/] [magenta]{type_name}[/]")
        where = location_of(cause)
        if where is not None:
            lines.append(f"       {where}")
    return "\n".join(lines)


def run(tasks: Sequence[Task], /) -> None:
    multi = len(tasks) > 1
    for task in tasks:
        if multi:
            console.stdout(f"[yellow]$[/] [cyan]{task.name}[/]")
        task.call()
        console.stdout("")


def show(registry: TaskRegistry, taskfile: str, /) -> None:
    tasks = registry.tasks()

    if not tasks:
        console.stdout("[dim]No tasks found.[/]")
        return

    n = len(tasks)
    console.stdout(
        f"{taskfile}: [dim]{n} {'task' if n == 1 else 'tasks'} (* = default)[/]"
    )
    console.stdout("")

    width = max(len(t.name) for t in tasks)

    for task in tasks:
        star = "[yellow]*[/]" if task.default else "[dim] [/]"
        desc = f"  [dim]{task.description}[/]" if task.description else ""
        console.stdout(f"  {star} [cyan]{task.name.ljust(width)}[/]{desc}")
