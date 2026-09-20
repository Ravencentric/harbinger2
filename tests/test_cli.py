from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from harbinger import task
from harbinger.cli import execute
from harbinger.cli.parser import HarbingerFlag, RunSelected
from harbinger.model import Task
from harbinger.registry import TaskRegistry


def test_empty_list_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    registry = TaskRegistry(Path("tasks.py"), {})

    assert execute(HarbingerFlag.LIST, registry) == 0
    captured = capsys.readouterr()
    assert captured.out == "tasks.py: 0 tasks\n"
    assert captured.err == ""


def test_list(capsys: pytest.CaptureFixture[str]) -> None:
    @task(default=True)
    def lint() -> None:
        """Check code."""

    @task
    def sum() -> None: ...

    @task
    def deploy() -> None:
        """Deploy app."""

    tasks = (
        Task.new(lint, lint.__harbinger_taskspec__),
        Task.new(sum, sum.__harbinger_taskspec__),
        Task.new(deploy, deploy.__harbinger_taskspec__),
    )
    registry = TaskRegistry(Path("tasks.py"), {task.id: task for task in tasks})

    assert execute(HarbingerFlag.LIST, registry) == 0
    captured = capsys.readouterr()
    assert captured.out == dedent(
        """\
        tasks.py: 3 tasks (* = default)

          * lint     Check code.
            sum
            deploy   Deploy app.
        """
    )
    assert captured.err == ""


def test_all_rejects_empty_registry(capsys: pytest.CaptureFixture[str]) -> None:
    registry = TaskRegistry(Path("tasks.py"), {})

    assert execute(HarbingerFlag.ALL, registry) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: no tasks found\n"


def test_default_rejects_empty_selection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @task
    def available() -> None: ...

    registered = Task.new(available, available.__harbinger_taskspec__)
    registry = TaskRegistry(Path("tasks.py"), {registered.id: registered})

    assert execute(HarbingerFlag.DEFAULT, registry) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: no default tasks\n"


@pytest.mark.parametrize(
    "command",
    [
        RunSelected(("fail", "later")),
        HarbingerFlag.ALL,
        HarbingerFlag.DEFAULT,
    ],
)
def test_multiple_tasks_stop_at_first_failure(
    command: RunSelected | HarbingerFlag,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called: list[str] = []

    @task(default=True)
    def fail() -> None:
        called.append("fail")
        raise RuntimeError("boom")

    @task(default=True)
    def later() -> None:
        called.append("later")

    tasks = (
        Task.new(fail, fail.__harbinger_taskspec__),
        Task.new(later, later.__harbinger_taskspec__),
    )
    registry = TaskRegistry(Path("tasks.py"), {task.id: task for task in tasks})

    assert execute(command, registry) == 1
    assert called == ["fail"]
    captured = capsys.readouterr()
    assert captured.out == "$ fail\n"
    assert captured.err.startswith("error: task 'fail' failed\n")


@pytest.mark.parametrize(
    ("argument", "diagnostic"),
    [
        ("Alice", "unknown task 'Alice'"),
        ("0", "invalid task id '0'"),
    ],
)
def test_missing_separator_hint(
    capsys: pytest.CaptureFixture[str],
    argument: str,
    diagnostic: str,
) -> None:
    @task
    def greet(name: str = "world") -> None: ...

    registered = Task.new(greet, greet.__harbinger_taskspec__)
    registry = TaskRegistry(
        Path("tasks.py"),
        {registered.id: registered},
    )

    assert execute(RunSelected(("greet", argument)), registry) == 2
    err = capsys.readouterr().err
    assert diagnostic in err
    assert "if the values after 'greet' are arguments" in err
    assert "harbinger greet -- <args>" in err
