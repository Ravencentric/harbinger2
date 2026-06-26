from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, overload

from .errors import (
    AlreadyTaskError,
    DuplicateTaskNameError,
    HarbingerError,
    InvalidTaskFileError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from .model import Task, TaskFn, TaskSpec

if TYPE_CHECKING:
    from .model import P, R, TaskDecorator

MARKER: Final = "__harbinger_task__"


@overload
def task(fn: TaskFn[P, R], /) -> TaskFn[P, R]: ...


@overload
def task(
    *,
    name: str | None = None,
    description: str | None = None,
    default: bool = True,
) -> TaskDecorator[P, R]: ...


def task(
    fn: TaskFn[P, R] | None = None,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
    default: bool = True,
) -> TaskFn[P, R] | TaskDecorator[P, R]:
    spec = TaskSpec(name=name, description=description, default=default)

    def decorator(fn: TaskFn[P, R], /) -> TaskFn[P, R]:
        if getattr(fn, MARKER, None) is not None:
            raise AlreadyTaskError(fn.__name__)
        setattr(fn, MARKER, spec)
        return fn

    return decorator(fn) if fn is not None else decorator


@dataclass(frozen=True, slots=True)
class TaskRegistry:
    store: dict[str, Task]

    @classmethod
    def load(cls, path: Path) -> TaskRegistry:
        if not path.is_file():
            raise TaskFileNotFoundError(path)

        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise InvalidTaskFileError(path)

        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except HarbingerError:
            raise

        except Exception as source:
            raise InvalidTaskFileError(path) from source

        store: dict[str, Task] = {}
        for obj in vars(module).values():
            spec = getattr(obj, MARKER, None)
            if spec is not None:
                task = Task.from_func(obj, spec)
                if task.name in store:
                    raise DuplicateTaskNameError(task.name)
                store[task.name] = task

        return cls(store)

    def all(self) -> tuple[Task, ...]:
        return tuple(self.store.values())

    def default(self) -> tuple[Task, ...]:
        return tuple(t for t in self.store.values() if t.default)

    def names(self) -> tuple[str, ...]:
        return tuple(self.store.keys())

    def select(self, names: Sequence[str]) -> tuple[Task, ...]:
        missing = tuple(n for n in names if n not in self.store)
        if missing:
            raise UndefinedTaskNameError(missing)
        return tuple(self.store[n] for n in names)

    def get(self, name: str) -> Task:
        task = self.store.get(name)
        if task is None:
            raise UndefinedTaskNameError((name,))
        return task
