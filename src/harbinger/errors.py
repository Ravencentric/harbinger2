import difflib
from collections.abc import Sequence
from pathlib import Path


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


class UndefinedTaskNameError(HarbingerError):
    def __init__(self, names: Sequence[str]) -> None:
        self.names = tuple(names)
        label = "task" if len(self.names) == 1 else "tasks"
        msg = f"unknown {label} {', '.join(repr(n) for n in self.names)}"
        super().__init__(msg)

    def suggest(self, available: Sequence[str]) -> Sequence[str]:
        hints = []
        for name in self.names:
            match = difflib.get_close_matches(name, available, n=1)
            if match:
                hints.append(f"{match[0]!r}")

        return hints


class TaskError(HarbingerError):
    def __init__(self, name: str) -> None:
        self.name = name
        msg = f"task {name!r} failed"
        super().__init__(msg)


class TaskDefinitionError(HarbingerError):
    pass


class AlreadyTaskError(TaskDefinitionError):
    def __init__(self, task: str) -> None:
        self.task = task
        msg = f"function {task!r} is already a task"
        super().__init__(msg)


class DuplicateTaskNameError(TaskDefinitionError):
    def __init__(self, task: str) -> None:
        self.task = task
        msg = f"duplicate task name {task!r}"
        super().__init__(msg)


class VarKeywordError(TaskDefinitionError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        msg = f"task {task!r} cannot use **{param}"
        super().__init__(msg)


class MissingDefaultError(TaskDefinitionError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        msg = f"task {task!r} has parameter {param!r} without a default"
        super().__init__(msg)


class PositionalBoolError(TaskDefinitionError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        msg = f"task {task!r} has positional bool parameter {param!r}"
        super().__init__(msg)


class UnsupportedAnnotationError(TaskDefinitionError):
    def __init__(self, task: str, param: str, annotation: object) -> None:
        self.annotation = annotation
        self.task = task
        self.param = param
        msg = (
            f"task {task!r} parameter {param!r}: unsupported annotation {annotation!r}"
        )
        super().__init__(msg)


class MixedVariadicSignatureError(TaskDefinitionError):
    def __init__(self, task: str, param: str) -> None:
        self.task = task
        self.param = param
        msg = f"task {task!r} cannot mix *{param} with other parameters"
        super().__init__(msg)
