from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Final, TypeAlias, final

Scalar: TypeAlias = int | float | str | bool | Path
SCALARS: Final[tuple[type[Scalar], ...]] = typing.get_args(Scalar)
UNANNOTATED: Final[tuple[object, ...]] = (inspect.Parameter.empty, object, Any)


@final
@dataclass(frozen=True, slots=True)
class Untyped:
    pass


@final
@dataclass(frozen=True, slots=True)
class ScalarType:
    type: type[Scalar]


@final
@dataclass(frozen=True, slots=True)
class StringLiteralType:
    type: ClassVar[type[str]] = str
    values: tuple[str, ...]


@final
@dataclass(frozen=True, slots=True)
class IntLiteralType:
    type: ClassVar[type[int]] = int
    values: tuple[int, ...]


TypeSpec: TypeAlias = ScalarType | StringLiteralType | IntLiteralType | Untyped


def parse(annotation: object) -> TypeSpec | None:
    if annotation in UNANNOTATED:
        return Untyped()
    if annotation in SCALARS:
        # Type checkers apparently cannot narrow this down
        # because it's unsafe to do for reasons unknown to me.
        return ScalarType(annotation)  # pyrefly: ignore[bad-argument-type]

    if typing.get_origin(annotation) is typing.Literal:
        args = typing.get_args(annotation)
        if all(arg.__class__ is str for arg in args):
            return StringLiteralType(args)
        if all(arg.__class__ is int for arg in args):
            return IntLiteralType(args)

    return None
