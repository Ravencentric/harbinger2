from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, final

from .errors import TaskDefinitionError


class ParameterKind(IntEnum):
    POSITIONAL = 0
    KEYWORD = 1


# ponytail: Parameter/Signature are constructed only by Signature.parse; the
# invariants (default is never empty, converter is a 1-arg callable, name is a
# legal identifier) are established there and not re-checked. Convention-only,
# no __post_init__ guards. `kind` is narrowed to ParameterKind so VAR_POSITIONAL
# / VAR_KEYWORD are unrepresentable at the type level, not just filtered.
@final
@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    converter: Callable[[str], object]
    default: object
    kind: ParameterKind


@final
@dataclass(frozen=True, slots=True)
class Signature:
    parameters: tuple[Parameter, ...]

    @classmethod
    def parse(cls, func: Callable[..., object], *, task_name: str) -> Signature:
        sig = inspect.signature(func)
        parameters: list[Parameter] = []
        for param in sig.parameters.values():
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                raise TaskDefinitionError(
                    f"task {task_name!r} cannot use *{param.name}. "
                    "Harbinger requires explicit, strongly-typed parameters."
                )
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                raise TaskDefinitionError(
                    f"task {task_name!r} cannot use **{param.name}. "
                    "Harbinger requires explicit, strongly-typed parameters."
                )
            if param.default is inspect.Parameter.empty:
                raise TaskDefinitionError(
                    f"task {task_name!r} has parameter {param.name!r} without a default. "
                    "All task parameters must have default values."
                )

            anno = param.annotation
            # ponytail: argv is strings, so `str` here is a no-op pass-through,
            # not a coercion. `object`/`Any` = "I don't know" -> str is the
            # sensible CLI default; only missing annotation strictly needs it.
            if anno in (inspect.Parameter.empty, str, object, Any):
                converter = str
            elif callable(anno):
                converter = anno
            else:
                raise TaskDefinitionError(
                    f"task {task_name!r} parameter {param.name!r} has invalid annotation. annotation {anno!r} is not callable"
                )

            # ponytail: POSITIONAL_ONLY + POSITIONAL_OR_KEYWORD both collapse to
            # POSITIONAL; task params always have defaults, so the distinction
            # is moot for invocation. KEYWORD_ONLY -> KEYWORD.
            kind = (
                ParameterKind.KEYWORD
                if param.kind is inspect.Parameter.KEYWORD_ONLY
                else ParameterKind.POSITIONAL
            )
            parameters.append(
                Parameter(
                    name=param.name,
                    converter=converter,
                    default=param.default,
                    kind=kind,
                )
            )

        return cls(parameters=tuple(parameters))
