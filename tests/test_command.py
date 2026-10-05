from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from string.templatelib import Template

import pytest

from harbinger import Capture, Cmd, Run
from harbinger.cli import main
from harbinger.command import Environment, Executable


@pytest.mark.parametrize("constructor", [Cmd, Executable.parse])
@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
@pytest.mark.parametrize("kind", ["missing", "directory", "file"])
def test_executable_requires_existing_file(
    constructor: Callable[[str | os.PathLike[str]], Cmd | Executable],
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
        executable = parsed.inner.executable if isinstance(parsed, Cmd) else parsed
        assert os.fspath(executable) == os.path.abspath(path)
    else:
        with pytest.raises(ValueError):
            constructor(value)


@pytest.mark.parametrize("constructor", [Cmd, Executable.parse])
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
        Path("bin/tool"),
        Path("../tool"),
    ],
)
def test_unsupported_executable_inputs_raise_value_error(
    executable: str | Path,
    constructor: Callable[[str | os.PathLike[str]], Cmd | Executable],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "harbinger.command.shutil.which", lambda program: sys.executable
    )
    with pytest.raises(ValueError):
        constructor(executable)


@pytest.mark.parametrize("constructor", [Cmd, Executable.parse])
@pytest.mark.parametrize("executable", ["tool", Path("tool"), Path("./tool")])
def test_missing_bare_executable_names_raise_file_not_found(
    executable: str | Path,
    constructor: Callable[[str | os.PathLike[str]], Cmd | Executable],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("harbinger.command.shutil.which", lambda program: None)
    with pytest.raises(FileNotFoundError):
        constructor(executable)


@pytest.mark.skipif(os.name != "nt", reason="Windows relative path syntax")
@pytest.mark.parametrize("constructor", [Cmd, Executable.parse])
@pytest.mark.parametrize(
    "executable", [r".\tool", r"..\tool", r"bin\tool", r"\tool", "C:tool"]
)
def test_windows_relative_executable_paths_raise_value_error(
    executable: str,
    constructor: Callable[[str | os.PathLike[str]], Cmd | Executable],
) -> None:
    with pytest.raises(ValueError):
        constructor(executable)


@pytest.mark.parametrize(
    "raw", ["tool", "git status", sys.executable, Path(sys.executable)]
)
def test_executable_parsing_returns_absolute_paths(
    raw: str | os.PathLike[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "harbinger.command.shutil.which", lambda program: sys.executable
    )
    executable = Executable.parse(raw)
    assert not isinstance(executable, str)
    assert isinstance(executable, os.PathLike)
    assert str(executable) == os.path.abspath(sys.executable)
    assert os.fspath(executable) == os.path.abspath(sys.executable)
    assert Executable.parse(executable) == executable
    assert Cmd(executable).inner.executable == executable


@pytest.mark.parametrize("constructor", [Cmd, Executable.parse])
@pytest.mark.parametrize("bare_name", [False, True], ids=["absolute", "bare-name"])
def test_executable_parsing_preserves_symlinks(
    constructor: Callable[[str | os.PathLike[str]], Cmd | Executable],
    bare_name: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    target.touch()
    link = tmp_path / "link"
    try:
        link.symlink_to(target)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Creating symlinks requires Windows symlink privileges")
        raise

    monkeypatch.setattr("harbinger.command.shutil.which", lambda program: str(link))
    parsed = constructor("tool" if bare_name else link)
    executable = parsed.inner.executable if isinstance(parsed, Cmd) else parsed
    assert str(executable) == str(link)
    assert os.fspath(executable) == str(link)


def test_executable_can_be_passed_directly_to_subprocess() -> None:
    executable = Executable.parse(sys.executable)
    result = subprocess.run(
        (executable, "-c", "print('executed')"),
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == "executed\n"


def test_executable_equality_and_hash_use_canonical_path() -> None:
    path = Path(sys.executable)
    spelling = str(path.parent) + os.sep + "." + os.sep + path.name
    first = Executable.parse(path)
    second = Executable.parse(spelling)

    assert first is not second
    assert first == second
    assert hash(first) == hash(second)
    assert {first: "resolved"}[second] == "resolved"


def test_command_constructor_accepts_only_positional_executable() -> None:
    with pytest.raises(TypeError):
        Cmd(executable=sys.executable)
    with pytest.raises(TypeError):
        Cmd(sys.executable, inner=Cmd(sys.executable).inner)


def test_equivalent_commands_have_equal_hashes(tmp_path: Path) -> None:
    first = (
        Cmd(sys.executable)
        .args(t"one {'two words'}")
        .cwd(str(tmp_path))
        .env({"B": "2", "A": "0"})
        .env({"A": "1"})
        .check(False)
    )
    second = (
        Cmd(Path(sys.executable))
        .args("one", "two words")
        .cwd(tmp_path)
        .env({"A": "1", "B": "2"})
        .check(False)
    )

    assert first is not second
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
    assert {first: "cached"}[second] == "cached"


def test_every_command_setting_participates_in_equality(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.touch()
    second.touch()
    base = Cmd(first)
    variants = (
        Cmd(second),
        base.args("argument"),
        base.cwd(tmp_path),
        base.env({"A": "1"}),
        base.check(False),
    )

    assert all(base != variant for variant in variants)
    assert len({base, *variants}) == 6


def test_command_hash_is_stable_after_derivation_and_input_changes() -> None:
    overrides = {"MODE": "base"}
    base = Cmd(sys.executable).args("initial").env(overrides)
    cached = {base: "cached"}
    before = hash(base)
    derived = base.args("extra").env({"MODE": "derived"}).check(False)
    overrides["MODE"] = "changed"

    equivalent = Cmd(sys.executable).args("initial").env({"MODE": "base"})
    assert hash(base) == before
    assert cached[equivalent] == "cached"
    assert derived not in cached


@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_builders_reuse_internal_executable_and_results_expose_string(
    capture: bool,
) -> None:
    base = Cmd(sys.executable)
    executable = base.inner.executable
    command = base.args("-c", "pass").cwd(None).env({}).check(False)
    result = command.capture() if capture else command.run()
    assert base.inner.executable is executable
    assert command.inner.executable is executable
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
    command = Cmd(executable).args("-c", "pass").cwd(tmp_path)
    result = command.capture() if capture else command.run()
    assert result.executable == os.path.abspath(executable)
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
    command = Cmd(executable.name).args("-c", "pass")
    result = command.capture() if capture else command.run()
    assert result.executable == os.path.abspath(executable)
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
    assert Cmd(sys.executable).args(part).inner.args.inner == expected


def test_pathlike_interpolation_uses_filesystem_path(tmp_path: Path) -> None:
    file = tmp_path / "source file.py"
    file.touch()
    with os.scandir(tmp_path) as entries:
        entry = next(entries)
        assert Cmd(sys.executable).args(t"{entry}").inner.args.inner == (
            os.fspath(entry),
        )


def test_dynamic_arguments_and_builder_variants() -> None:
    flags = ["-q", "-k", "slow tests"]
    base = Cmd(sys.executable).cwd("one").env({"CI": "1"}).check(False)
    variant = base.args(*flags).cwd("two").env({"CI": "2"}).check(True)
    flags.append("changed")

    assert base.inner.args.inner == ()
    assert base.inner.cwd == Path("one")
    assert dict(base.inner.env.inner) == {"CI": "1"}
    assert base.inner.check is False
    assert variant.inner.args.inner == ("-q", "-k", "slow tests")
    assert variant.inner.cwd == Path("two")
    assert dict(variant.inner.env.inner) == {"CI": "2"}
    assert variant.inner.check is True


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_environment_key_casing_and_command_equality(
    platform: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(os, "name", platform)
        environment = Environment.parse({"Mode": "first", "MODE": "Last Value"})
        first = Cmd(sys.executable).env({"Mode": "Last Value"})
        second = Cmd(sys.executable).env({"MODE": "Last Value"})

    if platform == "nt":
        assert dict(environment.inner) == {"MODE": "Last Value"}
        assert first == second
        assert hash(first) == hash(second)
        assert {first: "cached"}[second] == "cached"
    else:
        assert dict(environment.inner) == {"Mode": "first", "MODE": "Last Value"}
        assert first != second
        assert len({first, second}) == 2


@pytest.mark.parametrize("platform", ["nt", "posix"])
@pytest.mark.parametrize(
    "overrides",
    [{"Mode": "first", "MODE": "last"}, {"MODE": "first", "Mode": "last"}],
)
def test_environment_merge_normalizes_incoming_keys_before_merging(
    platform: str,
    overrides: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(os, "name", platform)
        base = Environment.parse({"MODE": "base", "OTHER": "unchanged"})
        merged = base.merge(overrides)

    assert dict(base.inner) == {"MODE": "base", "OTHER": "unchanged"}
    expected = (
        {"MODE": "last", "OTHER": "unchanged"}
        if platform == "nt"
        else {"MODE": "base", "OTHER": "unchanged", **overrides}
    )
    assert dict(merged.inner) == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows environment key casing")
@pytest.mark.parametrize("capture", [False, True], ids=["run", "capture"])
def test_windows_environment_overrides_ignore_key_casing(
    capture: bool,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    name = "HARBINGER_REVIEW_CASING"
    monkeypatch.setenv(name, "parent")
    command = (
        Cmd(sys.executable)
        .args("-c", f"import os; print(os.environ[{name!r}])")
        .env({name: "base"})
        .env({name.lower(): "first", name: "Last Value"})
    )
    result = command.capture() if capture else command.run()
    stdout = result.stdout if isinstance(result, Capture) else capfd.readouterr().out
    assert stdout.strip() == "Last Value"
    assert os.environ[name] == "parent"


def test_environment_inputs_are_snapshotted_for_reused_commands() -> None:
    overrides = {"HARBINGER_REVIEW_SNAPSHOT": "base"}
    script = (
        "import json, os, sys; "
        "print(json.dumps([os.environ['HARBINGER_REVIEW_SNAPSHOT'], sys.argv[1:]]))"
    )
    base = Cmd(sys.executable).args("-c", script).env(overrides)
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
    base = Cmd(sys.executable).args("-c", script).env(environment)
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
        Cmd(sys.executable)
        .args(t"first")
        .args("second")
        .cwd("one")
        .cwd("two")
        .env({"A": "1", "B": "2"})
        .env({"B": "3", "C": "4"})
        .check(False)
        .check(True)
    )
    assert command.inner.args.inner == ("first", "second")
    assert command.inner.cwd == Path("two")
    assert dict(command.inner.env.inner) == {"A": "1", "B": "3", "C": "4"}
    assert command.inner.check is True
    assert command.cwd(None).inner.cwd is None


def test_arguments_are_literal_and_templates_cannot_be_mixed() -> None:
    assert Cmd(sys.executable).args("two args", Path("some file")).inner.args.inner == (
        "two args",
        "some file",
    )
    with pytest.raises(TypeError):
        Cmd(sys.executable).args(t"one", "two")


def test_invalid_literal_arguments_are_rejected_when_added() -> None:
    with pytest.raises(TypeError):
        Cmd(Path(sys.executable)).args(3)


def test_empty_argument_additions_are_noops() -> None:
    command = Cmd(sys.executable).args(t"existing")
    flags: list[str] = []
    assert command.args(*flags).inner.args == command.inner.args


def test_run_delivers_arguments_and_inherits_streams(
    capfd: pytest.CaptureFixture[str],
) -> None:
    script = "import json, sys; print(json.dumps(sys.argv[1:])); print('warning', file=sys.stderr)"
    values = ["", "two words", Path("some file"), "'quote", "&&", "$(echo nope)"]
    command = Cmd(Path(sys.executable)).args(t"-c {script}").args(*values)
    result = command.run()
    assert result == Run(
        os.path.abspath(sys.executable),
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
    command = Cmd(sys.executable).args("-c", script, path, Path("some file"))
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
    command = Cmd(Path(sys.executable)).args(t"-c {script}").cwd("child")
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
    command = Cmd(Path(sys.executable)).args(t"-c {script}")
    assert command.capture() == Capture(
        os.path.abspath(sys.executable),
        ("-c", script),
        0,
        "  value \n\n",
        "diagnostic\n",
    )
    assert command.stdout() == "value"


def test_capture_decodes_utf8() -> None:
    script = "import sys; sys.stdout.buffer.write('caf\\u00e9'.encode('utf-8'))"
    command = Cmd(Path(sys.executable)).args(t"-c {script}")
    assert command.capture().stdout == "caf\u00e9"
    assert command.stdout() == "caf\u00e9"


def test_checked_failure_and_unchecked_result() -> None:
    command = Cmd(Path(sys.executable)).args(t"-c {'raise SystemExit(7)'}")
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        command.run()
    assert excinfo.value.cmd == (command.inner.executable, *command.inner.args.inner)
    assert excinfo.value.returncode == 7
    assert command.check(False).run() == Run(
        os.path.abspath(sys.executable), ("-c", "raise SystemExit(7)"), 7
    )


def test_captured_failure_exposes_output() -> None:
    script = "import sys; print('partial'); print('diagnostic', file=sys.stderr); sys.exit(7)"
    command = Cmd(Path(sys.executable)).args(t"-c {script}")
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        command.capture()
    assert excinfo.value.cmd == (command.inner.executable, *command.inner.args.inner)
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
        "from harbinger import Cmd, task\n"
        "@task\n"
        "def fail():\n"
        f"    Cmd(Path(sys.executable)).args(t'-c {{{script!r}}}').capture()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(("fail",)) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "CalledProcessError" in output.err
    assert "[red]missing configuration[/]" in output.err
