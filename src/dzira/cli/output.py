from __future__ import annotations

import concurrent.futures
import sys
import time
from dataclasses import dataclass, field
from functools import wraps
from itertools import cycle
from typing import Any

from jira.exceptions import JIRAError

from dzira.betterdict import D


class Colors:
    use = True
    C = {k: f"\033[{v}m" for k, v in (("^reset", 0),
                                      ("^bold", 1),
                                      ("^red", 91),
                                      ("^green", 92),
                                      ("^yellow", 93),
                                      ("^blue", 94),
                                      ("^magenta", 95),
                                      ("^cyan", 96))}

    def c(self, *args):
        if self.use:
            return "".join([self.C.get(a, a) for a in args]) + self.C["^reset"]
        return "".join([a for a in args if a not in self.C])


@dataclass
class Result:
    result: Any = None
    stdout: str = ""
    data: D = field(default_factory=D)


class Spinner:
    def __init__(self, colorizer):
        self.colorizer = colorizer
        self.use = True

    def run(self, msg="", done="✓", fail="✗"):
        spinner = cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        separator = "  "
        connector = ":\t"

        def decorator(func):
            func.is_decorated_with_spin_it = True

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.use:
                    return func(*args, **kwargs)
                try:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(func, *args, **kwargs)

                        while future.running():
                            print(
                                self.colorizer("\r", "^magenta", next(spinner), separator, msg),
                                end="",
                                flush=True,
                                file=sys.stderr
                            )
                            time.sleep(0.1)

                        r: Result = future.result()
                        print(
                            self.colorizer("\r", "^green", done, separator, msg, "^reset", connector, r.stdout),
                            flush=True,
                            file=sys.stderr
                        )
                        return r
                except Exception as exc:
                    if type(exc) == JIRAError:
                        messages = exc.response.json().get("errorMessages", [])
                        if messages:
                            error_msg = " ".join(messages)
                        else:
                            error_msg = (
                                f"failed not perform the request while trying to {func.__name__.replace('_', ' ')}"
                                " (no error supplied by JIRA) :("
                            )
                    else:
                        error_msg = exc
                    print(
                        self.colorizer("\r", "^red", fail, separator, msg),
                        end=":\t",
                        flush=True,
                        file=sys.stderr
                    )
                    raise Exception(error_msg)
            return wrapper
        return decorator


def hide_cursor():
    print("\033[?25l", end="", flush=True, file=sys.stderr)


def show_cursor():
    print("\033[?25h", end="", flush=True, file=sys.stderr)
