from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Generic, ParamSpec, Protocol, TypeAlias, TypeVar, final

from .errors import InvalidTaskIdError, TaskError
from .signature import FixedSignature, VariadicSignature, signature

P = ParamSpec("P")
R = TypeVar("R", covariant=True)

MARKER: Final = "__harbinger_taskspec__"


class NamedCallable(Protocol, Generic[P, R]):
    @property
    def __name__(self) -> str: ...

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


class TaskFn(NamedCallable[P, R]):
    @property
    def __name__(self) -> str: ...
    @property
    def __harbinger_taskspec__(self) -> TaskSpec: ...

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


TaskDecorator: TypeAlias = Callable[[NamedCallable[P, R]], TaskFn[P, R]]


@final
class TaskId(str):
    @classmethod
    def new(cls, raw: str) -> TaskId | None:
        name = raw.replace("_", "-")

        if not name:
            return None

        if not name.isprintable():
            return None

        if not name[0].isalpha():
            return None

        if not name[-1].isalnum():
            return None

        if any(char.isspace() for char in name):
            return None

        return cls(name)


@final
@dataclass(frozen=True, slots=True)
class TaskSpec:
    name: str | None = None
    description: str | None = None
    default: bool = False


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Task:
    func: TaskFn[..., object]
    id: TaskId
    description: str | None = None
    default: bool = False
    signature: FixedSignature | VariadicSignature

    @classmethod
    def new(cls, func: TaskFn[..., object], spec: TaskSpec) -> Task:
        fname = func.__name__
        resolved = spec.name or fname
        id = TaskId.new(resolved)
        if id is None:
            raise InvalidTaskIdError(resolved, func=fname)
        description = spec.description
        if description is None and func.__doc__:
            description = func.__doc__.strip()

        return cls(
            func=func,
            id=id,
            description=description,
            default=spec.default,
            signature=signature(func, id=id),
        )

    def call(self, *args: object, **kwargs: object) -> None:
        try:
            self.func(*args, **kwargs)
        except Exception as source:
            raise TaskError(self.id) from source
