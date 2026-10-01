"""Positive public API checks: run with pyrefly check tests/typing/command.py."""

import os
from pathlib import Path
from typing import assert_type

from harbinger import Capture, Command, Executable, Run


def public_api(path: Path) -> None:
    values: list[str | os.PathLike[str]] = ["one arg", path]
    command = Command(path).args(t"--output={path}")
    assert_type(Command("tool"), Command)
    assert_type(Command(path), Command)
    assert_type(Executable.new("tool"), Executable)
    assert_type(Executable.new(path), Executable)
    assert_type(os.fspath(Executable.new("tool")), str)
    assert_type(str(Executable.new("tool")), str)
    assert_type(Command(Executable.new("tool")), Command)
    assert_type(command.args(*values), Command)
    assert_type(command.cwd(path).cwd(None), Command)
    assert_type(command.env({"A": "1", "B": None}), Command)
    assert_type(command.check(False), Command)
    assert_type(command.run(), Run)
    assert_type(command.run().executable, Executable)
    assert_type(command.run().args, tuple[str, ...])
    assert_type(command.capture(), Capture)
    assert_type(command.capture().executable, Executable)
    assert_type(command.capture().args, tuple[str, ...])
    assert_type(command.stdout(), str)
