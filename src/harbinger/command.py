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
from typing import Sequence, final, overload, override

type StrOrPath = str | os.PathLike[str]


@final
@dataclass(frozen=True, slots=True)
class Executable(os.PathLike[str]):
    """The canonical absolute path to an existing executable file."""

    _: str

    @classmethod
    def new(cls, value: str | os.PathLike[str], /) -> Executable:
        match value:
            case str():
                if os.path.isabs(value):
                    program = value
                elif value not in ("", ".", "..") and os.path.basename(value) == value:
                    program = shutil.which(value)
                    if program is None:
                        raise FileNotFoundError(value)
                else:
                    raise ValueError

            case os.PathLike():
                program = os.fspath(value)

                if not os.path.isabs(program):
                    raise ValueError

            case _:
                raise TypeError

        if not os.path.isfile(program):
            raise FileNotFoundError(program)

        return cls(os.path.realpath(program))

    def __fspath__(self) -> str:
        return self._

    def __str__(self) -> str:
        return self._

    def __repr__(self) -> str:
        return f"Executable({self._!r})"


@final
@dataclass(frozen=True, slots=True)
class Environment:
    """Environment overrides, with None marking a variable for removal."""

    _: Mapping[str, str | None]

    @classmethod
    def new(cls, values: Mapping[str, str | None], /) -> Environment:
        return cls(
            {
                key.upper() if os.name == "nt" else key: value
                for key, value in values.items()
            }
        )

    def merge(self, values: Mapping[str, str | None], /) -> Environment:
        overrides = Environment.new(values)
        return Environment({**self._, **overrides._})

    def overlay(self, parent: Mapping[str, str], /) -> dict[str, str]:
        result = {
            key.upper() if os.name == "nt" else key: value
            for key, value in parent.items()
        }

        for key, value in self._.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value

        return result


def t2seq(template: Template) -> tuple[str, ...]:
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

    return tuple(shlex.split("".join(parts)))


def args2seq(args: Sequence[StrOrPath | Template]) -> tuple[StrOrPath, ...]:
    match args:
        case []:
            return ()
        case [Template() as template]:
            return t2seq(template)
        case _:
            seq: list[StrOrPath] = []
            for arg in args:
                if isinstance(arg, Template):
                    raise TypeError("a t-string cannot be mixed with other arguments")
                seq.append(arg)
            return tuple(seq)


@dataclass(frozen=True, slots=True)
class Run:
    """The executable, arguments, and exit status of a completed command."""

    executable: Executable
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

    _executable: Executable
    _args: tuple[StrOrPath, ...]
    _cwd: Path | None
    _env: Environment
    _check: bool

    def __init__(self, executable: str | os.PathLike[str], /) -> None:
        self._executable = Executable.new(executable)
        self._args = ()
        self._cwd = None
        self._env = Environment.new({})
        self._check = True

    @override
    def __repr__(self) -> str:
        return (
            f"<Command(executable={self._executable!r}, args={self._args!r}, "
            f"cwd={self._cwd!r}, env={self._env!r}, check={self._check!r})>"
        )

    @overload
    def args(self, args: Template, /) -> Command: ...

    @overload
    def args(self, *args: str | os.PathLike[str]) -> Command: ...

    def args(self, *args: str | os.PathLike[str] | Template) -> Command:
        command = copy(self)
        command._args = self._args + args2seq(args)
        return command

    def cwd(self, path: str | os.PathLike[str] | None, /) -> Command:
        command = copy(self)
        command._cwd = Path(path) if path is not None else None
        return command

    def env(self, overrides: Mapping[str, str | None], /) -> Command:
        command = copy(self)
        command._env = self._env.merge(overrides)
        return command

    def check(self, enabled: bool, /) -> Command:
        command = copy(self)
        command._check = enabled
        return command

    def run(self) -> Run:
        args = tuple(os.fspath(arg) for arg in self._args)
        env = self._env.overlay(os.environ)

        completed = subprocess.run(
            (self._executable, *args),
            cwd=self._cwd,
            env=env,
            check=self._check,
            shell=False,
        )

        return Run(self._executable, args, completed.returncode)

    def capture(self) -> Capture:
        args = tuple(os.fspath(arg) for arg in self._args)
        env = self._env.overlay(os.environ)

        completed = subprocess.run(
            (self._executable, *args),
            cwd=self._cwd,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=self._check,
            shell=False,
        )

        return Capture(
            self._executable,
            args,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def stdout(self) -> str:
        return self.capture().stdout.strip()
