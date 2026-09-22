# harbinger

A minimal, correct, user-friendly task runner. Define tasks in a `tasks.py` file, run them from the command line.

## Install

Harbinger requires Python 3.14 or later. Install it in the same environment as
the project whose tasks it will run:

```console
uv add --dev harbinger
```

Run it with `uv run harbinger`. The examples below use `harbinger` for brevity.

## Define tasks

Create a `tasks.py` in your project root. Decorate functions with `@task`:

```python
from pathlib import Path
from harbinger import task

@task
def hello() -> None:
    """Print a small greeting."""
    print("Hello")

@task
def greet(name: str = "World", *, count: int = 1, loud: bool = False) -> None:
    """Greet someone N times."""
    msg = f"Hello, {name}!" if not loud else f"HELLO, {name.upper()}!"
    for _ in range(count):
        print(msg)
```

### The decorator

`@task` uses the function name and docstring by default. Override either with:

```python
@task(name="greet", description="Greet someone N times")
def welcome(name: str = "World", *, count: int = 1) -> None: ...
```

Listings show the first line of a description; per-task help uses its full text.

### Name normalization

Function names are converted from `snake_case` to `kebab-case`. A function named `my_task` is invoked as `harbinger my-task`.
Task names must start with a letter, end with a letter or number, and otherwise
contain only printable non-whitespace characters.

## Run tasks

```console
harbinger                 # list available tasks
harbinger --list          # list explicitly (-l)
harbinger --default       # run default tasks only (-d)
harbinger --all           # run all tasks (-a)
harbinger --version       # print the version (-V)
harbinger hello           # run one task
harbinger hello check     # run multiple tasks in order
```

`python -m harbinger` also works.

Selection modes cannot be combined. When multiple tasks are selected, Harbinger
validates the entire selection before starting, then runs them in order and
stops at the first failure. A task name repeated on the command line runs once
per occurrence.

Tasks are excluded from `--default` by default. Mark a task with `default=True`
to opt it in:

```python
@task(default=True)
def check() -> None:
    """Run all gates."""
    lint()
    test()
```

### Passing arguments

Use `--` to separate task arguments from Harbinger's own arguments. Exactly one
task must precede it; arguments cannot be passed to a multi-task selection.
Arguments after `--` are parsed according to the task's signature:

```console
harbinger greet -- Alice
harbinger greet -- Bob --count 3
harbinger greet -- Charlie --count 2 --loud
harbinger greet -- Dana --no-loud
```

Per-task help:

```console
harbinger greet -- --help
```

Parameter names containing underscores become kebab-case options. For example,
`output_dir` is exposed as `--output-dir`.

## Supported parameter types

Every fixed task parameter **must have a default value**. Supported annotations:

| Type                     | Notes                                              |
|--------------------------|----------------------------------------------------|
| `str`                    |                                                    |
| `int`                    |                                                    |
| `float`                  |                                                    |
| `bool`                   | Must be keyword-only (use `*, flag: bool = False`) |
| `Path`                   | From `pathlib`                                     |
| `Literal["dev", "prod"]` | String choices from `typing`                       |
| `Literal[1, 2]`          | Integer choices from `typing`                      |

Unannotated parameters are treated as `str`. `bool` parameters expose `--flag` / `--no-flag`.

`Literal` choices must all be strings or all integers. For example:

```python
from typing import Literal

@task
def deploy(*, environment: Literal["dev", "prod"] = "dev") -> None:
    print(environment)
```

`harbinger deploy -- --help` shows `--environment {dev, prod}`.

### Variadic tasks

A task may accept a single `*args` parameter (typed or untyped) to collect an arbitrary number of positional values:

```python
@task
def files(*paths: Path) -> None:
    """Process one or more paths."""
    for p in paths:
        print(p)
```

```console
harbinger files -- a.txt b.txt c.txt
```

A variadic parameter may be followed by keyword-only parameters (`*args` plus `--flag` options), which is the natural CLI pattern for commands like `cp -r src dst1 dst2`:

```python
@task
def cp(*paths: Path, recursive: bool = False) -> None:
    """Copy paths."""
    for p in paths:
        print(p, recursive)
```

```console
harbinger cp -- --recursive a.txt b.txt
```

A variadic parameter cannot be mixed with non-keyword positional parameters, and `**kwargs` is not supported. The positional case (`*args` alongside a regular positional) makes the positional's default unreachable (argparse fills `nargs="?"` from the left), and `**kwargs` has no clean declarative mapping onto argparse. Flags may appear in any position, before or after the positional values.

## Errors

Harbinger exits `0` on success, `2` on usage errors, `130` when interrupted,
and `1` on any other failure. When a task fails, the error and its full cause
chain are printed:

    error: task 'deploy' failed

    caused by:
        0: RuntimeError: region 'us-east-1' is unreachable
           in _upload() at tasks.py:51
        1: ConnectionError: connection refused for us-east-1
           in _connect() at tasks.py:47

- `task file not found: <path>` — no `tasks.py` in the working directory.
- `unknown task '<name>'` — includes a "did you mean" suggestion when a name is close.
- `could not load <path>` — `tasks.py` raised at import; the cause chain shows why.
- `task '<name>' failed` — a task raised; the cause chain shows the root error.
- `interrupted` — execution was stopped with Ctrl-C.

`SystemExit`, including a zero status, is treated as a failure when raised while
loading `tasks.py` or running a task. Successful tasks return normally.

`--all` is a usage error when no tasks exist, and `--default` is a usage error
when no tasks are marked as default. Listing an empty task file succeeds.

## Task file

The task file is always `tasks.py` in the current working directory. It is
loaded as a standalone module, and its imports use normal Python resolution.
Harbinger does not modify the import path, create an environment, or install the
project on your behalf. Tasks run in the Harbinger process.

## Scope and limitations

### By design

- A bare `harbinger` invocation lists tasks instead of running one implicitly.
- Task files are trusted Python. Harbinger does not sandbox tasks or roll back
  their effects.
- Harbinger only looks for `tasks.py` in the current directory and uses normal
  Python import resolution; it does not search parents or alter the import path.
- Harbinger does not manage environments, dependencies, interpreter matrices,
  or `.env` files. Tasks can invoke other tools when needed.
- Booleans are keyword-only and use `--flag` / `--no-flag`.
- Retries, timeouts, confirmation, and environment setup belong in task code.
- Harbinger provides no build cache or plugin system.

### Not currently supported

- Required parameters; every fixed parameter needs a default.
- Passing arguments when multiple tasks are selected.
- `**kwargs`, or regular positional parameters combined with `*args`.
- Types beyond those listed above.
- Async or generator tasks. Return values are ignored; exceptions report failure.
- Task dependency graphs, richer selection, custom task-file paths, aliases,
  machine-readable output, shell completion, and subprocess conveniences.

These may be reconsidered for concrete use cases that do not substantially
increase complexity. Parallel execution is planned after the initial release.
