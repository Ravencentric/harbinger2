from pathlib import Path


class HarbingerError(Exception):
    pass


class TaskFileNotFoundError(HarbingerError):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.path = path


class InvalidTaskFileError(HarbingerError):
    pass


class UndefinedTaskNameError(HarbingerError):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class TaskError(HarbingerError):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class TaskDefinitionError(HarbingerError):
    pass
