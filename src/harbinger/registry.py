import dataclasses
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import DuplicateTaskError, TaskError, UndefinedTaskNameError
from .typs import Task, TaskFn

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaskRegistry:
    inner: dict[str, Task[..., object]] = dataclasses.field(default_factory=dict)

    def tasks(self) -> Iterable[Task[..., object]]:
        yield from self.inner.values()

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

        self.inner[name] = Task(func, name=name, description=description)
        logger.debug(f"registered task: {name}")

    def call(self, name: str) -> None:
        task = self.inner.get(name)

        if task is None:
            raise UndefinedTaskNameError

        try:
            task.call()
        except Exception as source:
            raise TaskError from source
