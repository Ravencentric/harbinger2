from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence, final

from . import annotation
from .annotation import Scalar, ScalarType, TypeSpec, Untyped
from .errors import (
    MissingDefaultError,
    MixedVariadicSignatureError,
    PositionalBoolError,
    UnsupportedAnnotationError,
    VarKeywordError,
)

if TYPE_CHECKING:
    from .model import TaskFn


@final
@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type: TypeSpec
    default: Scalar | None
    is_keyword: bool


@final
@dataclass(frozen=True, slots=True)
class FixedSignature:
    parameters: Sequence[Parameter]


@final
@dataclass(frozen=True, slots=True)
class VariadicSignature:
    name: str
    type: ScalarType | Untyped
    kwargs: Sequence[Parameter] = ()


def typespec(name: str, param: inspect.Parameter) -> TypeSpec:
    type = annotation.parse(param.annotation)
    if type is None:
        raise UnsupportedAnnotationError(
            task=name,
            param=param.name,
            annotation=param.annotation,
        )
    return type


def variadic(name: str, params: Sequence[inspect.Parameter]) -> VariadicSignature:
    posparam, *kwparams = params

    postype = annotation.parse(posparam.annotation)
    if not isinstance(postype, (ScalarType, Untyped)):
        raise UnsupportedAnnotationError(
            task=name,
            param=posparam.name,
            annotation=posparam.annotation,
        )

    kwargs: list[Parameter] = []
    for param in kwparams:
        if param.default is inspect.Parameter.empty:
            raise MissingDefaultError(name, param.name)

        kwargs.append(
            Parameter(
                name=param.name,
                type=typespec(name, param),
                default=param.default,
                is_keyword=True,
            )
        )

    return VariadicSignature(name=posparam.name, type=postype, kwargs=kwargs)


def fixed(name: str, params: Sequence[inspect.Parameter]) -> FixedSignature:
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

        parameters.append(
            Parameter(
                name=param.name,
                type=typespec(name, param),
                default=param.default,
                is_keyword=(param.kind is inspect.Parameter.KEYWORD_ONLY),
            )
        )
    return FixedSignature(parameters)


def signature(func: TaskFn[..., object]) -> FixedSignature | VariadicSignature:
    name = func.__name__
    params = tuple(inspect.signature(func).parameters.values())
    if params and params[0].kind is inspect.Parameter.VAR_POSITIONAL:
        return variadic(name, params)
    return fixed(name, params)
