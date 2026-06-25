# harbinger

A minimal, correct, user-friendly task runner. Define tasks in a `tasks.py` file, run them from the command line.

## Install

```
uv add harbinger
```

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
def greet(name: str = "World", *, count: int = 1) -> None: ...
```

### Name normalization

Function names are converted from `snake_case` to `kebab-case`. A function named `my_task` is invoked as `harbinger my-task`.

## Run tasks

```
harbinger              # list available tasks
harbinger --list       # same as above
harbinger --default    # run default tasks only
harbinger --all        # run all tasks
harbinger --version    # print version
harbinger hello        # run one or more tasks by name
```

Tasks are included in `--default` by default. Mark composite/aggregator tasks with `default=False`:

```python
@task(default=False)
def check() -> None:
    """Run all gates."""
    lint()
    test()
```

### Passing arguments

Use `--` to separate task arguments from harbinger's own flags. Arguments after `--` are parsed according to the task's signature:

```
harbinger greet -- Alice
harbinger greet -- Bob --count 3
harbinger greet -- Charlie --count 2 --loud
harbinger greet -- Dana --no-loud
```

Per-task help:

```
harbinger greet -- --help
```

## Supported parameter types

Every task parameter **must have a default value**. Supported annotations:

| Type    | Notes                                              |
|---------|----------------------------------------------------|
| `str`   |                                                    |
| `int`   |                                                    |
| `float` |                                                    |
| `bool`  | Must be keyword-only (use `*, flag: bool = False`) |
| `Path`  | From `pathlib`                                     |

Unannotated parameters are treated as `str`. `bool` parameters expose `--flag` / `--no-flag`. `*args` and `**kwargs` are not supported.

## Errors

Harbinger exits `0` on success, `2` on usage errors, and `1` on any other failure. When a task fails, the error and its full cause chain are printed:

    error: task 'deploy' failed

    caused by:
        0: region 'us-east-1' is unreachable
           in _upload() at tasks.py:51
        1: connection refused for us-east-1
           in _connect() at tasks.py:47

- `task file not found: <path>` — no `tasks.py` in the working directory.
- `unknown task '<name>'` — includes a "did you mean" suggestion when a name is close.
- `could not load <path>` — `tasks.py` raised at import; the cause chain shows why.
- `task '<name>' failed` — a task raised; the cause chain shows the root error.

## Task file

The task file is always `tasks.py` in the current working directory. It runs as a standalone module — import only installed packages, not sibling files.
