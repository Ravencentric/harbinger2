from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from string.templatelib import Template

import pytest

from harbinger import Capture, Command, Run
from harbinger.cli import main
from harbinger.command import Executable


@pytest.mark.parametrize("constructor", [Command, Executable.new])
@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
@pytest.mark.parametrize("kind", ["missing", "directory", "file"])
def test_executable_requires_existing_file(
    constructor: Callable[[str | os.PathLike[str]], Command | Executable],
    as_string: bool,
    kind: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / "program"
    if kind == "directory":
        path.mkdir()
    elif kind == "file":
        path.touch()
    value = str(path) if as_string else path

    if kind == "file":
        parsed = constructor(value)
        executable = parsed._executable if isinstance(parsed, Command) else parsed
        assert os.fspath(executable) == os.path.realpath(path)
    else:
        with pytest.raises(FileNotFoundError):
            constructor(value)


@pytest.mark.parametrize("constructor", [Command, Executable.new])
@pytest.mark.parametrize(
    "executable",
    [
        "./tool",
        "../tool",
        "bin/tool",
        "tool/",
        "",
        ".",
        "..",
        Path("tool"),
        Path("./tool"),
        Path("bin/tool"),
        Path("../tool"),
    ],
)
def test_unresolved_relative_executable_inputs_raise_file_not_found(
    executable: str | Path,
    constructor: Callable[[str | os.PathLike[str]], Command | Executable],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("harbinger.command.shutil.which", lambda program: None)
    with pytest.raises(FileNotFoundError):
        constructor(executable)


@pytest.mark.skipif(os.name != "nt", reason="Windows relative path syntax")
@pytest.mark.parametrize("constructor", [Command, Executable.new])
@pytest.mark.parametrize(
    "executable", [r".\tool", r"..\tool", r"bin\tool", r"\tool", "C:tool"]
)
def test_windows_relative_executable_paths_raise_file_not_found(
    executable: str,
    constructor: Callable[[str | os.PathLike[str]], Command | Executable],
) -> None:
    with pytest.raises(FileNotFoundError):
        constructor(executable)


@pytest.mark.parametrize("constructor", [Command, Executable.new])
@pytest.mark.parametrize(
    "executable", ["bad\0name", sys.executable + "\0", Path(sys.executable + "\0")]
)
def test_executable_null_bytes_are_rejected(
    executable: str | Path,
    constructor: Callable[[str | os.PathLike[str]], Command | Executable],
) -> None:
    with pytest.raises(ValueError, match="null bytes"):
        constructor(executable)


@pytest.mark.parametrize(
    "raw", ["tool", "git status", sys.executable, Path(sys.executable)]
)
def test_executable_parsing_returns_canonical_paths(
    raw: str | os.PathLike[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "harbinger.command.shutil.which", lambda program: sys.executable
    )
    executable = Executable.new(raw)
    assert not isinstance(executable, str)
    assert isinstance(executable, os.PathLike)
    assert str(executable) == os.path.realpath(sys.executable)
    assert os.fspath(executable) == os.path.realpath(sys.executable)
    assert Executable.new(executable) == executable
    assert Command(executable)._executable == executable


def test_executable_can_be_passed_directly_to_subprocess() -> None:
    executable = Executable.new(sys.executable)
    result = subprocess.run(
        (executable, "-c", "print('executed')"),
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "executed\n"


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_builders_reuse_internal_executable_and_results_expose_string(
    capture: bool,
) -> None:
    base = Command(sys.executable)
    executable = base._executable
    command = base.args("-c", "pass").cwd(None).env({}).check(False)
    result = command.capture() if capture else command.run()
    assert base._executable is executable
    assert command._executable is executable
    assert isinstance(result.executable, str)
    assert result.executable == str(executable)
    assert result.returncode == 0


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_absolute_executable_is_canonical_and_independent_of_cwd(
    capture: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path(sys.executable)
    executable = str(path.parent) + os.sep + "." + os.sep + path.name
    command = Command(executable).args("-c", "pass").cwd(tmp_path)
    result = command.capture() if capture else command.run()
    assert result.executable == os.path.realpath(executable)
    assert result.returncode == 0


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_bare_executable_name_is_supported(
    capture: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    executable = Path(sys.executable)
    monkeypatch.setenv("PATH", str(executable.parent))
    command = Command(executable.name).args("-c", "pass")
    result = command.capture() if capture else command.run()
    assert result.executable == os.path.realpath(executable)
    assert result.returncode == 0


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
    assert Command(sys.executable).args(part)._args == expected


def test_pathlike_interpolation_uses_filesystem_path(tmp_path: Path) -> None:
    file = tmp_path / "source file.py"
    file.touch()
    with os.scandir(tmp_path) as entries:
        entry = next(entries)
        assert Command(sys.executable).args(t"{entry}")._args == (os.fspath(entry),)


def test_dynamic_arguments_and_builder_copies() -> None:
    flags = ["-q", "-k", "slow tests"]
    base = Command(sys.executable).cwd("one").env({"CI": "1"}).check(False)
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


def test_environment_inputs_are_snapshotted_for_reused_commands() -> None:
    overrides = {"HARBINGER_REVIEW_SNAPSHOT": "base"}
    script = (
        "import json, os, sys; "
        "print(json.dumps([os.environ['HARBINGER_REVIEW_SNAPSHOT'], sys.argv[1:]]))"
    )
    base = Command(sys.executable).args("-c", script).env(overrides)
    variant = base.args("derived").env({"HARBINGER_REVIEW_SNAPSHOT": "variant"})
    overrides["HARBINGER_REVIEW_SNAPSHOT"] = "changed"

    assert json.loads(base.stdout()) == ["base", []]
    assert json.loads(variant.stdout()) == ["variant", ["derived"]]
    assert json.loads(base.stdout()) == ["base", []]


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_environment_overrides_are_reusable_across_commands(
    capture: bool,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HARBINGER_REVIEW_OVERRIDDEN", "parent")
    environment = {
        "HARBINGER_REVIEW_SHARED": "base",
        "HARBINGER_REVIEW_OVERRIDDEN": "override",
    }
    script = (
        "import json, os; "
        "print(json.dumps([os.environ['HARBINGER_REVIEW_SHARED'], "
        "os.environ['HARBINGER_REVIEW_OVERRIDDEN']]))"
    )
    base = Command(sys.executable).args("-c", script).env(environment)
    derived = base.env({"HARBINGER_REVIEW_SHARED": "derived"})

    for command, expected in [(base, "base"), (derived, "derived"), (base, "base")]:
        result = command.capture() if capture else command.run()
        stdout = (
            result.stdout if isinstance(result, Capture) else capfd.readouterr().out
        )
        assert json.loads(stdout) == [expected, "override"]

    assert os.environ["HARBINGER_REVIEW_OVERRIDDEN"] == "parent"


def test_repeated_settings() -> None:
    command = (
        Command(sys.executable)
        .args(t"first")
        .args("second")
        .cwd("one")
        .cwd("two")
        .env({"A": "1", "B": "2"})
        .env({"B": "3", "C": "4"})
        .check(False)
        .check(True)
    )
    assert command._args == ("first", "second")
    assert command._cwd == Path("two")
    assert command._env == {"A": "1", "B": "3", "C": "4"}
    assert command._check is True
    assert command.cwd(None)._cwd is None


def test_arguments_are_literal_and_templates_cannot_be_mixed() -> None:
    assert Command(sys.executable).args("two args", Path("some file"))._args == (
        "two args",
        "some file",
    )
    with pytest.raises(TypeError):
        Command(sys.executable).args(t"one", "two")


def test_invalid_literal_arguments_are_rejected_when_added() -> None:
    with pytest.raises(TypeError):
        Command(Path(sys.executable)).args(3)


def test_empty_argument_additions_are_noops() -> None:
    command = Command(sys.executable).args(t"existing")
    flags: list[str] = []
    assert command.args(*flags)._args == command._args


def test_run_delivers_arguments_and_inherits_streams(
    capfd: pytest.CaptureFixture[str],
) -> None:
    script = "import json, sys; print(json.dumps(sys.argv[1:])); print('warning', file=sys.stderr)"
    values = ["", "two words", Path("some file"), "'quote", "&&", "$(echo nope)"]
    command = Command(Path(sys.executable)).args(t"-c {script}").args(*values)
    result = command.run()
    assert result == Run(
        os.path.realpath(sys.executable),
        ("-c", script, *(os.fspath(value) for value in values)),
        0,
    )
    captured = capfd.readouterr()
    assert json.loads(captured.out) == [os.fspath(value) for value in values]
    assert captured.err.splitlines() == ["warning"]


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_pathlike_arguments_are_frozen_when_added_and_match_child(
    capture: bool,
    capfd: pytest.CaptureFixture[str],
) -> None:
    class ChangingPath(os.PathLike[str]):
        calls = 0
        value = "original argument"

        def __fspath__(self) -> str:
            self.calls += 1
            return self.value

    path = ChangingPath()
    script = "import json, sys; print(json.dumps(sys.argv[1:]))"
    command = Command(sys.executable).args("-c", script, path, Path("some file"))
    assert path.calls == 1
    path.value = "changed after construction"

    for _ in range(2):
        result = command.capture() if capture else command.run()
        stdout = (
            result.stdout if isinstance(result, Capture) else capfd.readouterr().out
        )
        assert path.calls == 1
        assert result.args == ("-c", script, "original argument", "some file")
        assert json.loads(stdout) == list(result.args[2:])


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_cwd_and_inherited_environment_apply_at_execution(
    capture: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "child").mkdir()
    monkeypatch.setenv("HARBINGER_REVIEW_INHERITED", "before")
    script = (
        "import json, os; print(json.dumps([os.getcwd(), "
        "os.environ.get('HARBINGER_REVIEW_INHERITED')]))"
    )
    command = Command(Path(sys.executable)).args(t"-c {script}").cwd("child")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARBINGER_REVIEW_INHERITED", "after")
    result = command.capture() if capture else command.run()
    stdout = result.stdout if isinstance(result, Capture) else capfd.readouterr().out
    assert json.loads(stdout) == [
        str(tmp_path / "child"),
        "after",
    ]


def test_capture_preserves_text_and_stdout_strips_it() -> None:
    script = (
        "import sys; sys.stdout.write('  value \\n\\n'); "
        "sys.stderr.write('diagnostic\\n')"
    )
    command = Command(Path(sys.executable)).args(t"-c {script}")
    assert command.capture() == Capture(
        os.path.realpath(sys.executable),
        ("-c", script),
        0,
        "  value \n\n",
        "diagnostic\n",
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
        os.path.realpath(sys.executable), ("-c", "raise SystemExit(7)"), 7
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
