from __future__ import annotations

from collections.abc import Callable
from dataclasses import KW_ONLY, dataclass
from typing import Generic, ParamSpec, Protocol, TypeAlias, TypeVar, final

from .errors import TaskError
from .signature import Signature

P = ParamSpec("P")
R = TypeVar("R", covariant=True)


class TaskFn(Protocol, Generic[P, R]):
    @property
    def __name__(self) -> str: ...

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


TaskDecorator: TypeAlias = Callable[[TaskFn[P, R]], TaskFn[P, R]]


@final
@dataclass(frozen=True, slots=True)
class TaskSpec:
    name: str | None = None
    description: str | None = None


@final
@dataclass(frozen=True, slots=True)
class Task:
    func: Callable[..., object]
    _: KW_ONLY
    name: str
    signature: Signature
    description: str | None = None

    def call(self, *args: object, **kwargs: object) -> object:
        try:
            result = self.func(*args, **kwargs)
        except Exception as source:
            raise TaskError(self.name) from source
        else:
            return result
