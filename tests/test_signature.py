import pytest

from harbinger.annotation import ScalarType
from harbinger.errors import (
    MissingDefaultError,
    PositionalBoolError,
    VarKeywordError,
)
from harbinger.model import TaskId
from harbinger.signature import (
    FixedSignature,
    VariadicSignature,
    signature,
)


def test_no_params() -> None:
    def f() -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, FixedSignature)
    assert len(sig.parameters) == 0


def test_positional_with_default() -> None:
    def f(a: int = 1) -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, FixedSignature)
    assert len(sig.parameters) == 1
    p = sig.parameters[0]
    assert p.name == "a"
    assert p.type == ScalarType(int)
    assert p.default == 1
    assert p.is_keyword is False


def test_positional_only_collapses_to_positional() -> None:
    def f(a: int = 1, /) -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, FixedSignature)
    assert sig.parameters[0].is_keyword is False


def test_keyword_only() -> None:
    def f(*, a: int = 1) -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, FixedSignature)
    assert sig.parameters[0].is_keyword is True


def test_bool_annotation_is_keyword() -> None:
    def f(*, loud: bool = False) -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, FixedSignature)
    param = sig.parameters[0]
    assert param.type == ScalarType(bool)
    assert param.is_keyword is True


def test_var_args() -> None:
    def f(*args: int) -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, VariadicSignature)
    assert sig.name == "args"
    assert sig.type == ScalarType(int)
    assert len(sig.kwargs) == 0


def test_var_args_with_keywords() -> None:
    def f(*args: str, flag: int = 0, loud: bool = False) -> None: ...

    sig = signature(f, id=TaskId("f"))
    assert isinstance(sig, VariadicSignature)
    assert sig.name == "args"
    assert sig.type == ScalarType(str)
    assert len(sig.kwargs) == 2
    flag, loud = sig.kwargs
    assert flag.name == "flag"
    assert flag.type == ScalarType(int)
    assert flag.default == 0
    assert flag.is_keyword is True
    assert loud.name == "loud"
    assert loud.type == ScalarType(bool)
    assert loud.default is False
    assert loud.is_keyword is True


def test_var_keyword_rejected() -> None:
    def f(**k: int) -> None: ...

    with pytest.raises(VarKeywordError):
        signature(f, id=TaskId("f"))


def test_missing_default_rejected() -> None:
    def f(a: int) -> None: ...

    with pytest.raises(MissingDefaultError):
        signature(f, id=TaskId("f"))


def test_positional_bool_rejected() -> None:
    def f(loud: bool = False) -> None: ...

    with pytest.raises(PositionalBoolError):
        signature(f, id=TaskId("f"))
