from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from harbinger import task
from harbinger.cli import execute, main
from harbinger.cli.parser import HarbingerFlag, RunSelected
from harbinger.model import Task
from harbinger.registry import TaskRegistry


def test_missing_task_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(()) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        f"""\
        error: task file not found: {tmp_path / "tasks.py"}

        tip: create tasks.py here, or run harbinger from the project root
        """
    )


def test_task_file_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_file = tmp_path / "tasks.py"
    task_file.write_text('raise RuntimeError("broken import")\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        f"""\
        error: could not load {task_file}

        caused by:
            0: RuntimeError: broken import
               in <module>() at tasks.py:1:1
        """
    )


def test_system_exit_while_loading_is_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_file = tmp_path / "tasks.py"
    task_file.write_text("raise SystemExit(0)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        f"""\
        error: could not load {task_file}

        caused by:
            0: SystemExit: 0
               in <module>() at tasks.py:1:1
        """
    )


def test_task_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_file = tmp_path / "tasks.py"
    task_file.write_text(
        dedent(
            """\
            from harbinger import task

            def connect() -> None:
                raise ConnectionError("connection refused")

            @task
            def deploy() -> None:
                try:
                    connect()
                except ConnectionError as source:
                    raise RuntimeError("upload failed") from source
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(("deploy",)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        """\
        error: task 'deploy' failed

        caused by:
            0: RuntimeError: upload failed
               in deploy() at tasks.py:11:9
            1: ConnectionError: connection refused
               in connect() at tasks.py:4:5
        """
    )


def test_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "tasks.py").write_text(
        dedent(
            """\
            from harbinger import task

            @task
            def wait() -> None:
                raise KeyboardInterrupt
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(("wait",)) == 130
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: interrupted\n"


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


@pytest.mark.parametrize("code", [0, 2])
def test_system_exit_is_task_failure(
    code: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called: list[str] = []

    @task
    def stop() -> None:
        called.append("stop")
        raise SystemExit(code)

    @task
    def later() -> None:
        called.append("later")

    tasks = (
        Task.new(stop, stop.__harbinger_taskspec__),
        Task.new(later, later.__harbinger_taskspec__),
    )
    registry = TaskRegistry(Path("tasks.py"), {task.id: task for task in tasks})

    assert execute(RunSelected(("stop", "later")), registry) == 1
    assert called == ["stop"]
    captured = capsys.readouterr()
    assert captured.out == "$ stop\n"
    assert f"0: SystemExit: {code}\n" in captured.err


def test_repeated_task_runs_once_per_occurrence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    called: list[str] = []

    @task
    def repeat() -> None:
        called.append("repeat")

    registered = Task.new(repeat, repeat.__harbinger_taskspec__)
    registry = TaskRegistry(Path("tasks.py"), {registered.id: registered})

    assert execute(RunSelected(("repeat", "repeat")), registry) == 0
    assert called == ["repeat", "repeat"]
    captured = capsys.readouterr()
    assert captured.out == "$ repeat\n\n$ repeat\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("bad_name", "diagnostic"),
    [
        ("missing", "unknown task 'missing'"),
        ("0", "invalid task id '0'"),
    ],
)
def test_invalid_selection_does_not_start_any_tasks(
    bad_name: str,
    diagnostic: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called: list[str] = []

    @task
    def first() -> None:
        called.append("first")

    @task
    def last() -> None:
        called.append("last")

    tasks = (
        Task.new(first, first.__harbinger_taskspec__),
        Task.new(last, last.__harbinger_taskspec__),
    )
    registry = TaskRegistry(Path("tasks.py"), {task.id: task for task in tasks})

    assert execute(RunSelected(("first", bad_name, "last")), registry) == 2
    assert called == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert diagnostic in captured.err


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
