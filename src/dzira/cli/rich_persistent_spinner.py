from __future__ import annotations

import time
from functools import wraps
from typing import Callable, TypeVar

from rich.console import Console
from rich.status import Status

from dzira.core.result import Result, success, failure

T = TypeVar("T")
E = TypeVar("E", bound=Exception)

# Use stderr for spinner output (like your current implementation)
# Force colors to show even in non-TTY environments like tmux capture
console = Console(stderr=True, force_terminal=True)


def with_persistent_rich_spinner(
    msg: str = "",
    success_msg_fn: Callable[[Result], str] | None = None,
    spinner_style: str = "dots",
    done: str = "✓",
    fail: str = "✗",
):
    """
    Rich spinner that preserves all outputs - each spinner creates a persistent line.
    This matches your current behavior where multiple spinners don't override each other.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> Result[T, E]:
            # Start with a temporary status that we'll replace with persistent output
            with Status(f"[cyan]{msg}...", spinner=spinner_style, console=console) as status:
                try:
                    result: Result[T, E] = func(*args, **kwargs)

                    # Stop the spinner and clear the line
                    status.stop()

                    if result.is_success:
                        # Generate success message
                        success_msg = "done"
                        if success_msg_fn and result.value is not None:
                            try:
                                success_msg = success_msg_fn(result)
                            except:
                                pass

                        # Print persistent success line (stays visible)
                        console.print(f"[green]{done}[/]  {msg}:\t{success_msg}")

                    else:
                        # Print persistent error line
                        error_msg = str(result.error) if result.error else "failed"
                        console.print(f"[red]{fail}[/]  {msg}:\t{error_msg}")

                    return result

                except Exception as exc:
                    status.stop()
                    console.print(f"[red]{fail}[/]  {msg}:\t{str(exc)}")
                    return failure(exc)

        return wrapper
    return decorator


# Alternative approach using console.status context manager more explicitly
def with_rich_spinner_log(
    msg: str = "",
    success_msg_fn: Callable[[Result], str] | None = None,
    done: str = "✓",
    fail: str = "✗",
):
    """
    Another approach that creates a log-like output preserving all spinner results.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> Result[T, E]:
            # Show spinner during operation
            with console.status(f"[magenta]⠋[/]  {msg}...", spinner="dots"):
                result: Result[T, E] = func(*args, **kwargs)

            # After operation completes, print the persistent result line
            if result.is_success:
                success_msg = "done"
                if success_msg_fn and result.value is not None:
                    try:
                        success_msg = success_msg_fn(result)
                    except:
                        pass

                console.print(f"[green]{done}[/]  {msg}:\t{success_msg}")
            else:
                error_msg = str(result.error) if result.error else "failed"
                console.print(f"[red]{fail}[/]  {msg}:\t{error_msg}")

            return result

        return wrapper
    return decorator


# Example showing how multiple spinners preserve their output:
if __name__ == "__main__":
    import time

    @with_persistent_rich_spinner("Getting client", success_msg_fn=lambda r: "connecting to anaconda.atlassian.net")
    def get_client():
        time.sleep(1)  # Simulate work
        return success("jira_client")

    @with_persistent_rich_spinner("Getting issues", success_msg_fn=lambda r: "Found 8 issues")
    def get_issues():
        time.sleep(1.5)  # Simulate work
        return success(["issue1", "issue2"])

    @with_persistent_rich_spinner("Processing data", success_msg_fn=lambda r: "Processed successfully")
    def process_data():
        time.sleep(0.5)  # Simulate work
        return success("processed")

    # This will show:
    # ✓  Getting client:    connecting to anaconda.atlassian.net
    # ✓  Getting issues:    Found 8 issues
    # ✓  Processing data:   Processed successfully

    print("Demo of multiple persistent spinners:")
    get_client()
    get_issues()
    process_data()
    print("All spinner outputs preserved!")
