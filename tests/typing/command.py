"""Positive public API checks: run with pyrefly check tests/typing/command.py."""

from pathlib import Path
from typing import assert_type

from harbinger import Capture, Command, Run, StrOrPath


def public_api(path: Path) -> None:
    values: list[StrOrPath] = ["one arg", path]
    command = Command(path).args(t"--output={path}")
    assert_type(Command("tool"), Command)
    assert_type(Command(path), Command)
    assert_type(command.args(*values), Command)
    assert_type(command.cwd(path).cwd(None), Command)
    assert_type(command.env({"A": "1", "B": None}), Command)
    assert_type(command.check(False), Command)
    assert_type(command.run(), Run)
    assert_type(command.run().args, tuple[StrOrPath, ...])
    assert_type(command.capture(), Capture)
    assert_type(command.stdout(), str)
