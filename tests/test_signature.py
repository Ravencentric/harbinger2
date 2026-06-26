import pytest

from harbinger.errors import (
    MissingDefaultError,
    PositionalBoolError,
    VarKeywordError,
)
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


def test_var_positional_accepted() -> None:
    def f(*args: int) -> None: ...

    p = signature(f).parameters[0]
    assert p.name == "args"
    assert p.converter is int
    assert p.default == ()
    assert p.kind is ParameterKind.VAR_POSITIONAL


def test_var_keyword_rejected() -> None:
    def f(**k: int) -> None: ...

    with pytest.raises(VarKeywordError):
        signature(f)


def test_missing_default_rejected() -> None:
    def f(a: int) -> None: ...

    with pytest.raises(MissingDefaultError):
        signature(f)


def test_positional_bool_rejected() -> None:
    def f(loud: bool = False) -> None: ...

    with pytest.raises(PositionalBoolError):
        signature(f)
