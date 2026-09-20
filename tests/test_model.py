from __future__ import annotations

import pytest

from harbinger import task
from harbinger.errors import UnsupportedTaskFunctionError
from harbinger.model import Task, TaskFn, TaskId


@task
async def async_task() -> None: ...


@task
def generator_task():
    yield


@task
async def async_generator_task():
    yield


@pytest.mark.parametrize(
    ("func", "kind"),
    [
        (async_task, "async"),
        (generator_task, "generator"),
        (async_generator_task, "async generator"),
    ],
)
def test_unsupported_task_function(func: TaskFn[..., object], kind: str) -> None:
    with pytest.raises(UnsupportedTaskFunctionError) as excinfo:
        Task.new(func, func.__harbinger_taskspec__)

    assert excinfo.value.id == func.__name__.replace("_", "-")
    assert excinfo.value.kind == kind


def test_description_is_cleaned() -> None:
    @task
    def deploy() -> None:
        """Deploy the application.

        Build assets and upload the release.
        """

    registered = Task.new(deploy, deploy.__harbinger_taskspec__)

    assert registered.description == (
        "Deploy the application.\n\nBuild assets and upload the release."
    )


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
        "foo\x00bar",
    ],
)
def test_invalid(raw: str) -> None:
    assert TaskId.new(raw) is None
