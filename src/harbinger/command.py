from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from string.templatelib import Interpolation, Template, convert
from typing import Sequence, final, overload, override

type StrOrPath = str | os.PathLike[str]


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


def replace(cmd: Command, key: str, value: object) -> Command:
    copied = copy(cmd)
    object.__setattr__(copied, key, value)
    return copied


@dataclass(frozen=True, slots=True)
class Run:
    """The executable, arguments, and exit status of a completed command."""

    executable: Path
    args: tuple[StrOrPath, ...]
    returncode: int


@final
@dataclass(frozen=True, slots=True)
class Capture(Run):
    """A completed command with captured stdout and stderr."""

    stdout: str
    stderr: str


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class Command:
    _executable: Path
    _args: tuple[StrOrPath, ...]
    _cwd: Path | None
    _env: Mapping[str, str | None]
    _check: bool

    def __init__(self, executable: StrOrPath, /) -> None:
        object.__setattr__(self, "_executable", Path(executable))
        object.__setattr__(self, "_args", ())
        object.__setattr__(self, "_cwd", None)
        object.__setattr__(self, "_env", {})
        object.__setattr__(self, "_check", True)

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
        return replace(self, "_args", self._args + args2seq(args))

    def cwd(self, path: StrOrPath | None, /) -> Command:
        return replace(
            self,
            "_cwd",
            Path(path) if path is not None else None,
        )

    def env(self, overrides: Mapping[str, str | None], /) -> Command:
        return replace(self, "_env", {**self._env, **overrides})

    def check(self, enabled: bool, /) -> Command:
        return replace(self, "_check", enabled)

    def run(self) -> Run:
        args = (self._executable, *self._args)
        env = dict(os.environ)

        for key, value in self._env.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value

        completed = subprocess.run(
            args,
            cwd=self._cwd,
            env=env,
            check=self._check,
            shell=False,
        )

        return Run(self._executable, self._args, completed.returncode)

    def capture(self) -> Capture:
        args = (self._executable, *self._args)
        env = dict(os.environ)

        for key, value in self._env.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value

        completed = subprocess.run(
            args,
            cwd=self._cwd,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=self._check,
            shell=False,
        )

        return Capture(
            self._executable,
            self._args,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def stdout(self) -> str:
        return self.capture().stdout.strip()
