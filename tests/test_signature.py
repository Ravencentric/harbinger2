import pytest

from harbinger.errors import (
    MissingDefaultError,
    PositionalBoolError,
    VarKeywordError,
)
from harbinger.model import TaskFn
from harbinger.signature import (
    FixedSignature,
    ParameterKind,
    Signature,
    VariadicSignature,
)


def signature(fn: TaskFn[..., object]) -> Signature:
    return Signature.parse(fn)


def test_no_params() -> None:
    def f() -> None: ...

    sig = signature(f)
    assert isinstance(sig.kind, FixedSignature)
    assert len(sig.kind.parameters) == 0


def test_positional_with_default() -> None:
    def f(a: int = 1) -> None: ...

    sig = signature(f)
    assert isinstance(sig.kind, FixedSignature)
    assert len(sig.kind.parameters) == 1
    p = sig.kind.parameters[0]
    assert p.name == "a"
    assert p.converter is int
    assert p.default == 1
    assert p.kind is ParameterKind.POSITIONAL


def test_positional_only_collapses_to_positional() -> None:
    def f(a: int = 1, /) -> None: ...

    sig = signature(f)
    assert isinstance(sig.kind, FixedSignature)
    assert sig.kind.parameters[0].kind is ParameterKind.POSITIONAL


def test_keyword_only() -> None:
    def f(*, a: int = 1) -> None: ...

    sig = signature(f)
    assert isinstance(sig.kind, FixedSignature)
    assert sig.kind.parameters[0].kind is ParameterKind.KEYWORD


def test_bool_annotation_is_keyword() -> None:
    def f(*, loud: bool = False) -> None: ...

    sig = signature(f)
    assert isinstance(sig.kind, FixedSignature)
    param = sig.kind.parameters[0]
    assert param.converter is bool
    assert param.kind is ParameterKind.KEYWORD


def test_var_args() -> None:
    def f(*args: int) -> None: ...

    sig = signature(f)
    assert isinstance(sig.kind, VariadicSignature)
    assert sig.kind.name == "args"
    assert sig.kind.converter is int


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
