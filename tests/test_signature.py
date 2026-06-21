import inspect
from pathlib import Path

import pytest

from harbinger.errors import TaskDefinitionError
from harbinger.typs import ParameterKind, Signature


def _parse(fn: object) -> Signature:
    return Signature.parse(fn, task_name=fn.__name__)  # type: ignore[arg-type]


def test_no_params() -> None:
    def f() -> None: ...
    assert _parse(f).parameters == ()


def test_positional_with_default() -> None:
    def f(a: int = 1) -> None: ...
    sig = _parse(f)
    assert len(sig.parameters) == 1
    p = sig.parameters[0]
    assert p.name == "a"
    assert p.converter is int
    assert p.default == 1
    assert p.kind is ParameterKind.POSITIONAL


def test_positional_only_collapses_to_positional() -> None:
    ns: dict[str, object] = {}
    exec("def f(a: int = 1, /):\n    ...\n", ns)
    p = _parse(ns["f"]).parameters[0]
    assert p.kind is ParameterKind.POSITIONAL


def test_keyword_only() -> None:
    def f(*, a: int = 1) -> None: ...
    p = _parse(f).parameters[0]
    assert p.kind is ParameterKind.KEYWORD


def test_bool_annotation_is_keyword() -> None:
    def f(*, loud: bool = False) -> None: ...
    p = _parse(f).parameters[0]
    assert p.converter is bool
    assert p.kind is ParameterKind.KEYWORD


def test_missing_annotation_defaults_to_str() -> None:
    def f(a="x") -> None: ...
    assert _parse(f).parameters[0].converter is str


def test_str_annotation_is_str() -> None:
    def f(a: str = "x") -> None: ...
    assert _parse(f).parameters[0].converter is str


def test_object_annotation_is_str() -> None:
    def f(a: object = 0) -> None: ...
    assert _parse(f).parameters[0].converter is str


def test_path_annotation_is_path() -> None:
    def f(p: Path = Path(".")) -> None: ...
    assert _parse(f).parameters[0].converter is Path


def test_var_positional_rejected() -> None:
    def f(*a: int) -> None: ...
    with pytest.raises(TaskDefinitionError):
        _parse(f)


def test_var_keyword_rejected() -> None:
    def f(**k: int) -> None: ...
    with pytest.raises(TaskDefinitionError):
        _parse(f)


def test_missing_default_rejected() -> None:
    def f(a: int) -> None: ...
    with pytest.raises(TaskDefinitionError):
        _parse(f)


def test_non_callable_annotation_rejected() -> None:
    ns: dict[str, object] = {}
    exec("def f(a: 42 = 'x') -> None:\n    ...\n", ns)
    with pytest.raises(TaskDefinitionError):
        Signature.parse(ns["f"], task_name="f")  # type: ignore[arg-type]
