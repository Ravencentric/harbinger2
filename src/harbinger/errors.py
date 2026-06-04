class HarbingerError(Exception):
    pass


class TaskFileNotFoundError(HarbingerError):
    pass


class InvalidTaskFileError(HarbingerError):
    pass


class UndefinedTaskNameError(HarbingerError):
    pass


class TaskError(HarbingerError):
    pass


class DuplicateTaskError(HarbingerError):
    pass
