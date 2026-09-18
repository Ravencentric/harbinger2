from __future__ import annotations

from pathlib import Path

import pytest

from harbinger import task
from harbinger.cli import execute
from harbinger.cli.parser import RunSelected
from harbinger.model import Task
from harbinger.registry import TaskRegistry


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
