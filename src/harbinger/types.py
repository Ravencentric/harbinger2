from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, ParamSpec, Protocol, TypeAlias, TypeVar, final

P = ParamSpec("P")
R = TypeVar("R", covariant=True)


class TaskFn(Protocol, Generic[P, R]):
    @property
    def __name__(self) -> str: ...
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


TaskDecorator: TypeAlias = Callable[[TaskFn[P, R]], TaskFn[P, R]]


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Task(Generic[P, R]):
    name: str
    func: TaskFn[P, R]

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self.func(*args, **kwargs)
