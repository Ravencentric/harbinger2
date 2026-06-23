from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, final

from .coerce import converter_for
from .errors import TaskDefinitionError

if TYPE_CHECKING:
    from .model import TaskFn


class ParameterKind(IntEnum):
    POSITIONAL = 0
    KEYWORD = 1

    def is_positional(self) -> bool:
        return self is ParameterKind.POSITIONAL

    def is_keyword(self) -> bool:
        return self is ParameterKind.KEYWORD


@final
@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    converter: Callable[[str], object]
    default: object
    kind: ParameterKind


@final
@dataclass
class Signature:
    parameters: Sequence[Parameter]

    @classmethod
    def parse(cls, func: TaskFn[..., object]) -> Signature:
        name = func.__name__
        sig = inspect.signature(func)
        parameters: list[Parameter] = []

        for param in sig.parameters.values():
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                raise TaskDefinitionError(f"task {name!r} cannot use *{param.name}.")
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                raise TaskDefinitionError(f"task {name!r} cannot use **{param.name}.")
            if param.default is inspect.Parameter.empty:
                raise TaskDefinitionError(
                    f"task {name!r} has parameter {param.name!r} without a default. "
                    "All task parameters must have default values."
                )
            if param.annotation is bool and param.kind is not inspect.Parameter.KEYWORD_ONLY:
                raise TaskDefinitionError(
                    f"task {name!r} has positional bool parameter {param.name!r}; "
                    f"bool parameters must be keyword-only (use '*, {param.name}: bool = ...')."
                )

            kind = (
                ParameterKind.KEYWORD
                if param.kind is inspect.Parameter.KEYWORD_ONLY
                else ParameterKind.POSITIONAL
            )

            parameters.append(
                Parameter(
                    name=param.name,
                    converter=converter_for(param.annotation),
                    default=param.default,
                    kind=kind,
                )
            )

        return cls(parameters)
