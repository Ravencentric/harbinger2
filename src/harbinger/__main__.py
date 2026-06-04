import importlib
import importlib.util
from pathlib import Path

from rich import print

from .core import REGISTRY, TASKFILE


def import_from_path(path: Path) -> None:
    spec = importlib.util.spec_from_file_location("megatron", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def main() -> None:
    f = Path.cwd() / TASKFILE
    assert f.is_file()
    import_from_path(f)
    print(REGISTRY)
