import importlib
import importlib.util
import sys
from pathlib import Path

from .core import REGISTRY, TASKFILE


def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    f = Path.cwd() / TASKFILE
    assert f.is_file()
    import_from_path("megatron", f)
    REGISTRY.inner["hello"].call()
