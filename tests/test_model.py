from __future__ import annotations

import pytest

from harbinger.model import TaskId


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("greet", "greet"),
        ("my_task", "my-task"),
        ("my-task", "my-task"),
        ("a", "a"),
        ("éfoo", "éfoo"),
    ],
)
def test_valid(raw: str, expected: str) -> None:
    assert TaskId.new(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "_foo",
        "_",
        "__init__",
        "9foo",
        "foo-",
        "my task",
        "my\ttask",
    ],
)
def test_invalid(raw: str) -> None:
    assert TaskId.new(raw) is None
