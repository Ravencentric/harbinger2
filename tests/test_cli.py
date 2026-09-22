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


def test_task_file_syntax_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_file = tmp_path / "tasks.py"
    task_file.write_text("def broken(:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        f"""\
        error: could not load {task_file}

        caused by:
            0: SyntaxError: invalid syntax
               at tasks.py:1:12
        """
    )


def test_signature_inspection_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "tasks.py").write_text(
        dedent(
            """\
            from __future__ import annotations

            from harbinger import task

            def broken_annotation() -> object:
                raise ZeroDivisionError("broken annotation")

            @task
            def deploy(target: broken_annotation() = None) -> None: ...
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        """\
        error: could not inspect task 'deploy' signature

        tip: signature inspection raised ZeroDivisionError: broken annotation
        """
    )


def test_unresolved_annotation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "tasks.py").write_text(
        dedent(
            """\
            from __future__ import annotations

            from harbinger import task

            @task
            def deploy(target: MissingType = None) -> None: ...
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        """\
        error: could not inspect task 'deploy' signature

        tip: signature inspection raised NameError: name 'MissingType' is not defined
        """
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            """\
            from harbinger import task

            @task
            def deploy(target: str) -> None: ...
            """,
            """\
            error: task 'deploy' has parameter 'target' without a default

            tip: all task parameters must have default values
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(target: list[str] = None) -> None: ...
            """,
            """\
            error: task 'deploy' parameter 'target': unsupported annotation list[str]

            tip: supported types: int, float, str, bool, Path
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(force: bool = False) -> None: ...
            """,
            """\
            error: task 'deploy' has positional bool parameter 'force'

            tip: bool parameters must be keyword-only (use '*, force: bool = ...')
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def build_docs() -> None: ...

            @task(name="build-docs")
            def docs() -> None: ...
            """,
            """\
            error: duplicate task id 'build-docs'

            tip: two functions resolved to the same id; use @task(name=...) to disambiguate
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            async def deploy() -> None: ...
            """,
            """\
            error: task 'deploy' is an unsupported async function

            tip: wrap it in a regular task that runs or consumes it explicitly
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy():
                yield
            """,
            """\
            error: task 'deploy' is an unsupported generator function

            tip: wrap it in a regular task that runs or consumes it explicitly
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(**options: str) -> None: ...
            """,
            """\
            error: task 'deploy' cannot use **options

            tip: variadic keyword args are not supported; list parameters explicitly
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(*files: str, **options: str) -> None: ...
            """,
            """\
            error: task 'deploy' cannot use **options

            tip: variadic keyword args are not supported; list parameters explicitly
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(target: str = "prod", *files: str) -> None: ...
            """,
            """\
            error: task 'deploy' cannot mix *files with other parameters

            tip: remove the other parameters or replace *files with explicit parameters
            """,
        ),
        (
            """\
            from harbinger import task

            @task(name="deploy-")
            def deploy() -> None: ...
            """,
            """\
            error: invalid task id 'deploy-'

            tip: ids must start with a letter, end with a letter or number, and contain only printable non-whitespace characters
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(*, help: str = "") -> None: ...
            """,
            """\
            error: task 'deploy' parameter 'help' conflicts with reserved option '--help'

            tip: rename the parameter; --help is reserved for task help
            """,
        ),
        (
            """\
            from harbinger import task

            @task
            def deploy(*, force: bool = False, no_force: str = "") -> None: ...
            """,
            """\
            error: task 'deploy' parameters 'force' and 'no_force' both define option '--no-force'

            tip: rename one parameter so its command-line option is unique
            """,
        ),
    ],
    ids=[
        "missing-default",
        "unsupported-annotation",
        "positional-bool",
        "duplicate-id",
        "async",
        "generator",
        "variadic-keyword",
        "variadic-with-keyword",
        "mixed-variadic",
        "invalid-id",
        "reserved-option",
        "option-collision",
    ],
)
def test_task_definition_error(
    source: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "tasks.py").write_text(dedent(source), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(expected)


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


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (
            'raise RuntimeError("upload failed")',
            """\
            error: task 'deploy' failed

            caused by:
                0: RuntimeError: upload failed
                   in deploy() at tasks.py:11:9
                1: ConnectionError: connection refused
                   in connect() at tasks.py:4:5
            """,
        ),
        (
            'raise RuntimeError("upload failed") from None',
            """\
            error: task 'deploy' failed

            caused by:
                0: RuntimeError: upload failed
                   in deploy() at tasks.py:11:9
            """,
        ),
        (
            'raise RuntimeError("upload failed") from ValueError("explicit cause")',
            """\
            error: task 'deploy' failed

            caused by:
                0: RuntimeError: upload failed
                   in deploy() at tasks.py:11:9
                1: ValueError: explicit cause
            """,
        ),
    ],
    ids=["implicit-context", "suppressed-context", "explicit-cause"],
)
def test_task_failure(
    statement: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_file = tmp_path / "tasks.py"
    task_file.write_text(
        dedent(
            f"""\
            from harbinger import task

            def connect() -> None:
                raise ConnectionError("connection refused")

            @task
            def deploy() -> None:
                try:
                    connect()
                except ConnectionError:
                    {statement}
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(("deploy",)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(expected)


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

    @task(description="Deploy app.\n\nUpload the release.")
    def deploy() -> None: ...

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
    ("name", "expected"),
    [
        (
            "foo-",
            dedent(
                """\
                error: invalid task id 'foo-'

                tip: ids must start with a letter, end with a letter or number, and contain only printable non-whitespace characters
                """
            ),
        ),
        (
            "foo\x00bar",
            dedent(
                """\
                error: invalid task id 'foo\\x00bar'

                tip: ids must start with a letter, end with a letter or number, and contain only printable non-whitespace characters
                """
            ),
        ),
    ],
)
def test_invalid_task_id_diagnostic(
    name: str,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = TaskRegistry(Path("tasks.py"), {})

    assert execute(RunSelected((name,)), registry) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == expected


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        (
            "Alice",
            dedent(
                """\
                error: unknown task 'Alice'

                tip: if the values after 'greet' are arguments, use '--': harbinger greet -- <arg> ...
                """
            ),
        ),
        (
            "0",
            dedent(
                """\
                error: invalid task id '0'

                tip: ids must start with a letter, end with a letter or number, and contain only printable non-whitespace characters

                tip: if the values after 'greet' are arguments, use '--': harbinger greet -- <arg> ...
                """
            ),
        ),
    ],
)
def test_missing_separator_hint(
    capsys: pytest.CaptureFixture[str],
    argument: str,
    expected: str,
) -> None:
    @task
    def greet(name: str = "world") -> None: ...

    registered = Task.new(greet, greet.__harbinger_taskspec__)
    registry = TaskRegistry(
        Path("tasks.py"),
        {registered.id: registered},
    )

    assert execute(RunSelected(("greet", argument)), registry) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == expected


def test_close_task_match_wins_over_missing_separator_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @task
    def lint() -> None: ...

    @task
    def test() -> None: ...

    tasks = (
        Task.new(lint, lint.__harbinger_taskspec__),
        Task.new(test, test.__harbinger_taskspec__),
    )
    registry = TaskRegistry(Path("tasks.py"), {task.id: task for task in tasks})

    assert execute(RunSelected(("lint", "tes")), registry) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == dedent(
        """\
        error: unknown task 'tes'

        tip: did you mean 'test'?
        """
    )
