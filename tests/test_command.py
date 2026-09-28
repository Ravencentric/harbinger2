from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from string.templatelib import Template

import pytest

from harbinger import Capture, Command, Run
from harbinger.cli import main


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        (t"one two", ("one", "two")),
        (t"'one two'", ("one two",)),
        (t"{'a b'}", ("a b",)),
        (t"--output={'a b'}", ("--output=a b",)),
        (t"{7:03d}", ("007",)),
        (t"{Path('some file')}", ("some file",)),
        (t"{Path('file'):>6}", ("  file",)),
    ],
)
def test_template_arguments(part: Template, expected: tuple[str, ...]) -> None:
    assert Command("tool").args(part)._args == expected


def test_pathlike_interpolation_uses_filesystem_path(tmp_path: Path) -> None:
    file = tmp_path / "source file.py"
    file.touch()
    with os.scandir(tmp_path) as entries:
        entry = next(entries)
        assert Command("tool").args(t"{entry}")._args == (os.fspath(entry),)


def test_dynamic_arguments_and_builder_copies() -> None:
    flags = ["-q", "-k", "slow tests"]
    base = Command("pytest").cwd("one").env({"CI": "1"}).check(False)
    variant = base.args(*flags).cwd("two").env({"CI": "2"}).check(True)
    flags.append("changed")

    assert base._args == ()
    assert base._cwd == Path("one")
    assert base._env == {"CI": "1"}
    assert base._check is False
    assert variant._args == ("-q", "-k", "slow tests")
    assert variant._cwd == Path("two")
    assert variant._env == {"CI": "2"}
    assert variant._check is True


def test_repeated_settings() -> None:
    command = (
        Command("tool")
        .args(t"first")
        .args("second")
        .cwd("one")
        .cwd("two")
        .env({"A": "1", "B": "2"})
        .env({"B": "3", "C": None})
        .check(False)
        .check(True)
    )
    assert command._args == ("first", "second")
    assert command._cwd == Path("two")
    assert command._env == {"A": "1", "B": "3", "C": None}
    assert command._check is True
    assert command.cwd(None)._cwd is None


def test_arguments_are_literal_and_templates_cannot_be_mixed() -> None:
    assert Command("tool").args("two args", Path("some file"))._args == (
        "two args",
        Path("some file"),
    )
    with pytest.raises(TypeError):
        Command("tool").args(t"one", "two")


def test_subprocess_rejects_invalid_literal_arguments() -> None:
    command = Command(Path(sys.executable)).args(3)
    assert command._args == (3,)
    with pytest.raises(TypeError):
        command.run()


def test_empty_argument_additions_are_noops() -> None:
    command = Command("tool").args(t"existing")
    flags: list[str] = []
    assert command.args(*flags)._args == command._args


def test_run_delivers_arguments_and_inherits_streams(
    capfd: pytest.CaptureFixture[str],
) -> None:
    script = "import json, sys; print(json.dumps(sys.argv[1:])); print('warning', file=sys.stderr)"
    values = ["", "two words", Path("some file"), "'quote", "&&", "$(echo nope)"]
    command = Command(Path(sys.executable)).args(t"-c {script}").args(*values)
    result = command.run()
    assert result == Run(Path(sys.executable), ("-c", script, *values), 0)
    captured = capfd.readouterr()
    assert json.loads(captured.out) == [os.fspath(value) for value in values]
    assert captured.err.splitlines() == ["warning"]


def test_cwd_and_environment_apply_at_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "child").mkdir()
    monkeypatch.setenv("HARBINGER_REVIEW_INHERITED", "before")
    monkeypatch.setenv("HARBINGER_REVIEW_REMOVED", "present")
    script = (
        "import json, os; print(json.dumps([os.getcwd(), "
        "os.environ.get('HARBINGER_REVIEW_INHERITED'), "
        "os.environ.get('HARBINGER_REVIEW_REMOVED')]))"
    )
    command = (
        Command(Path(sys.executable))
        .args(t"-c {script}")
        .cwd("child")
        .env({"HARBINGER_REVIEW_REMOVED": None})
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARBINGER_REVIEW_INHERITED", "after")
    command.run()
    assert json.loads(capfd.readouterr().out) == [
        str(tmp_path / "child"),
        "after",
        None,
    ]


def test_capture_preserves_text_and_stdout_strips_it() -> None:
    script = (
        "import sys; sys.stdout.write('  value \\n\\n'); "
        "sys.stderr.write('diagnostic\\n')"
    )
    command = Command(Path(sys.executable)).args(t"-c {script}")
    assert command.capture() == Capture(
        Path(sys.executable), ("-c", script), 0, "  value \n\n", "diagnostic\n"
    )
    assert command.stdout() == "value"


def test_capture_decodes_utf8() -> None:
    script = "import sys; sys.stdout.buffer.write('caf\\u00e9'.encode('utf-8'))"
    command = Command(Path(sys.executable)).args(t"-c {script}")
    assert command.capture().stdout == "caf\u00e9"
    assert command.stdout() == "caf\u00e9"


def test_checked_failure_and_unchecked_result() -> None:
    command = Command(Path(sys.executable)).args(t"-c {'raise SystemExit(7)'}")
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        command.run()
    assert excinfo.value.cmd == (command._executable, *command._args)
    assert excinfo.value.returncode == 7
    assert command.check(False).run() == Run(
        Path(sys.executable), ("-c", "raise SystemExit(7)"), 7
    )


def test_captured_failure_exposes_output() -> None:
    script = "import sys; print('partial'); print('diagnostic', file=sys.stderr); sys.exit(7)"
    command = Command(Path(sys.executable)).args(t"-c {script}")
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        command.capture()
    assert excinfo.value.cmd == (command._executable, *command._args)
    assert excinfo.value.returncode == 7
    assert excinfo.value.stdout == "partial\n"
    assert excinfo.value.stderr == "diagnostic\n"


def test_captured_failure_prints_stderr_in_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = (
        "import sys; print('[red]' + 'missing configuration' + '[/]', "
        "file=sys.stderr); sys.exit(7)"
    )
    (tmp_path / "tasks.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "from harbinger import Command, task\n"
        "@task\n"
        "def fail():\n"
        f"    Command(Path(sys.executable)).args(t'-c {{{script!r}}}').capture()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(("fail",)) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "CalledProcessError" in output.err
    assert "[red]missing configuration[/]" in output.err
