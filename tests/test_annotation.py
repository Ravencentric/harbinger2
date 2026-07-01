from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Literal

import pytest

from harbinger.annotation import (
    IntLiteralType,
    ScalarType,
    StringLiteralType,
    Untyped,
    parse,
)


@pytest.mark.parametrize(
    "annotation",
    [
        inspect.Parameter.empty,
        object,
        Any,
    ],
)
def test_parse_empty(annotation: object) -> None:
    assert parse(annotation) == Untyped()


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (int, int),
        (float, float),
        (str, str),
        (bool, bool),
        (Path, Path),
    ],
)
def test_parse_scalar(
    annotation: type[object],
    expected: type[object],
) -> None:
    assert parse(annotation) == ScalarType(expected)


def test_parse_string_literal() -> None:
    assert parse(Literal["foo", "bar"]) == StringLiteralType(
        ("foo", "bar"),
    )


def test_parse_singleton_string_literal() -> None:
    assert parse(Literal["foo"]) == StringLiteralType(
        ("foo",),
    )


def test_parse_int_literal() -> None:
    assert parse(Literal[1, 2, 3]) == IntLiteralType(
        (1, 2, 3),
    )


@pytest.mark.parametrize(
    "annotation",
    [
        Literal[1, "foo"],
        Literal[True],
        Literal[Path("a")],
    ],
)
def test_parse_unsupported_literal(annotation: object) -> None:
    assert parse(annotation) is None


@pytest.mark.parametrize(
    "annotation",
    [
        list[int],
        dict[str, int],
        tuple[int, ...],
        set[int],
        type(None),
        bytes,
        complex,
    ],
)
def test_parse_unsupported(annotation: object) -> None:
    assert parse(annotation) is None
