from dataclasses import dataclass
from functools import wraps
from typing import Callable, Any


@dataclass
class Result:
    value: Any | None
    error: Exception | None


def safe(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Result:
        for arg in args:
            if isinstance(arg, Result) and arg.error:
                return arg
        processed_args = [arg.value if isinstance(arg, Result) else arg for arg in args]
        try:
            return Result(value=fn(*processed_args, **kwargs), error=None)
        except Exception as e:
            return Result(value=None, error=e)

    return wrapper


def pipe(value: Any, *fns: Callable) -> Result:
    result = value if isinstance(value, Result) else Result(value=value, error=None)
    for fn in fns:
        if result.error:
            return result
        result = fn(result)
    return result
