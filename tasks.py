import subprocess

from harbinger import task

base = ["uv", "run"]


@task
def lint() -> None:
    """Run the ruff linter."""
    subprocess.run(base + ["ruff", "check", "."], check=True)


@task
def format(*, check: bool = False) -> None:
    """Format code with ruff."""
    cmd = ["ruff", "format", "."]
    if check:
        cmd.append("--check")
    subprocess.run(base + cmd, check=True)


@task
def typecheck() -> None:
    """Run the pyrefly type checker."""
    subprocess.run(base + ["pyrefly", "check"], check=True)


@task
def test() -> None:
    """Run the test suite."""
    subprocess.run(base + ["pytest"], check=True)


@task(default=False)
def check() -> None:
    """Run all static gates (lint, format-check, typecheck, test)."""
    lint()
    format(check=True)
    typecheck()
    test()


def _build_artifact(target: str) -> str:
    print(f"building {target}...")
    return f"dist/{target}.tar"


def _connect(region: str) -> None:
    raise ConnectionError(f"connection refused for {region}")


def _upload(artifact: str, *, region: str) -> None:
    print(f"uploading {artifact} to {region}...")
    try:
        _connect(region)
    except ConnectionError as source:
        raise RuntimeError(
            f"region {region!r} is unreachable (simulated outage)"
        ) from source


def _deploy_to(target: str, *, region: str) -> None:
    artifact = _build_artifact(target)
    _upload(artifact, region=region)


@task(default=False)
def fail(*, target: str = "app", region: str = "us-east-1") -> None:
    """Simulate a multi-step deploy that fails mid-flight (showcase error UX)."""
    print(f"deploying {target} to {region}")
    _deploy_to(target, region=region)
    print("deploy complete")
