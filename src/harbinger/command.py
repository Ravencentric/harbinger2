from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from string.templatelib import Interpolation, Template, convert
from typing import NewType, Sequence, final, overload, override

type StrOrPath = str | os.PathLike[str]
Args = NewType("Args", tuple[str, ...])


@final
@dataclass(frozen=True, slots=True)
class Executable(os.PathLike[str]):
    """The canonical absolute path to an existing executable file."""

    _: str

    @classmethod
    def new(cls, value: StrOrPath, /) -> Executable:
        program = os.fspath(value)

        if os.path.isabs(program):
            if os.path.isfile(program):
                return cls(os.path.realpath(program))

        if program not in ("", ".", "..") and os.path.basename(program) == program:
            if found := shutil.which(program):
                return cls(os.path.realpath(found))

        raise FileNotFoundError(program)

    def __fspath__(self) -> str:
        return self._

    def __str__(self) -> str:
        return self._

    def __repr__(self) -> str:
        return f"Executable({self._!r})"


def template2args(template: Template) -> Args:
    parts: list[str] = []

    for item in template:
        match item:
            case str():
                parts.append(item)

            case Interpolation(value, _, conversion, format_spec):
                if isinstance(value, os.PathLike):
                    value = os.fspath(value)
                value = convert(value, conversion)
                value = format(value, format_spec)
                parts.append(shlex.quote(value))

    return Args(shlex.split("".join(parts)))


def sequence2args(args: Sequence[StrOrPath | Template]) -> Args:
    match args:
        case []:
            return Args()
        case [Template() as template]:
            return template2args(template)
        case _:
            seq: list[StrOrPath] = []
            for arg in args:
                if isinstance(arg, Template):
                    raise TypeError("a t-string cannot be mixed with other arguments")
                seq.append(os.fspath(arg))
            return Args(seq)


@dataclass(frozen=True, slots=True)
class Run:
    """The executable, arguments, and exit status of a completed command."""

    executable: str
    args: tuple[str, ...]
    returncode: int


@final
@dataclass(frozen=True, slots=True)
class Capture(Run):
    """A completed command with captured stdout and stderr."""

    stdout: str
    stderr: str


@final
class Command:
    __slots__ = ("_executable", "_args", "_cwd", "_env", "_check")

    def __init__(self, executable: StrOrPath, /) -> None:
        self._executable: Executable = Executable.new(executable)
        self._args: Args = Args()
        self._cwd: Path | None = None
        self._env: Mapping[str, str] = {}
        self._check: bool = True

    @override
    def __repr__(self) -> str:
        return (
            f"<Command(executable={self._executable!r}, args={self._args!r}, "
            f"cwd={self._cwd!r}, env={self._env!r}, check={self._check!r})>"
        )

    @overload
    def args(self, args: Template, /) -> Command: ...

    @overload
    def args(self, *args: StrOrPath) -> Command: ...

    def args(self, *args: StrOrPath | Template) -> Command:
        command = copy(self)
        command._args = self._args + sequence2args(args)
        return command

    def cwd(self, path: StrOrPath | None, /) -> Command:
        command = copy(self)
        command._cwd = Path(path) if path is not None else None
        return command

    def env(self, overrides: Mapping[str, str], /) -> Command:
        command = copy(self)
        command._env = {**self._env, **overrides}
        return command

    def check(self, enabled: bool, /) -> Command:
        command = copy(self)
        command._check = enabled
        return command

    def run(self) -> Run:

        completed = subprocess.run(
            (self._executable, *self._args),
            cwd=self._cwd,
            env={**os.environ, **self._env},
            check=self._check,
            shell=False,
        )

        return Run(self._executable, self._args, completed.returncode)

    def capture(self) -> Capture:

        completed = subprocess.run(
            (self._executable, *self._args),
            cwd=self._cwd,
            env={**os.environ, **self._env},
            capture_output=True,
            encoding="utf-8",
            check=self._check,
            shell=False,
        )

        return Capture(
            f"{self._executable}",
            self._args,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def stdout(self) -> str:
        return self.capture().stdout.strip()
