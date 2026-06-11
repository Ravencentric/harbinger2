import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .core import REGISTRY
from .errors import InvalidTaskFileError, TaskFileNotFoundError


@dataclass(frozen=True, slots=True)
class TaskRunner:
    taskfile: Path

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

    def execute(self, names: Iterable[str] = ()) -> None:
        selected = names or REGISTRY.names()

        for name in selected:
            REGISTRY.call(name)
