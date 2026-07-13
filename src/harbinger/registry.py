from __future__ import annotations

import importlib.util
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, overload

from .errors import (
    DuplicateTaskIdError,
    HarbingerError,
    InvalidTaskFileError,
    InvalidTaskIdError,
    TaskFileNotFoundError,
    UndefinedTaskIdError,
)
from .model import MARKER, NamedCallable, Task, TaskFn, TaskId, TaskSpec

if TYPE_CHECKING:
    from .model import P, R, TaskDecorator


@overload
def task(fn: NamedCallable[P, R], /) -> TaskFn[P, R]: ...


@overload
def task(
    *,
    name: str | None = None,
    description: str | None = None,
    default: bool = False,
) -> TaskDecorator[P, R]: ...


def task(
    fn: NamedCallable[P, R] | None = None,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
    default: bool = False,
) -> TaskFn[P, R] | TaskDecorator[P, R]:
    spec = TaskSpec(name=name, description=description, default=default)

    def decorator(fn: NamedCallable[P, R], /) -> TaskFn[P, R]:
        setattr(fn, MARKER, spec)
        return fn  # pyrefly: ignore[bad-return]

    return decorator(fn) if fn is not None else decorator


@dataclass(frozen=True, slots=True)
class TaskRegistry:
    file: Path
    store: Mapping[TaskId, Task]

    @classmethod
    def load(cls, file: Path) -> TaskRegistry:
        if not file.is_file():
            raise TaskFileNotFoundError(file)

        spec = importlib.util.spec_from_file_location(file.stem, file)
        if spec is None or spec.loader is None:
            raise InvalidTaskFileError(file)

        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except HarbingerError:
            # We have better error handling implemented for
            # HarbingerError, so we want to propoagate it up
            # instead of having it swallowed by the catch-all
            # below
            raise

        except Exception as source:
            raise InvalidTaskFileError(file) from source

        store: dict[TaskId, Task] = {}
        for func in vars(module).values():
            spec = getattr(func, MARKER, None)
            if spec is not None:
                task = Task.new(func, spec)
                if task.id in store:
                    raise DuplicateTaskIdError(task.id)
                store[task.id] = task

        return cls(file, store)

    def all(self) -> tuple[Task, ...]:
        return tuple(self.store.values())

    def default(self) -> tuple[Task, ...]:
        return tuple(t for t in self.store.values() if t.default)

    def ids(self) -> tuple[TaskId, ...]:
        return tuple(t.id for t in self.store.values())

    def select(self, names: Sequence[str]) -> tuple[Task, ...]:
        missing: list[str] = []
        invalid: list[str] = []
        ids: list[TaskId] = []
        for n in names:
            id = TaskId.new(n)
            if id is None:
                invalid.append(n)
            elif id not in self.store:
                missing.append(n)
            else:
                ids.append(id)
        if invalid:
            raise InvalidTaskIdError(*invalid)
        if missing:
            raise UndefinedTaskIdError(*missing)
        return tuple(self.store[id] for id in ids)

    def get(self, name: str) -> Task:
        id = TaskId.new(name)
        if id is None:
            raise InvalidTaskIdError(name)
        if id not in self.store:
            raise UndefinedTaskIdError(name)
        return self.store[id]
