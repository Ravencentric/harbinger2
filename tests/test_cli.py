from __future__ import annotations

from pathlib import Path

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
