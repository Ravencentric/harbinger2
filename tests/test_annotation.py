from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Literal

import pytest

from harbinger.annotation import EmptyType, LiteralType, ScalarType, parse


@pytest.mark.parametrize(
    "annotation",
    [
        inspect.Parameter.empty,
        object,
        Any,
    ],
)
def test_parse_empty(annotation: object) -> None:
    assert parse(annotation) == EmptyType()


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
    assert parse(Literal["foo", "bar"]) == LiteralType(
        ("foo", "bar"),
    )


def test_parse_singleton_string_literal() -> None:
    assert parse(Literal["foo"]) == LiteralType(
        ("foo",),
    )


@pytest.mark.parametrize(
    "annotation",
    [
        Literal[1],
        Literal[1, 2],
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