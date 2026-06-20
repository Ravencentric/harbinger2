import dataclasses
import importlib.util
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    DuplicateTaskError,
    InvalidTaskFileError,
    TaskFileNotFoundError,
    UndefinedTaskNameError,
)
from .typs import Signature, Task, TaskFn

logger = logging.getLogger(__name__)


def load(taskfile: Path) -> None:
    """Import a taskfile, populating the global registry via @task decorators."""
    if not taskfile.is_file():
        raise TaskFileNotFoundError(taskfile)

    spec = importlib.util.spec_from_file_location(taskfile.stem, taskfile)

    if spec is None or spec.loader is None:
        raise InvalidTaskFileError(taskfile)

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as source:
        raise InvalidTaskFileError(taskfile) from source


@dataclass(frozen=True, slots=True)
class TaskRegistry:
    inner: dict[str, Task[..., object]] = dataclasses.field(default_factory=dict)

    def tasks(self) -> Iterable[Task[..., object]]:
        yield from self.inner.values()

    def names(self) -> Iterable[str]:
        yield from self.inner.keys()

    def register(
        self,
        func: TaskFn[..., object],
        /,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        orig = name or func.__name__
        name = orig.replace("_", "-")

        description = description or func.__doc__
        if description:
            description = description.strip()

        if name in self.inner:
            raise DuplicateTaskError(f"duplicate task registered: {name!r}")

        signature = Signature.parse(func, task_name=name)

        self.inner[name] = Task(
            func, name=name, signature=signature, description=description
        )
        logger.debug(f"registered task: {name}")

    def get(self, name: str) -> Task[..., object]:
        func = self.inner.get(name)
        if func is None:
            raise UndefinedTaskNameError(name)
        return func

    def run(self, name: str, *args: object, **kwargs: object) -> None:
        self.get(name).call(*args, **kwargs)
