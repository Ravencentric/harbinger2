# harbinger

Harbinger runs Python functions from a `tasks.py` file as command-line tasks.

## Install

Harbinger requires Python 3.14 or newer. Add it to the project whose tasks you
want to run:

```console
uv add --dev harbinger
```

Run it with `uv run harbinger`. The examples below use `harbinger` for brevity.
`uv run python -m harbinger` also works.

## Define tasks

Create `tasks.py` in your project root and decorate functions with `@task`:

```python
from harbinger import task


@task
def hello() -> None:
    """Print a greeting."""
    print("Hello")


@task
def greet(name: str = "World", *, count: int = 1, loud: bool = False) -> None:
    """Greet someone N times."""
    message = f"Hello, {name}!"
    if loud:
        message = message.upper()
    for _ in range(count):
        print(message)
```

Harbinger uses the function name as the task name and the docstring as its
description. Underscores in task names become hyphens on the command line:
`my_task` becomes `my-task`. Use `@task(name="...", description="...")` to
override either value. The task list shows the first line of each description;
task help shows the full description.

## Run tasks

```console
harbinger                 # list available tasks
harbinger --list          # list available tasks explicitly
harbinger hello           # run one task
harbinger hello greet     # run both tasks in order
harbinger --default       # run tasks marked default=True
harbinger --version       # print the version
```

Use either `--list`, `--default`, or task names; they cannot be combined.
Harbinger checks every named task before running any of them, then stops at
the first failure. Repeating a name runs that task again.

Tasks are excluded from `--default` unless you opt them in:

```python
from harbinger import Cmd, task


@task(default=True)
def test() -> None:
    """Run the test suite."""
    Cmd("pytest").run()
```

`--default` runs the marked tasks in listing order, using their parameter
defaults. The task list marks them with `*`. If none are marked, `--default`
exits with a usage error. Running `harbinger` without arguments lists tasks;
it never runs them.

### Task arguments

Put `--` between a task name and its arguments:

```console
harbinger greet -- Alice
harbinger greet -- Bob --count 3
harbinger greet -- Charlie --count 2 --loud
harbinger greet -- Dana --no-loud
harbinger greet -- --help
```

Arguments can be passed to one task at a time. Without the separator, words
after the first task name are treated as more task names. In task options,
underscores become hyphens: `output_dir` becomes `--output-dir`.

## Task parameters

Every parameter except `*args` needs a default value. Parameters without an
annotation are treated as strings. Supported annotations are:

| Annotation | Command-line behavior |
| --- | --- |
| `str`, `int`, `float`, `Path` | Parsed as the annotated type. |
| `bool` | Keyword-only; accepts `--flag` and `--no-flag`. |
| `Literal["dev", "prod"]` | Accepts one of the listed strings. |
| `Literal[1, 2]` | Accepts one of the listed integers. |

Import `Path` from `pathlib` and `Literal` from `typing`.

Positional parameters use their names as placeholders. Keyword-only parameters
become options. The `greet` task above accepts an optional `name` and the
`--count` and `--loud` options after the separator. `Literal` choices must all
be strings or all be integers.

A task can accept any number of positional values with `*args`. It can also
have keyword-only parameters after `*args`:

```python
from pathlib import Path
from harbinger import task


@task
def cp(*paths: Path, recursive: bool = False) -> None:
    for path in paths:
        print(path, recursive)
```

```console
harbinger cp -- --recursive src dst
```

Options may appear before or after the positional values. `*args` cannot be
combined with other positional parameters, and `**kwargs` is not supported.

## External commands

`Cmd` builds a reusable invocation. `.run()` executes it synchronously with
inherited stdin, stdout, and stderr. Nonzero exit statuses raise by default.
There is no shell option or automatic command echo.

```python
from pathlib import Path
from harbinger import Cmd

project = Path("my project")
uv = Cmd("uv").args(t"run").cwd(project)

uv.args(t"pytest").run()
uv.args(t"ruff check").args("--fix").run()

paths = [Path("first file.py"), Path("second file.py")]
Cmd("git").args("add", *paths).run()
```

Pass the executable as a string or path. It is a single path, so
`Cmd("git status")` looks for a program named `git status`. Path-like inputs
are converted with `os.fspath()` and follow the same rules as strings. Bare names,
including `Path("git")`, are resolved through the current `PATH` during
construction. Absolute paths that do not point to an existing file, empty names,
and relative executable paths such as
`./tool`, `../tool`, and `bin/tool` raise `ValueError`.
Resolve local paths explicitly, for example
`Cmd(Path("bin/tool").resolve())`. Bare names absent from `PATH` raise
`FileNotFoundError`.
The stored path is absolute and preserves symlinks.

