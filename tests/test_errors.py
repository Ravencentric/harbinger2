from __future__ import annotations

import pytest

from harbinger.errors import HarbingerError


def test_causes_follows_implicit_context() -> None:
    with pytest.raises(HarbingerError) as excinfo:
        try:
            raise ConnectionError("connection refused")
        except ConnectionError:
            raise HarbingerError("upload failed")

    assert [type(cause) for cause in excinfo.value.causes()] == [ConnectionError]


def test_causes_respects_suppressed_context() -> None:
    with pytest.raises(HarbingerError) as excinfo:
        try:
            raise ConnectionError("connection refused")
        except ConnectionError:
            raise HarbingerError("upload failed") from None

    assert excinfo.value.causes() == []


def test_causes_prefers_explicit_cause() -> None:
    with pytest.raises(HarbingerError) as excinfo:
        try:
            raise ConnectionError("incidental context")
        except ConnectionError:
            raise HarbingerError("upload failed") from ValueError("explicit cause")

    assert [type(cause) for cause in excinfo.value.causes()] == [ValueError]


def test_causes_stops_at_cycle() -> None:
    first = RuntimeError("first")
    second = RuntimeError("second")
    first.__cause__ = second
    second.__cause__ = first

    error = HarbingerError("task failed")
    error.__cause__ = first

    assert error.causes() == [first, second]
