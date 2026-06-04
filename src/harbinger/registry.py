import dataclasses
import logging
from dataclasses import dataclass

from .types import Task, TaskFn

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaskRegistry:
    inner: dict[str, Task[..., object]] = dataclasses.field(default_factory=dict)

    def register(
        self, func: TaskFn[..., object], /, *, name: str | None = None
    ) -> None:
        orig = name or func.__name__
        name = orig.replace("_", "-")

        if name in self.inner:
            raise KeyError(f"duplicate task registered: {name!r}")

        self.inner[name] = Task(name=name, func=func)
        logger.debug(f"registered task: {name}")
