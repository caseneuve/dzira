"""Railway-Oriented Programming (ROP) utilities for functional error handling."""

from dataclasses import dataclass
from functools import wraps, reduce
from typing import Callable, TypeVar, Generic, Any, Union, cast, Dict

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=Exception)


@dataclass(frozen=True)
class Result(Generic[T, E]):
    """Represents a result that can be either success or failure."""

    value: T | None = None
    error: E | None = None
    data: Dict[str, Any] | None = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return self.error is not None

    def map(self, fn: Callable[[T], U]) -> "Result[U, E]":
        """Apply function to value if success, otherwise return failure."""
        if self.is_failure:
            return Result(error=self.error, data=self.data)
        try:
            return Result(value=fn(cast(T, self.value)), data=self.data)
        except Exception as e:
            return Result(error=cast(E, e), data=self.data)

    def bind(self, fn: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        """Flat map - apply function that returns Result."""
        if self.is_failure:
            return Result(error=self.error, data=self.data)
        try:
            new_result = fn(cast(T, self.value))
            # Merge data from both results - new result takes precedence
            merged_data = self.data.copy() if self.data else {}
            if new_result.data:
                merged_data.update(new_result.data)
            return Result(
                value=new_result.value,
                error=new_result.error,
                data=merged_data if merged_data else None,
            )
        except Exception as e:
            return Result(error=cast(E, e), data=self.data)

    def fold(self, on_success: Callable[[T], U], on_failure: Callable[[E], U]) -> U:
        """Handle both success and failure cases."""
        if self.is_success:
            return on_success(cast(T, self.value))
        else:
            return on_failure(cast(E, self.error))

    def tee(self, fn: Callable[[T], None]) -> "Result[T, E]":
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

    def __bool__(self) -> bool:
        return self.is_success

    def with_data(self, *_, **data) -> "Result[T, E]":
        """Return a new Result with updated data."""
        merged_data = self.data.copy() if self.data else {}
        merged_data.update(data)
        return Result(value=self.value, error=self.error, data=merged_data)

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data value by key."""
        if self.data is None:
            return default
        return self.data.get(key, default)


def success(value: T, data: Dict[str, Any] | None = None) -> Result[T, Exception]:
    """Create a success result."""
    return Result(value=value, data=data)


def failure(error: E, data: Dict[str, Any] | None = None) -> Result[Any, E]:
    """Create a failure result."""
    return Result(error=error, data=data)


def safe(fn: Callable[..., T]) -> Callable[..., Result[T, Exception]]:
    """Decorator to wrap function in Result, catching exceptions."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Result[T, Exception]:
        # Check if any args are Result objects with errors - propagate first error found
        for arg in args:
            if isinstance(arg, Result) and arg.is_failure:
                return Result(error=arg.error, data=arg.data)

        # Collect data from all Result arguments
        merged_data = {}
        for arg in args:
            if isinstance(arg, Result) and arg.data:
                merged_data.update(arg.data)

        # Extract values from Result objects, leave other args as-is
        processed_args = [arg.value if isinstance(arg, Result) else arg for arg in args]

        try:
            return success(
                fn(*processed_args, **kwargs), data=merged_data if merged_data else None
            )
        except Exception as e:
            return failure(e, data=merged_data if merged_data else None)

    return wrapper


def pipe(
    value: Union[T, Result[T, Exception]], *fns: Callable[[Any], Result[Any, Exception]]
) -> Result[Any, Exception]:
    """Pipe value through a sequence of functions."""
    result = value if isinstance(value, Result) else success(value)
    return reduce(lambda acc, fn: acc.bind(fn) if acc.is_success else acc, fns, result)


def compose(*fns: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Compose functions right to left."""
    return lambda x: reduce(lambda acc, fn: fn(acc), reversed(fns), x)


def partial(
    fn: Callable[..., Any], *partial_args: Any, **partial_kwargs: Any
) -> Callable[..., Any]:
    """Create a partial function with some arguments pre-filled."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*partial_args, *args, **partial_kwargs, **kwargs)

    return wrapper
