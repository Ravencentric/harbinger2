from functools import wraps
from typing import TYPE_CHECKING, Final, overload

from .registry import TaskRegistry

if TYPE_CHECKING:
    from .types import P, R, TaskDecorator, TaskFn

TASKFILE: Final = "megatron.py"
REGISTRY: Final[TaskRegistry] = TaskRegistry()


@overload
def task(fn: TaskFn[P, R], /) -> TaskFn[P, R]: ...


@overload
def task(*, name: str | None = None) -> TaskDecorator[P, R]: ...


def task(
    fn: TaskFn[P, R] | None = None,
    /,
    *,
    name: str | None = None,
) -> TaskFn[P, R] | TaskDecorator[P, R]:

    def decorator(fn: TaskFn[P, R], /) -> TaskFn[P, R]:
        REGISTRY.register(fn, name=name)

        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> R:
            return fn(*args, **kwargs)

        return inner

    if fn is None:
        return decorator

    return decorator(fn)
