from __future__ import annotations

import difflib
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import TaskId


class HarbingerError(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(msg)

    def causes(self) -> list[BaseException]:
        causes = []
        current = self.__cause__
        while current is not None:
            causes.append(current)
            current = current.__cause__
        return causes


class TaskFileNotFoundError(HarbingerError):
    def __init__(self, file: Path) -> None:
        self.file = file
        msg = f"task file not found: {file}"
        super().__init__(msg)


class InvalidTaskFileError(HarbingerError):
    def __init__(self, file: Path) -> None:
        self.file = file
        msg = f"could not load {file}"
        super().__init__(msg)


class UndefinedTaskIdError(HarbingerError):
    def __init__(self, *ids: str) -> None:
        self.ids = tuple(ids)
        label = "task" if len(self.ids) == 1 else "tasks"
        msg = f"unknown {label} {', '.join(repr(n) for n in self.ids)}"
        super().__init__(msg)

    def suggest(self, available: Sequence[TaskId]) -> Sequence[str]:
        hints = []
        for id in self.ids:
            match = difflib.get_close_matches(id, available, n=1)
            if match:
                hints.append(f"{match[0]!r}")

        return hints


class TaskError(HarbingerError):
    def __init__(self, id: TaskId) -> None:
        self.id = id
        msg = f"task {id!r} failed"
        super().__init__(msg)


class TaskDefinitionError(HarbingerError):
    pass


class DuplicateTaskIdError(TaskDefinitionError):
    def __init__(self, id: TaskId) -> None:
        self.id = id
        msg = f"duplicate task id {id!r}"
        super().__init__(msg)


class VarKeywordError(TaskDefinitionError):
    def __init__(self, id: TaskId, param: str) -> None:
        self.id = id
        self.param = param
        msg = f"task {id!r} cannot use **{param}"
        super().__init__(msg)


class MissingDefaultError(TaskDefinitionError):
    def __init__(self, id: TaskId, param: str) -> None:
        self.id = id
        self.param = param
        msg = f"task {id!r} has parameter {param!r} without a default"
        super().__init__(msg)


class PositionalBoolError(TaskDefinitionError):
    def __init__(self, id: TaskId, param: str) -> None:
        self.id = id
        self.param = param
        msg = f"task {id!r} has positional bool parameter {param!r}"
        super().__init__(msg)


class UnsupportedAnnotationError(TaskDefinitionError):
    def __init__(self, id: TaskId, param: str, annotation: object) -> None:
        self.annotation = annotation
        self.id = id
        self.param = param
        msg = f"task {id!r} parameter {param!r}: unsupported annotation {annotation!r}"
        super().__init__(msg)


class MixedVariadicSignatureError(TaskDefinitionError):
    def __init__(self, id: TaskId, param: str) -> None:
        self.id = id
        self.param = param
        msg = f"task {id!r} cannot mix *{param} with other parameters"
        super().__init__(msg)


class InvalidTaskIdError(TaskDefinitionError):
    def __init__(self, *ids: str) -> None:
        self.ids = ids
        label = "task id" if len(self.ids) == 1 else "task ids"
        msg = f"invalid {label} {', '.join(repr(n) for n in self.ids)}"
        super().__init__(msg)
