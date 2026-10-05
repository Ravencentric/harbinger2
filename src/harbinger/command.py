from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from string.templatelib import Interpolation, Template, convert
from typing import Any, Sequence, final, overload, override

type StrOrPath = str | os.PathLike[str]


@final
@dataclass(frozen=True, slots=True)
class Executable(os.PathLike[str]):
    """The canonical absolute path to an existing executable file."""

    inner: str

    @classmethod
    def parse(cls, value: StrOrPath, /) -> Executable:
        program = os.fspath(value)

        if not program:
            raise ValueError("executable cannot be empty")

        if os.path.isabs(program):
            if not os.path.isfile(program):
                raise ValueError(f"executable must be an existing file: {program!r}")
            return cls(os.path.realpath(program))

        if program in (".", "..") or os.path.basename(program) != program:
            raise ValueError(
                f"executable must be an absolute path or bare name: {program!r}"
            )

        if found := shutil.which(program):
            return cls(os.path.realpath(found))

        raise FileNotFoundError(program)

    @override
    def __fspath__(self) -> str:
        return self.inner

    @override
    def __str__(self) -> str:
        return self.inner


@final
@dataclass(frozen=True, slots=True)
class Arguments:
    inner: tuple[str, ...] = ()

    @classmethod
    def parse(cls, args: Sequence[StrOrPath | Template] = (), /) -> Arguments:
        match args:
            case []:
                return cls()
            case [Template() as template]:
                return cls.from_template(template)
            case _:
                seq: list[str] = []

                for arg in args:
                    if isinstance(arg, Template):
                        raise TypeError(
                            "a t-string cannot be mixed with other arguments"
                        )

                    seq.append(os.fspath(arg))

                return cls(tuple(seq))

    def concat(self, args: Sequence[StrOrPath | Template], /) -> Arguments:
        other = Arguments.parse(args)
        return Arguments(self.inner + other.inner)

    @classmethod
    def from_template(cls, template: Template) -> Arguments:
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

        return cls(tuple(shlex.split("".join(parts))))


@final
@dataclass(frozen=True, slots=True)
class Environment:
    inner: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def parse(cls, overrides: Mapping[str, str], /) -> Environment:
        if os.name == "nt":
            # Environment keys on Windows are case-insensitive
            # but conventionally upper case
            overrides = {name.upper(): value for name, value in overrides.items()}
        return cls(frozenset(overrides.items()))

    def merge(self, overrides: Mapping[str, str], /) -> Environment:
        incoming = Environment.parse(overrides)
        environment = {**dict(self.inner), **dict(incoming.inner)}
        return Environment(frozenset(environment.items()))

    def inherit(self) -> Mapping[str, str]:
        return {**os.environ, **dict(self.inner)}


@final
@dataclass(frozen=True, slots=True)
class Run:
    """The executable, arguments, and exit status of a completed command."""

    executable: str
    args: tuple[str, ...]
    returncode: int


@final
@dataclass(frozen=True, slots=True)
class Capture:
    """A completed command with captured stdout and stderr."""

    executable: str
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@final
@dataclass(frozen=True, slots=True)
class State:
    """The parsed configuration of a command."""

    executable: Executable
    args: Arguments = Arguments()
    cwd: Path | None = None
    env: Environment = Environment()
    check: bool = True


@final
@dataclass(frozen=True, slots=True, init=False)
class Cmd:
    inner: State

    def __init__(self, executable: StrOrPath, /) -> None:
        object.__setattr__(self, "inner", State(Executable.parse(executable)))

    @override
    def __repr__(self) -> str:
        state = self.inner
        return (
            f"<Cmd(executable={state.executable!r}, args={state.args.inner!r}, "
            f"cwd={state.cwd!r}, env={dict(sorted(state.env.inner))!r}, check={state.check!r})>"
        )

    @overload
    def args(self, args: Template, /) -> Cmd: ...

    @overload
    def args(self, *args: StrOrPath) -> Cmd: ...

    def args(self, *args: StrOrPath | Template) -> Cmd:
        return command(self, args=self.inner.args.concat(args))

    def cwd(self, path: StrOrPath | None, /) -> Cmd:
        return command(self, cwd=Path(path) if path is not None else None)

    def env(self, overrides: Mapping[str, str], /) -> Cmd:
        return command(self, env=self.inner.env.merge(overrides))

    def check(self, enabled: bool, /) -> Cmd:
        return command(self, check=enabled)

    def run(self) -> Run:
        state = self.inner
        completed = subprocess.run(
            (state.executable, *state.args.inner),
            cwd=state.cwd,
            env=state.env.inherit(),
            check=state.check,
            shell=False,
        )

        return Run(state.executable.inner, state.args.inner, completed.returncode)

    def capture(self) -> Capture:
        state = self.inner
        completed = subprocess.run(
            (state.executable, *state.args.inner),
            cwd=state.cwd,
            env=state.env.inherit(),
            capture_output=True,
            encoding="utf-8",
            check=state.check,
            shell=False,
        )

        return Capture(
            state.executable.inner,
            state.args.inner,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def stdout(self) -> str:
        return self.capture().stdout.strip()


def command(source: Cmd, /, **changes: Any) -> Cmd:
    result = object.__new__(Cmd)
    object.__setattr__(result, "inner", replace(source.inner, **changes))
    return result
