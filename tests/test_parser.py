import itertools
import os
from pathlib import Path
from textwrap import dedent
from typing import Literal

import pytest

from harbinger.cli.parser import HarbingerFlag, Invoke, RunSelected, TaskParser, command
from harbinger.model import Task, TaskFn, TaskSpec


class TaskParserTester:
    def __init__(self, func: TaskFn[..., object], /) -> None:
        self.task = Task.new(func, TaskSpec())
        self.parser = TaskParser(self.task)

    def parse(self, *argv: str) -> None:
        pos, kw = self.parser.parse(argv)
        self.task.call(*pos, **kw)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ((), HarbingerFlag.LIST),
        (("--list",), HarbingerFlag.LIST),
        (("--default",), HarbingerFlag.DEFAULT),
        (("--all",), HarbingerFlag.ALL),
        (("lint",), RunSelected(["lint"])),
        (("lint", "test"), RunSelected(["lint", "test"])),
        (("greet", "--"), Invoke("greet", ())),
        (("greet", "--", "Alice"), Invoke("greet", ("Alice",))),
    ],
)
def test_command(argv: tuple[str, ...], expected: object) -> None:
    assert command(argv) == expected


def test_command_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(os, "get_terminal_size", lambda _: os.terminal_size((80, 24)))

    with pytest.raises(SystemExit) as excinfo:
        command(("--help",))

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == dedent(
        """\
        usage: harbinger [--list | --all | --default]
               harbinger <task> [<task> ...]
               harbinger <task> -- [<arg> ...]

        Run tasks from tasks.py.

        Omit <task> to list available tasks.
        Specify multiple tasks to run them in order.
        Use '--' to pass arguments to a single task.

        positional arguments:
          <task>         tasks to run in order

        options:
          -h, --help     show this help message and exit
          -a, --all      run all tasks
          -d, --default  run default tasks only
          -l, --list     list available tasks without running them
          -V, --version  show program's version number and exit
        """
    )
    assert captured.err == ""


def test_fixed_task_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(os, "get_terminal_size", lambda _: os.terminal_size((80, 24)))

    def deploy(
        source_dir: Path = Path("src"),
        *,
        environment: Literal["dev", "prod"] = "dev",
        dry_run: bool = False,
        retries: int = 3,
    ) -> None:
        """Deploy a source directory."""

    with pytest.raises(SystemExit) as excinfo:
        TaskParserTester(deploy).parse("--help")

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == dedent(
        """\
        usage: harbinger deploy -- [-h] [--environment {dev, prod}]
                                   [--dry-run | --no-dry-run] [--retries RETRIES]
                                   [source-dir]

        Deploy a source directory.

        positional arguments:
          source-dir            default: src

        options:
          -h, --help            show this help message and exit
          --environment {dev, prod}
                                default: dev
          --dry-run, --no-dry-run
                                default: False
          --retries RETRIES     default: 3
        """
    )
    assert captured.err == ""


def test_variadic_task_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(os, "get_terminal_size", lambda _: os.terminal_size((80, 24)))

    def copy_files(
        *source_paths: Path,
        overwrite_files: bool = False,
    ) -> None:
        """Copy one or more source paths."""

    with pytest.raises(SystemExit) as excinfo:
        TaskParserTester(copy_files).parse("--help")

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == dedent(
        """\
        usage: harbinger copy-files -- [-h] [--overwrite-files | --no-overwrite-files]
                                       [source-paths ...]

        Copy one or more source paths.

        positional arguments:
          source-paths

        options:
          -h, --help            show this help message and exit
          --overwrite-files, --no-overwrite-files
                                default: False
        """
    )
    assert captured.err == ""


@pytest.mark.parametrize(
    "argv",
    [
        ("--all", "lint"),
        ("--default", "lint"),
        ("--list", "lint"),
    ],
)
def test_command_rejects_mode_with_tasks(
    argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        command(argv)

    assert excinfo.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ("--all", "--"),
        ("--default", "--", "argument"),
        ("--list", "--", "argument"),
        ("--", "argument"),
        ("lint", "test", "--"),
    ],
)
def test_command_rejects_invalid_separator_use(
    argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        command(argv)

    assert excinfo.value.code == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv", itertools.permutations(("--recursive", "a.txt", "b.txt"))
)
def test_variadic_with_keyword_flags(argv: tuple[str, ...]) -> None:
    expected = tuple(Path(arg) for arg in argv if arg != "--recursive")

    def cp(*paths: Path, recursive: bool = False) -> None:
        assert paths == expected
        assert recursive is True

    TaskParserTester(cp).parse(*argv)


def test_variadic_keyword_defaults() -> None:
    def cp(*paths: Path, recursive: bool = False) -> None:
        assert paths == (Path("a.txt"),)
        assert recursive is False

    TaskParserTester(cp).parse("a.txt")


def test_variadic_untyped() -> None:
    def files(*paths) -> None:
        assert paths == ("a", "b")

    TaskParserTester(files).parse("a", "b")


def test_variadic_empty() -> None:
    def files(*paths) -> None:
        assert paths == ()

    TaskParserTester(files).parse()


def test_fixed_positional_and_keyword() -> None:
    def greet(name: str = "world", *, count: int = 1, loud: bool = False) -> None:
        assert name == "alice"
        assert count == 3
        assert loud is True

    TaskParserTester(greet).parse("alice", "--count", "3", "--loud")


def test_fixed_defaults() -> None:
    def greet(name: str = "world", *, count: int = 1, loud: bool = False) -> None:
        assert name == "world"
        assert count == 1
        assert loud is False

    TaskParserTester(greet).parse()


def test_bool_no_prefix() -> None:
    def f(*, loud: bool = False) -> None:
        assert loud is False

    TaskParserTester(f).parse("--no-loud")


def test_keyword_flags_use_kebab_case() -> None:
    values = []

    def f(*, dry_run: bool = False) -> None:
        values.append(dry_run)

    TaskParserTester(f).parse("--dry-run")
    TaskParserTester(f).parse("--no-dry-run")

    assert values == [True, False]


def test_literal_choices() -> None:
    def greet(*, punct: Literal[".", "!"] = ".") -> None:
        assert punct == "!"

    TaskParserTester(greet).parse("--punct", "!")


def test_invalid_choice_exits(capsys: pytest.CaptureFixture[str]) -> None:
    def greet(*, punct: Literal[".", "!"] = ".") -> None: ...

    with pytest.raises(SystemExit) as excinfo:
        TaskParserTester(greet).parse("--punct", "?")

    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "error: argument --punct: invalid choice: '?'" in err
    assert "choose from" in err


def test_missing_flag_value_exits(capsys: pytest.CaptureFixture[str]) -> None:
    def f(*, count: int = 1) -> None: ...

    with pytest.raises(SystemExit) as excinfo:
        TaskParserTester(f).parse("--count")

    assert excinfo.value.code == 2
    assert "error: argument --count: expected one argument" in capsys.readouterr().err
