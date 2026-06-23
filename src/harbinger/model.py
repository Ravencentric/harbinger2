from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
    default: bool = True


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Task:
    func: TaskFn[..., object]
    name: str
    description: str | None = None
    default: bool = True
    signature: Signature

    @classmethod
    def from_func(cls, func: TaskFn[..., object], spec: TaskSpec) -> Task:
        name = (spec.name or func.__name__).replace("_", "-")
        description = spec.description
        if description is None and func.__doc__:
            description = func.__doc__.strip()

        return cls(
            func=func,
            name=name,
            description=description,
            default=spec.default,
            signature=Signature.parse(func),
        )

    def call(self, *args: object, **kwargs: object) -> None:
        try:
            self.func(*args, **kwargs)
        except Exception as source:
            raise TaskError(self.name) from source
