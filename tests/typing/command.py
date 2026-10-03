"""Positive public API checks: run with pyrefly check tests/typing/command.py."""

import os
import sys
from pathlib import Path
from typing import assert_type

from harbinger import Capture, Command, Run


def public_api(path: Path) -> None:
    values: list[str | os.PathLike[str]] = ["one arg", path]
    command = Command(path).args(t"--output={path}")
    assert_type(Command(sys.executable), Command)
    assert_type(Command(path), Command)
    assert_type(command.args(*values), Command)
    assert_type(command.cwd(path).cwd(None), Command)
    assert_type(command.env({"A": "1", "B": "2"}), Command)
    assert_type(command.check(False), Command)
    assert_type(command.run(), Run)
    assert_type(command.run().executable, str)
    assert_type(command.run().args, tuple[str, ...])
    assert_type(command.capture(), Capture)
    assert_type(command.capture().executable, str)
    assert_type(command.capture().args, tuple[str, ...])
    assert_type(command.stdout(), str)
