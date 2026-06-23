from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeAlias, TypeVar, cast

from .errors import TaskDefinitionError

T = TypeVar("T")

ConverterFn: TypeAlias = Callable[[str], object]

SUPPORTED: Final[set[ConverterFn]] = {str, int, float, bool, Path}
NOOP: Final[set[object]] = {inspect.Parameter.empty, object, Any}


def identity(o: T) -> T:
    return o


def converter_for(annotation: object) -> ConverterFn:
    if annotation in NOOP:
        return identity
    if annotation in SUPPORTED:
        return cast(ConverterFn, annotation)
    allowed = ", ".join(t.__name__ for t in SUPPORTED)
    raise TaskDefinitionError(
        f"unsupported annotation {annotation!r}. supported types: {allowed}"
    )
