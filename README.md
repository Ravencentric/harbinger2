# harbinger

Harbinger is a small, dependency-free task runner where a task is a regular Python
function.

It's meant for Python projects because they already depend on Python, and it's
primarily meant for me. I believe declarative task runners just (foreshadowing)
cannot do everything I want them to, like cleaning up a bunch of artifacts in a
cross-platform way.

I could use a justfile and shell out, but then it's no longer cross-platform. I
could use justfile's `[script]`, but then I might as well just write a Python
script and call it directly instead.

`poethepoet` and `tox`, being declarative, suffer from much of the same issues.
Then there's `nox`, where you do write tasks in Python, but it's a full-blown
environment manager and more, and I'd have to go out of my way to stop it from
doing a bunch of extra work.

> [!NOTE]
> While I like where the API is going, I'm certain there will be a few
> sweeping and breaking changes. I've been on and off working on this
> for months now waiting to get the API right but that's not gonna happen
> anytime soon and I want to start dogfooding it now.

## Table Of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Task arguments](#task-arguments)
- [Running commands](#running-commands)
- [Errors and limitations](#errors-and-limitations)
- [Development](#development)

## Installation

Harbinger requires Python 3.14 or newer because it uses
[t-strings](https://docs.python.org/3/whatsnew/3.14.html#whatsnew314-template-string-literals).
Add it to your project's development dependencies with
[`uv`](https://docs.astral.sh/uv/):

```console
uv add --dev harbinger
```

You can then run it with `uv run harbinger`, or `uv run python -m harbinger`.
The examples below use `harbinger` for brevity.

> [!NOTE]
> Your project can still support older Python versions. Only the environment
> running Harbinger needs Python 3.14 or newer.
>
> With uv, you can give your development dependencies a separate Python requirement
> in `pyproject.toml`:
>
> ```toml
> # <https://docs.astral.sh/uv/reference/settings/#dependency-groups>
> [tool.uv.dependency-groups]
> dev = { requires-python = ">=3.14" }
> ```
>
> If you don't use uv, you should check your tool's documentation for something similar.

## Usage

Create a `tasks.py` file in your project root and decorate your functions with
`@task`:

```python
from harbinger import Cmd, task


@task(default=True)
def lint() -> None:
    """Check the code with Ruff."""
    Cmd("ruff").args(t"check").run()


@task(default=True)
def test() -> None:
    """Run the test suite."""
    Cmd("pytest").run()


@task
def ci() -> None:
    """Run all checks."""
    lint()
    test()
```

Run Harbinger from the directory containing `tasks.py`:

```console
harbinger                 # List the available tasks
harbinger lint            # Run a task
harbinger lint test       # Run several tasks in order
harbinger ci              # Call other tasks from a task
harbinger --default       # Run tasks marked default=True
harbinger --help          # Show command-line help
```

The function name becomes the task name, with underscores replaced by hyphens.
For example, `build_docs` becomes `build-docs`. The docstring becomes its
description. You can override either with `@task(name="...", description="...")`.

When you pass several task names, Harbinger checks that all of them exist before
running anything. Tasks run in the order you pass them, stopping at the first
failure.

`--default` runs the tasks marked `default=True` in the order they appear in
`tasks.py`, using their parameter defaults.

## Task arguments

Harbinger uses your function's signature to build its command-line interface.
Positional parameters become positional arguments, and keyword-only parameters
become options:

```python
from harbinger import task


@task
def greet(name: str = "World", *, count: int = 1, loud: bool = False) -> None:
    """Greet someone a number of times."""
    message = f"Hello, {name}!"
    for _ in range(count):
        print(message.upper() if loud else message)
```

Put `--` between the task name and its arguments:

```console
harbinger greet -- Alice
harbinger greet -- Bob --count 3
harbinger greet -- Charlie --count 2 --loud
harbinger greet -- Dana --no-loud
harbinger greet -- --help
```

Without the separator, `Alice` would be treated as another task name. Arguments
can only be passed to one task at a time. Underscores in option names become
hyphens too, so `output_dir` becomes `--output-dir`.

### Supported types

Every parameter except `*args` needs a default value. Parameters without a type
annotation are parsed as strings.

| Annotation | Behavior |
| --- | --- |
| `str`, `int`, `float`, `Path` | Convert the argument to the given type. |
| `bool` | Accept `--flag` and `--no-flag`. Must be keyword-only. |
| `Literal["dev", "prod"]` | Accept one of the listed strings. |
| `Literal[1, 2]` | Accept one of the listed integers. |

I'll add more types here if I find real use cases.

### Variable arguments

Use `*args` to accept any number of positional values. You can also have
keyword-only parameters after it:

```python
from pathlib import Path
from harbinger import task


@task
def paths(*paths: Path, absolute: bool = False) -> None:
    """Print the given paths."""
    for path in paths:
        print(path.absolute() if absolute else path)
```

```console
harbinger paths -- src tests
harbinger paths -- --absolute src tests
```

Options can appear before or after the positional values. `*args` can't be
combined with other positional parameters, and `**kwargs` isn't supported.

## Running commands

`Cmd` lets you build and reuse external commands:

```python
from harbinger import Cmd

uv = Cmd("uv").args(t"run")

uv.args(t"ruff check").run()
uv.args(t"pytest").run()
```

`.run()` waits for the command to finish and uses the parent's stdin, stdout, and
stderr. A nonzero exit status raises `subprocess.CalledProcessError` by default.

### Arguments and t-strings

Pass the executable to `Cmd`, then add arguments with `.args()`. Each call accepts
either one t-string or any number of strings and paths:

```python
from pathlib import Path
from harbinger import Cmd

paths = [Path("first file.py"), Path("second file.py")]

Cmd("git").args("add", *paths).run()
Cmd("git").args(t'commit -m "release build"').run()

destination = Path("build files")
Cmd("uv").args(t"build --out-dir={destination}").run()
```
Notice how I never quoted `{destination}`.
Thanks to t-strings, we can automatically quote interpolated values appropriately.
This was inspired by [PEP 787 – Safer subprocess usage using t-strings](https://peps.python.org/pep-0787/).

To pass a collection as separate arguments, unpack it with `*`:

```python
flags = ["-q", "-k", "slow tests"]
Cmd("pytest").args(*flags).run()
```

A regular string is passed as is, which
is important for filenames with spaces.

```python
add = Cmd("git").args("add")
add.args("my file.py").run() # git add "my file.py"
```

### Executables

Pass a program name to look it up on the current `PATH` when the command is
created, as in `Cmd("git")`. You can also pass an absolute executable path:

Relative executable paths such as `./tool` or `bin/tool` aren't accepted.
This is because their resolution is ambiguous. Should it be relative to
`tasks.py` or relative to your cwd?

### Configuration and reuse

`Cmd` is an immutable object, so every method returns a new instance:

```python
from harbinger import Cmd

base = Cmd("pytest").env({"CI": "1", "DEBUG": "0"})
debug = base.env({"DEBUG": "1"}).args("-s")

base.run()   # DEBUG=0
debug.run()  # DEBUG=1, with -s
```

### Output and exit status

`.run()` returns a `Run` with `.executable`, `.args` (excluding the executable),
and `.returncode`. To handle a nonzero exit status yourself, turn off checking:

```python
from harbinger import Cmd

result = Cmd("git").args(t"diff --quiet").check(False).run()
print(result.returncode)
```

`.capture()` captures stdout and stderr as UTF-8 text, returning a `Capture`
with the same fields plus `.stdout` and `.stderr`:

```python
result = Cmd("git").args(t"status --short").capture()
print(result.stdout)
print(result.stderr)

commit = Cmd("git").args(t"rev-parse HEAD").stdout()
```

`.stdout()` returns captured stdout with leading and trailing whitespace stripped.
Use `.capture().stdout` if you need to preserve whitespace.

## Errors and limitations

Harbinger loads `tasks.py` from the current directory and runs tasks in the same
process and environment. It doesn't search parent directories or create an
environment for you.

Task functions must be synchronous. Async functions, generators, and required
parameters aren't supported. Return values are ignored.

| Exit code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | A task failed, or there was an error loading or defining tasks. |
| `2` | Invalid command, missing task file, unknown task, or no default tasks. |
| `130` | Interrupted with Ctrl-C. |
