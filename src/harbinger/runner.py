from __future__ import annotations

import importlib.util
import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .core import REGISTRY
from .errors import (
    InvalidTaskFileError,
    TaskFileNotFoundError,
)


@dataclass(frozen=True, slots=True)
class TaskRunner:
    taskfile: Path

    def __init__(self, taskfile: Path) -> None:
        object.__setattr__(self, "taskfile", taskfile)
        self.load()

    def load(self) -> None:
        if not self.taskfile.is_file():
            raise TaskFileNotFoundError(self.taskfile)

        spec = importlib.util.spec_from_file_location(
            self.taskfile.stem,
            self.taskfile,
        )

        if spec is None or spec.loader is None:
            raise InvalidTaskFileError(self.taskfile)

        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except Exception as source:
            raise InvalidTaskFileError(self.taskfile) from source

    def run(self, names: Iterable[str] = ()) -> None:
        selected = tuple(names) or tuple(REGISTRY.names())

        for name in selected:
            REGISTRY.call(name)

    def invoke(
        self,
        name: str,
        /,
        *args: object,
        **kwargs: object,
    ) -> None:
        task = REGISTRY.get(name)
        bound = inspect.signature(task.func).bind(
            *args,
            **kwargs,
        )

        task.call(
            *bound.args,
            **bound.kwargs,
        )