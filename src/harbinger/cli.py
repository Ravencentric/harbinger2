import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markup import escape

from .core import REGISTRY, TASKFILE
from .errors import TaskError, UndefinedTaskNameError
from .types import Task

console = Console()
error_console = Console(stderr=True)


def errmsg(message: str) -> str:
    return f"[red]error:[/] {escape(message)}"


@dataclass(frozen=True, slots=True)
class RichTaskList:
    tasks: dict[str, Task[..., object]]
    taskfile: str

    def __rich_console__(
        self, _console: Console, _options: ConsoleOptions
    ) -> RenderResult:
        if not self.tasks:
            yield errmsg(f"no tasks found in {escape(self.taskfile)}")
            return

        width = max(len(name) for name in self.tasks)

        yield f"[bold cyan]Tasks[/] [dim]{escape(self.taskfile)}[/]"
        yield ""

        for name, task in self.tasks.items():
            description = task.description or "No description."
            yield f"  [bold]{escape(name.ljust(width))}[/]  [dim]{escape(description)}[/]"

        yield ""
        yield "[dim]Run one task with[/] [bold]harbinger <task>[/]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harbinger",
        description="Run tasks from megatron.py.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available tasks without running them",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="task to run; omit to run every task in order",
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
    console.print(RichTaskList(REGISTRY.inner, TASKFILE))


def render_error(title: str, message: str) -> None:
    error_console.print(RichError(title, message))


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


def run_all_tasks() -> int:
    if not REGISTRY.inner:
        return 0

    for index, name in enumerate(REGISTRY.inner):
        if index > 0:
            console.print()

        console.print(f"[bold cyan]{escape(name)}[/]")
        status = run_task(name)

        if status != 0:
            return status

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

    if args.list:
        render_tasks()
        return 0

    if args.task is None:
        return run_all_tasks()

    return run_task(args.task)


if __name__ == "__main__":
    sys.exit(main())