Pass arguments with `.args()`: one t-string per call, or any number of literal
strings and paths.
Unpack a sequence of arguments with `*`. Literal strings are stored unchanged;
path-like arguments are converted with `os.fspath()` when `.args()` is called.
The resulting strings are fixed for every execution. Empty additions do nothing.

Templates use `shlex` POSIX quoting rules on every platform. Interpolated values
are quoted automatically before splitting, so write `{path}` without surrounding
shell quotes. Path-like interpolations use `os.fspath()`. Prefer interpolated
paths, especially for Windows backslashes. There is no shell expansion or
execution; operators are ordinary arguments.

```python
Cmd("git").args(t'commit -m "release build"').run()
Cmd("tool").args(t"--output={project / 'build files'}").run()

count = 7
Cmd("tool").args(t"--count={count:03d}").run()
```

Python conversions (`!s`, `!r`, `!a`) and format specifications work on
interpolated values. Unpack a sequence when a collection should become multiple
command arguments:

```python
flags = ["-q", "-k", "slow tests"]
Cmd("pytest").args(*flags).run()
```

### Configuration and reuse

Optional settings are configured through builder methods. Every method returns a
new command; retain the return value when building conditionally.

| Method | Behavior when repeated |
| --- | --- |
| `.args(*values)` | Append literal arguments, or parse one t-string. |
| `.cwd(path)` | Replace the directory; the last call wins. |
| `.env(mapping)` | Merge string overrides; later values replace identical keys. |
| `.check(enabled)` | Replace exit checking; the default is `True`. |

```python
base = Cmd("pytest").env({"CI": "1", "DEBUG": "0"})
debug = base.env({"DEBUG": "1"})
debug.run()  # base still has DEBUG=0

probe = Cmd("git").args(t"diff --quiet").check(False)
result = probe.run()
print(result.returncode)
```

Builder methods return new command variants: deriving `debug` above does not
change `base`. Arguments are stored in tuples and environment overrides are
copied from the supplied mappings. Repeated `.args()` calls append arguments;
repeated `.cwd()` and `.check()` calls replace their settings. Repeated `.env()`
calls merge dictionaries by key.

Commands compare by their configured executable, arguments, working directory,
environment overrides, and exit checking. Equivalent commands have equal hashes
and can be used as dictionary keys or set members. The insertion order of
environment overrides does not affect equality. On Windows, override names are
normalized to uppercase, so casing does not affect merging or equality. On other
platforms, names remain case sensitive.

Commands inherit the parent environment at execution time, with `.env()` string
overrides applied on top. Overrides never modify the parent environment, and an
empty mapping changes nothing. By default, commands also inherit the working
directory. Relative working directories resolve at execution time, and
`.cwd(None)` restores directory inheritance.

`.run()` returns an immutable `Run` with `.executable`, `.args`, and
`.returncode`. `.executable` is the absolute executable path as a string, preserving symlinks.
`.args` is a tuple of strings containing the arguments passed to the child,
excluding the executable. Path-like arguments were converted when added to the
command.
`.capture()` captures both output streams as UTF-8 text and returns `Capture`,
adding `.stdout` and `.stderr`. `.stdout()` executes and returns stripped stdout;
use `.capture().stdout` to preserve whitespace.
Checked failures raise `subprocess.CalledProcessError`. Failures from
`.capture()` retain captured output on the exception, and Harbinger prints
captured stderr in its task-failure diagnostic. Launch errors such as
`FileNotFoundError` and interruptions propagate normally.

## Errors and execution

Harbinger reads `tasks.py` from the current directory. It imports the file as
Python code and runs tasks in the same process and environment. It does not
search parent directories or set up an environment for you.

| Exit code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Task failure or error loading or defining tasks. |
| `2` | Invalid command, missing task file, unknown task, or empty `--default` selection. |
| `130` | Interrupted with Ctrl-C. |

If importing `tasks.py` or running a task raises an exception, Harbinger prints
its cause and source location. A task that raises `SystemExit` fails even if its
exit code is zero. Listing an empty `tasks.py` succeeds.

## Limitations

Task functions must be regular synchronous functions. Harbinger ignores their
return values. Async functions, generators, required parameters, and arguments
for multiple tasks are not supported. To compose tasks, call one task function
from another.
