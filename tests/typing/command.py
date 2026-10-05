"""Positive public API checks: run with pyrefly check tests/typing/command.py."""

import os
import sys
from pathlib import Path
from typing import assert_type

from harbinger import Capture, Cmd, Run


def public_api(path: Path) -> None:
    values: list[str | os.PathLike[str]] = ["one arg", path]
    command = Cmd(path).args(t"--output={path}")
    assert_type(Cmd(sys.executable), Cmd)
    assert_type(Cmd(path), Cmd)
    assert_type(command.args(*values), Cmd)
    assert_type(command.cwd(path).cwd(None), Cmd)
    assert_type(command.env({"A": "1", "B": "2"}), Cmd)
    assert_type(command.check(False), Cmd)
    assert_type(command == Cmd(path), bool)
    assert_type(hash(command), int)
    assert_type(command.run(), Run)
    assert_type(command.run().executable, str)
    assert_type(command.run().args, tuple[str, ...])
    assert_type(command.capture(), Capture)
    assert_type(command.capture().executable, str)
    assert_type(command.capture().args, tuple[str, ...])
    assert_type(command.stdout(), str)
