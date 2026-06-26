import difflib
from collections.abc import Sequence
from pathlib import Path
from typing import TypeAlias


class HarbingerError(Exception):
    def causes(self) -> list[BaseException]:
        causes: list[BaseException] = []
        current: BaseException | None = self.__cause__
        while current is not None:
            causes.append(current)
            current = current.__cause__
        return causes


class TaskFileNotFoundError(HarbingerError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"task file not found: {path}")


class InvalidTaskFileError(HarbingerError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"could not load {path}")


class UndefinedTaskNameError(HarbingerError):
    def __init__(self, names: Sequence[str]) -> None:
        self.names: tuple[str, ...] = tuple(names)
        label = "task" if len(self.names) == 1 else "tasks"
        super().__init__(f"unknown {label} {', '.join(repr(n) for n in self.names)}")

    def suggest(self, available: Sequence[str]) -> list[str]:
        hints: list[str] = []
        for name in self.names:
            match = difflib.get_close_matches(name, tuple(available), n=1)
            if match:
                hints.append(f"{match[0]!r}")
        return hints


class TaskError(HarbingerError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"task {name!r} failed")


class AlreadyTaskError(HarbingerError):
    def __init__(self, func: str) -> None:
        self.func_name = func
        super().__init__(f"function {func!r} is already a task")


class DuplicateTaskNameError(HarbingerError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"duplicate task name {name!r}")


class VarKeywordError(HarbingerError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        super().__init__(f"task {task!r} cannot use **{param}")


class MissingDefaultError(HarbingerError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        super().__init__(f"task {task!r} has parameter {param!r} without a default")


class PositionalBoolError(HarbingerError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        super().__init__(f"task {task!r} has positional bool parameter {param!r}")


class UnsupportedAnnotationError(HarbingerError):
    def __init__(self, annotation: object, task: str, param: str) -> None:
        self.annotation = annotation
        self.task = task
        self.param = param
        super().__init__(
            f"task {task!r} parameter {param!r}: unsupported annotation {annotation!r}"
        )


class MixedVariadicSignatureError(HarbingerError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        super().__init__(f"task {task!r} cannot mix *{param} with other parameters")


TaskDefinitionError: TypeAlias = (
    AlreadyTaskError
    | DuplicateTaskNameError
    | VarKeywordError
    | MissingDefaultError
    | PositionalBoolError
    | UnsupportedAnnotationError
    | MixedVariadicSignatureError
)
