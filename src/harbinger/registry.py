from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, overload

from .errors import (
    DuplicateTaskError,
    InvalidTaskFileError,
    TaskDefinitionError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from .model import Task, TaskFn, TaskSpec
from .signature import Signature

if TYPE_CHECKING:
    from .model import P, R, TaskDecorator

logger = logging.getLogger(__name__)

MARKER: Final = "_harbinger_task"


@overload
def task(fn: TaskFn[P, R], /) -> TaskFn[P, R]: ...


@overload
def task(
    *, name: str | None = None, description: str | None = None
) -> TaskDecorator[P, R]: ...


def task(
    fn: TaskFn[P, R] | None = None,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
) -> TaskFn[P, R] | TaskDecorator[P, R]:
    spec = TaskSpec(name=name, description=description)

    def decorator(fn: TaskFn[P, R], /) -> TaskFn[P, R]:
        if getattr(fn, MARKER, None) is not None:
            raise TaskDefinitionError(f"function {fn.__name__!r} is already a task")
        setattr(fn, MARKER, spec)
        return fn

    return decorator(fn) if fn is not None else decorator


def load(path: Path) -> TaskRegistry:
    """Import a taskfile, returning a registry built from its @task-marked functions."""
    if not path.is_file():
        raise TaskFileNotFoundError(path)

    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise InvalidTaskFileError(path)

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as source:
        raise InvalidTaskFileError(path) from source

    found: list[Task] = []
    for obj in vars(module).values():
        ms = getattr(obj, MARKER, None)
        if isinstance(ms, TaskSpec):
            found.append(build(obj, ms))
    return TaskRegistry.from_tasks(found)


def build(func: TaskFn[..., object], spec: TaskSpec) -> Task:
    orig = spec.name or func.__name__
    name = orig.replace("_", "-")
    description = spec.description
    if description is None and func.__doc__:
        description = func.__doc__.strip()
    signature = Signature.parse(func)
    logger.debug(f"registered task: {name}")
    return Task(func=func, name=name, signature=signature, description=description)


@dataclass(frozen=True, slots=True)
class TaskRegistry:
    store: dict[str, Task]

    @classmethod
    def from_tasks(cls, tasks: list[Task]) -> TaskRegistry:
        inner: dict[str, Task] = {}
        for t in tasks:
            if t.name in inner:
                raise DuplicateTaskError(f"duplicate task registered: {t.name!r}")
            inner[t.name] = t
        return cls(store=inner)

    def tasks(self) -> tuple[Task, ...]:
        return tuple(self.store.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self.store.keys())

    def get(self, name: str) -> Task:
        task = self.store.get(name)
        if task is None:
            raise UndefinedTaskNameError(name)
        return task
