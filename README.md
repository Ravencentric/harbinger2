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
import subprocess

from harbinger import task


@task(default=True)
def test() -> None:
    """Run the test suite."""
    subprocess.run(["pytest"], check=True)
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
