import difflib
from collections.abc import Sequence
from pathlib import Path


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


class TaskDefinitionError(HarbingerError):
    pass
