from __future__ import annotations

import os
import traceback
from collections.abc import Sequence

from .. import annotation
from ..errors import (
    AlreadyTaskError,
    DuplicateTaskNameError,
    HarbingerError,
    MissingDefaultError,
    MixedVariadicSignatureError,
    PositionalBoolError,
    TaskDefinitionError,
    UnsupportedAnnotationError,
    VarKeywordError,
)
from ..model import Task
from . import console


def location_of(exc: BaseException) -> str | None:
    if (tb := exc.__traceback__) is None:
        return None

    frame = next(
        (
            frame
            for frame in reversed(traceback.extract_tb(tb))
            # Skip frames like "<stdin>" or "<frozen importlib._bootstrap>"
            if not frame.filename.startswith("<")
        ),
        None,
    )

    if frame is None:
        return None

    filename = os.path.relpath(frame.filename, start=os.getcwd())
    col = f":{frame.colno + 1}" if frame.colno is not None else ""

    return f"in [magenta]{frame.name}()[/] at [cyan]{filename}:{frame.lineno}{col}[/]"


def causes_of(error: HarbingerError) -> str:
    if not (causes := error.causes()):
        return ""

    lines = ["", "[yellow]caused by:[/]"]

    for i, cause in enumerate(causes):
        message = f": {cause}" if str(cause) else ""
        lines.append(f"    {i}: [magenta]{type(cause).__name__}[/]{message}")

        if where := location_of(cause):
            lines.append(f"       {where}")

    return "\n".join(lines)


def run(tasks: Sequence[Task], /) -> None:
    for i, task in enumerate(tasks):
        if len(tasks) > 1:
            console.stdout(f"[yellow]$[/] [cyan]{task.name}[/]")
        task.call()
        if len(tasks) > 1 and i < len(tasks) - 1:
            console.stdout("")


def show(tasks: Sequence[Task], taskfile: str, /) -> None:
    if not tasks:
        console.stdout("[dim]No tasks found.[/]")
        return

    total = len(tasks)
    header = f"{taskfile}: [dim]{total} {'task' if total == 1 else 'tasks'} (* = default)[/]\n"
    console.stdout(header)

    width = max(len(task.name) for task in tasks) + 1

    for task in tasks:
        star = "[yellow]*[/]" if task.default else " "
        desc = f"  [dim]{task.description}[/]" if task.description else ""
        console.stdout(f"  {star} [cyan]{task.name.ljust(width)}[/]{desc}")


def diagnostic_for(error: TaskDefinitionError) -> tuple[str, str]:

    match error:
        case AlreadyTaskError(task=task):
            return (
                f"function [yellow]{task!r}[/] is already a task",
                "each function can only be decorated with [magenta]@task[/] once",
            )

        case DuplicateTaskNameError(task=task):
            return (
                f"duplicate task name [yellow]{task!r}[/]",
                "two functions resolved to the same name; use [magenta]@task(name=...)[/] to disambiguate",
            )

        case VarKeywordError(task=task, param=param):
            return (
                f"task [cyan]{task!r}[/] cannot use [magenta]**{param}[/]",
                "variadic keyword args are not supported; list parameters explicitly",
            )

        case MissingDefaultError(task=task, param=param):
            return (
                f"task [cyan]{task!r}[/] has parameter [magenta]{param!r}[/] without a default",
                "all task parameters must have default values",
            )

        case PositionalBoolError(task=task, param=param):
            return (
                f"task [cyan]{task!r}[/] has positional bool parameter [magenta]{param!r}[/]",
                f"bool parameters must be keyword-only (use [magenta]'*, {param}: bool = ...'[/])",
            )

        case UnsupportedAnnotationError(annotation=ann, task=task, param=param):
            supported = ", ".join(
                f"[magenta]{type.__name__}[/]" for type in annotation.SCALARS
            )
            return (
                f"task [cyan]{task!r}[/] parameter [magenta]{param!r}[/]: unsupported annotation [magenta]{ann!r}[/]",
                f"supported types: {supported}",
            )

        case MixedVariadicSignatureError(task=task, param=param):
            return (
                f"task [cyan]{task!r}[/] cannot mix [magenta]*{param}[/] with other parameters",
                f"remove the other parameters or replace [magenta]*{param}[/] with explicit parameters",
            )

        case _:
            raise AssertionError(
                f"unhandled TaskDefinitionError: {type(error).__name__}: {error}"
            )
