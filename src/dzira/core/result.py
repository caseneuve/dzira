from __future__ import annotations

from dataclasses import dataclass
from functools import wraps, reduce
from typing import Any, Callable, Generic, TypeVar, Union, cast


T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=Exception)


@dataclass(frozen=True)
class Result(Generic[T, E]):
    """Represents a result that can be either success or failure,
    where success is any non-exception value returned and failure
    wraps the exception."""

    value: T | None = None
    error: E | None = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return self.error is not None

    def map(self, fn: Callable[[T], U]) -> Result[U, E]:
        """Apply function to value if success, otherwise return failure."""
        if self.is_failure:
            return Result(error=self.error)
        try:
            return Result(value=fn(cast(T, self.value)))
        except Exception as e:
            return Result(error=cast(E, e))

    def bind(self, fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Flat map - apply function that returns Result."""
        if self.is_failure:
            return Result(error=self.error)
        try:
            new_result = fn(cast(T, self.value))
            return Result(
                value=new_result.value,
                error=new_result.error,
            )
        except Exception as e:
            return Result(error=cast(E, e))

    def fold(self, on_success: Callable[[T], U], on_failure: Callable[[E], U]) -> U:
        """Handle both success and failure cases."""
        if self.is_success:
            return on_success(cast(T, self.value))
        else:
            return on_failure(cast(E, self.error))

    def tee(self, fn: Callable[[T], None]) -> Result[T, E]:
        """Apply side effect function if success, return original result."""
        if self.is_success:
            try:
                fn(cast(T, self.value))
            except Exception:
                pass  # Ignore side effect errors
        return self

    def or_else(self, default: T) -> T:
        """Return value if success, otherwise return default."""
        return cast(T, self.value) if self.is_success else default

    def or_else_result(self, fn: Callable[[], Result[T, E]]) -> Result[T, E]:
        return self if self.is_success else fn()

    def __bool__(self) -> bool:
        return self.is_success


def success(value: T) -> Result[T, Exception]:
    return Result(value=value)


def failure(error: E) -> Result[Any, E]:
    return Result(error=error)


def safe(fn: Callable[..., T]) -> Callable[..., Result[T, Exception]]:
    """Decorator to wrap function in Result, catching exceptions."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Result[T, Exception]:
        for arg in args:
            if isinstance(arg, Result) and arg.is_failure:
                return Result(error=arg.error)

        processed_args = [arg.value if isinstance(arg, Result) else arg for arg in args]

        try:
            return success(fn(*processed_args, **kwargs))
        except Exception as e:
            return failure(e)

    return wrapper


def pipe(
    value: Union[T, Result[T, Exception]], *fns: Callable[[Any], Result[Any, Exception]]
) -> Result[Any, Exception]:
    result = value if isinstance(value, Result) else success(value)
    return reduce(lambda acc, fn: acc.bind(fn) if acc.is_success else acc, fns, result)


def compose(*fns: Callable[[Any], Any]) -> Callable[[Any], Any]:
    return lambda x: reduce(lambda acc, fn: fn(acc), reversed(fns), x)


def partial(
    fn: Callable[..., Any], *partial_args: Any, **partial_kwargs: Any
) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*partial_args, *args, **partial_kwargs, **kwargs)

    return wrapper
