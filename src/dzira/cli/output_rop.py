from __future__ import annotations

import concurrent.futures
import sys
import time
from functools import wraps
from itertools import cycle
from typing import Callable, TypeVar

from jira.exceptions import JIRAError

from ..core.result import Result, failure

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


class Colors:
    use = True
    C = {
        k: f"\033[{v}m"
        for k, v in (
            ("^reset", 0),
            ("^bold", 1),
            ("^red", 91),
            ("^green", 92),
            ("^yellow", 93),
            ("^blue", 94),
            ("^magenta", 95),
            ("^cyan", 96),
        )
    }

    def c(self, *args):
        if self.use:
            return "".join([self.C.get(a, a) for a in args]) + self.C["^reset"]
        return "".join([a for a in args if a not in self.C])


class ROPSpinner:
    def __init__(self, colorizer: Colors):
        self.colorizer = colorizer
        self.use = True

    def with_spinner(
        self,
        msg: str = "",
        success_msg_fn: Callable[[Result], str] | None = None,
        done: str = " ",
        fail: str = " ",
    ):
        """
        Decorator for async spinner with ROP Result types.

        Args:
            msg: Message to show during operation
            success_msg_fn: Function to generate success message from result value
            done: Success indicator character
            fail: Failure indicator character
        """
        spinner_chars = cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        separator = "  "
        connector = ":\t"

        def decorator(func):
            func.is_decorated_with_spinner = True

            @wraps(func)
            def wrapper(*args, **kwargs) -> Result[T, E]:
                if not self.use:
                    return func(*args, **kwargs)

                try:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(func, *args, **kwargs)

                        # Show spinner animation while function runs
                        while future.running():
                            print(
                                self.colorizer.c(
                                    "\r",
                                    "^magenta",
                                    next(spinner_chars),
                                    separator,
                                    msg,
                                ),
                                end="",
                                flush=True,
                                file=sys.stderr,
                            )
                            time.sleep(0.1)

                        result: Result[T, E] = future.result()

                        if result.is_success:
                            success_msg = "done"
                            if success_msg_fn and result.value is not None:
                                try:
                                    success_msg = success_msg_fn(result)
                                except:
                                    pass

                            print(
                                self.colorizer.c(
                                    "\r",
                                    "^green",
                                    done,
                                    separator,
                                    msg,
                                    "^reset",
                                    connector,
                                    success_msg,
                                ),
                                flush=True,
                                file=sys.stderr,
                            )
                        else:
                            error_msg = self._format_error_message(
                                result.error, func.__name__
                            )
                            print(
                                self.colorizer.c(
                                    "\r",
                                    "^red",
                                    fail,
                                    separator,
                                    msg,
                                    "^reset",
                                    connector,
                                    error_msg,
                                ),
                                flush=True,
                                file=sys.stderr,
                            )

                        return result

                except Exception as exc:
                    error_msg = self._format_error_message(exc, func.__name__)
                    print(
                        self.colorizer.c("\r", "^red", fail, separator, msg),
                        end=":\t",
                        flush=True,
                        file=sys.stderr,
                    )
                    print(error_msg, file=sys.stderr)
                    return failure(exc)

            return wrapper

        return decorator

    def _format_error_message(self, exc: Exception, func_name: str) -> str:
        if isinstance(exc, JIRAError):
            messages = exc.response.json().get("errorMessages", [])
            if messages:
                return " ".join(messages)
            else:
                return (
                    f"{func_name.replace('_', ' ')} returned an error: "
                    f"{exc.response.reason!r} :("
                )
        else:
            return str(exc)


def hide_cursor():
    print("\033[?25l", end="", flush=True, file=sys.stderr)


def show_cursor():
    print("\033[?25h", end="", flush=True, file=sys.stderr)


# Global spinner instance convenience function
def with_spinner(
    msg: str = "",
    success_msg_fn: Callable[[Result], str] | None = None,
    done: str = "✓",
    fail: str = "✗",
):
    """
    Convenience decorator for async spinner with ROP Result types.

    Args:
        msg: Message to show during operation
        success_msg_fn: Function to generate success message from Result
        done: Success indicator character
        fail: Failure indicator character
    """
    colors = Colors()
    spinner = ROPSpinner(colors)
    return spinner.with_spinner(msg, success_msg_fn, done, fail)
