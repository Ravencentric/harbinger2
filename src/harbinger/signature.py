from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Self, Sequence, final

from .coerce import converter_for
from .errors import (
    MissingDefaultError,
    MixedVariadicSignatureError,
    PositionalBoolError,
    UnsupportedAnnotationError,
    VarKeywordError,
)

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
@dataclass(frozen=True, slots=True)
class FixedSignature:
    parameters: Sequence[Parameter]


@final
@dataclass(frozen=True, slots=True)
class VariadicSignature:
    name: str
    converter: Callable[[str], object]


@final
@dataclass(frozen=True, slots=True)
class Signature:
    kind: FixedSignature | VariadicSignature

    @classmethod
    def parse(cls, func: TaskFn[..., object]) -> Self:
        name = func.__name__
        params = tuple(inspect.signature(func).parameters.values())

        if len(params) == 1 and params[0].kind is inspect.Parameter.VAR_POSITIONAL:
            param = params[0]
            converter = converter_for(param.annotation)
            if converter is None:
                raise UnsupportedAnnotationError(
                    task=name,
                    param=param.name,
                    annotation=param.annotation,
                )

            return cls(
                VariadicSignature(
                    name=param.name,
                    converter=converter,
                )
            )

        parameters: list[Parameter] = []

        for param in params:
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                raise VarKeywordError(name, param.name)

            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                raise MixedVariadicSignatureError(name, param.name)

            if param.default is inspect.Parameter.empty:
                raise MissingDefaultError(name, param.name)

            if (
                param.annotation is bool
                and param.kind is not inspect.Parameter.KEYWORD_ONLY
            ):
                raise PositionalBoolError(name, param.name)

            converter = converter_for(param.annotation)
            if converter is None:
                raise UnsupportedAnnotationError(
                    task=name,
                    param=param.name,
                    annotation=param.annotation,
                )

            parameters.append(
                Parameter(
                    name=param.name,
                    converter=converter,
                    default=param.default,
                    kind=(
                        ParameterKind.KEYWORD
                        if param.kind is inspect.Parameter.KEYWORD_ONLY
                        else ParameterKind.POSITIONAL
                    ),
                )
            )

        return cls(FixedSignature(parameters))
