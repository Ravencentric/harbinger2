import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from rich.console import Console
from rich.markup import escape

from .core import REGISTRY, TASKFILE
from .errors import TaskError, UndefinedTaskNameError

console = Console()
error_console = Console(stderr=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harbinger",
        description="Run tasks from megatron.py.",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="task to run; omit to list available tasks",
    )
    return parser


def import_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"invalid task file: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_tasks() -> None:
    console.print("[bold cyan]Tasks[/]")

    if not REGISTRY.inner:
        console.print("[dim]  No tasks found.[/]")
        return

    for name, task in sorted(REGISTRY.inner.items()):
        console.print(f"  [bold]{escape(name)}[/] [dim]({escape(task.func.__name__)})[/]")


def render_error(title: str, message: str) -> None:
    error_console.print(f"[bold red]{title}[/]")
    error_console.print(message)


def render_unknown_task(name: str) -> None:
    available = ", ".join(escape(task) for task in sorted(REGISTRY.inner)) or "none"
    render_error(
        "Unknown task",
        f"No task named [bold]{escape(name)}[/].\n\nAvailable tasks: {available}",
    )


def run_task(name: str) -> int:
    try:
        REGISTRY.call(name)
    except UndefinedTaskNameError:
        render_unknown_task(name)
        return 1
    except TaskError as error:
        source = error.__cause__
        message = str(source) if source is not None else "task failed"
        render_error("Task failed", message)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path.cwd() / TASKFILE

    if not path.is_file():
        render_error(
            "Task file not found",
            f"Expected [bold]{escape(TASKFILE)}[/] in {escape(str(Path.cwd()))}",
        )
        return 1

    try:
        import_from_path(path)
    except Exception as error:
        render_error("Could not load task file", escape(str(error)))
        return 1

    if args.task is None:
        render_tasks()
        return 0

    return run_task(args.task)


if __name__ == "__main__":
    sys.exit(main())
