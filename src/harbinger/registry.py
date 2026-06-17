import dataclasses
import inspect
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import DuplicateTaskError, UndefinedTaskNameError
from .typs import Task, TaskFn

logger = logging.getLogger(__name__)


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

        self.inner[name] = Task(
            func, name=name, sig=inspect.signature(func), description=description
        )
        logger.debug(f"registered task: {name}")

    def get(self, name: str) -> Task[..., object]:
        func = self.inner.get(name)
        if func is None:
            raise UndefinedTaskNameError(name)
        return func

    def call(self, name: str, *args: object, **kwargs: object) -> None:
        self.get(name).call(*args, **kwargs)
