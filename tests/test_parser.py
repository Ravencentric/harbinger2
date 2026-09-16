import itertools
from pathlib import Path
from typing import Literal

import pytest

from harbinger.cli.parser import TaskParser
from harbinger.model import Task, TaskFn, TaskSpec


class TaskParserTester:
    def __init__(self, func: TaskFn[..., object], /) -> None:
        self.task = Task.new(func, TaskSpec())
        self.parser = TaskParser(self.task)

    def parse(self, *argv: str) -> None:
        pos, kw = self.parser.parse(argv)
        self.task.call(*pos, **kw)


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
