from datetime import datetime
from pathlib import Path

import pytest

from harbinger.errors import TaskDefinitionError
from harbinger.model import TaskFn
from harbinger.signature import ParameterKind, Signature


def signature(fn: TaskFn[..., object]) -> Signature:
    return Signature.parse(fn)


def test_no_params() -> None:
    def f() -> None: ...

    sig = signature(f)
    assert len(sig.parameters) == 0


def test_positional_with_default() -> None:
    def f(a: int = 1) -> None: ...

    sig = signature(f)
    assert len(sig.parameters) == 1
    p = sig.parameters[0]
    assert p.name == "a"
    assert p.converter is int
    assert p.default == 1
    assert p.kind is ParameterKind.POSITIONAL


def test_positional_only_collapses_to_positional() -> None:
    def f(a: int = 1, /) -> None: ...

    p = signature(f).parameters[0]
    assert p.kind is ParameterKind.POSITIONAL


def test_keyword_only() -> None:
    def f(*, a: int = 1) -> None: ...

    p = signature(f).parameters[0]
    assert p.kind is ParameterKind.KEYWORD


def test_bool_annotation_is_keyword() -> None:
    def f(*, loud: bool = False) -> None: ...

    p = signature(f).parameters[0]
    assert p.converter is bool
    assert p.kind is ParameterKind.KEYWORD


def test_str_annotation_is_str() -> None:
    def f(a: str = "x") -> None: ...

    assert signature(f).parameters[0].converter is str


def test_path_annotation_is_path() -> None:
    def f(p: Path = Path(".")) -> None: ...

    assert signature(f).parameters[0].converter is Path


def test_var_positional_rejected() -> None:
    def f(*a: int) -> None: ...

    with pytest.raises(TaskDefinitionError):
        signature(f)


def test_var_keyword_rejected() -> None:
    def f(**k: int) -> None: ...

    with pytest.raises(TaskDefinitionError):
        signature(f)


def test_missing_default_rejected() -> None:
    def f(a: int) -> None: ...

    with pytest.raises(TaskDefinitionError):
        signature(f)


def test_float_annotation_rejected() -> None:
    def f(a: float = 1.0) -> None: ...

    with pytest.raises(TaskDefinitionError):
        signature(f)


def test_datetime_annotation_rejected() -> None:
    def f(t: datetime = datetime(2024, 1, 1)) -> None: ...

    with pytest.raises(TaskDefinitionError):
        signature(f)
