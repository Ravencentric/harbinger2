"""Exercise every CLI path."""

import subprocess


def run(label: str, *args: str) -> None:
    print(f"\n-- {label} --")
    subprocess.run(["uv", "run", "harbinger", *args])


run("NoArgs (lists)")
run("ListTasks", "--list")
run("RunAll", "--all")
run("Version", "--version")
run("RunSelected", "hello")
run("Invoke: greet", "greet", "--", "Alice")
run("Invoke: greet x3", "greet", "--", "Bob", "--count", "3")
run("Invoke: greet loud", "greet", "--", "Charlie", "--count", "2", "--loud")
run("Invoke: greet --no-loud", "greet", "--", "Dana", "--no-loud")
run("Invoke: add", "add", "--", "3", "2")
run("Invoke: cat", "cat", "--", "pyproject.toml")
run("Invoke: cat --numbered", "cat", "--", "pyproject.toml", "--numbered")
run("Per-task help", "greet", "--", "--help")
run("Error: unknown task", "nonexistent")
run("Invoke: greet default", "greet", "--")
run("Error: bad type", "add", "--", "hello", "world")
run("Error: bare --", "--")
