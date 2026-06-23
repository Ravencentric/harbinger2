import inspect
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from harbinger.coerce import converter_for, identity
from harbinger.errors import TaskDefinitionError


@pytest.mark.parametrize("annotation", [int, str, float, bool, Path])
def test_supported(annotation: object) -> None:
    assert converter_for(annotation) is annotation


@pytest.mark.parametrize("annotation", [object, Any, inspect.Parameter.empty])
def test_noop(annotation: object) -> None:
    assert converter_for(annotation) is identity


@pytest.mark.parametrize("annotation", [bytes, datetime])
def test_unsupported_rejected(annotation: object) -> None:
    with pytest.raises(TaskDefinitionError):
        converter_for(annotation)
