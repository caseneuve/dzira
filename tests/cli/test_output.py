import sys
import time
from unittest.mock import Mock, call, patch, sentinel

import pytest
from jira.exceptions import JIRAError

from src.dzira.betterdict import D
from src.dzira.cli.output import (
    Colors,
    Result,
    Spinner,
    hide_cursor,
    show_cursor,
)


class TestColors:
    @pytest.mark.parametrize(
        "test_input,expected",
        [
            ("^bold", "\033[1m\033[0m"),
            ("^red", "\033[91m\033[0m"),
            ("^green", "\033[92m\033[0m"),
            ("^yellow", "\033[93m\033[0m"),
            ("^blue", "\033[94m\033[0m"),
            ("^magenta", "\033[95m\033[0m"),
            ("^cyan", "\033[96m\033[0m"),
         ]
    )
    def test_uses_right_codes_for_given_colors(self, test_input, expected):
        assert Colors().c(test_input) == expected

    @pytest.mark.parametrize(
        "test_input,expected",
        [
            (("^red", "text"), "\033[91mtext\033[0m"),
            (("red",), "red\033[0m"),
            (
                ("^bold", "one ", "^reset", "^green", "two"),
                "\033[1mone \033[0m\033[92mtwo\033[0m"
            ),
         ]
    )
    def test_is_variadic(self, test_input, expected):
        assert Colors().c(*test_input) == expected

    def test_returns_string_without_color_tags_when_use_color_is_false(self):
        colors = Colors()
        colors.use = False

        assert colors.c("^bold", "this ", "^red", "text ", "^blue", "does not have colors", "^reset") == (
            "this text does not have colors"
        )


@patch("src.dzira.cli.output.print")
class TestCursorHelpers:
    def test_hides_cursor(self, mock_print):
        hide_cursor()

        mock_print.assert_called_once_with("\033[?25l", end="", flush=True, file=sys.stderr)

    def test_shows_cursor(self, mock_print):
        show_cursor()

        mock_print.assert_called_once_with("\033[?25h", end="", flush=True, file=sys.stderr)


class TestResult:
    def test_instantiates_with_default_values_for_result_stdout_and_data(self):
        result = Result()

        assert result.result is None
        assert result.stdout == ""
        assert result.data == D()

    def test_instantiates_with_given_values(self):
        result = Result(result=sentinel.result, stdout="foo")

        assert result.result == sentinel.result
        assert result.stdout == "foo"


class TestSpinner:
    def test_is_initialized_properly(self):
        colors = Colors()
        spinner = Spinner(colors.c)

        assert spinner.colorizer == colors.c
        assert spinner.use == True

    @patch("src.dzira.cli.output.print")
    @patch("src.dzira.cli.output.concurrent.futures.ThreadPoolExecutor")
    def test_uses_spinner(self, mock_thread_pool_executor, mock_print):
        mock_submit = Mock(
            return_value=Mock(
                running=Mock(side_effect=[True, False]),
                result=Mock(
                    return_value=Mock(
                        stdout=sentinel.stdout
                    )
                )
            )
        )
        mock_thread_pool_executor.return_value.__enter__.return_value.submit = mock_submit

        mock_colorizer = Mock(side_effect=[sentinel.for_running, sentinel.for_result])
        spinner = Spinner(mock_colorizer)

        @spinner.run(msg=sentinel.msg, done=sentinel.done)
        def run_with_spinner(arg, kwarg=None):
            time.sleep(0.11)
            return [arg, kwarg]

        run_with_spinner(sentinel.arg, kwarg=sentinel.kwarg)

        assert run_with_spinner.is_decorated_with_spinner
        assert mock_submit.call_args[0][0].__name__ == "run_with_spinner"
        assert mock_submit.call_args[0][1] == sentinel.arg
        assert mock_submit.call_args[1] == {"kwarg": sentinel.kwarg}
        assert mock_print.call_args_list == [
            call(sentinel.for_running, end="", flush=True, file=sys.stderr),
            call(sentinel.for_result, flush=True, file=sys.stderr),
        ]
        assert mock_colorizer.call_args_list == [
            call("\r", "^magenta", "⠋", "  ", sentinel.msg),
            call("\r", "^green", sentinel.done, "  ", sentinel.msg, "^reset", ":\t", sentinel.stdout)
        ]

    @patch("src.dzira.cli.output.concurrent.futures.ThreadPoolExecutor")
    def test_does_not_use_spinner(self, mock_thread_pool_executor):
        spinner = Spinner(Mock())
        spinner.use = False

        @spinner.run("Testing")
        def run_without_spinner():
            return sentinel.result

        result = run_without_spinner()

        assert run_without_spinner.is_decorated_with_spinner
        assert result == sentinel.result
        assert not mock_thread_pool_executor.called

    @patch("src.dzira.cli.output.print", Mock())
    def test_gracefully_reports_errors(self):
        colors = Colors()
        spinner = Spinner(colors.c)

        @spinner.run("Testing")
        def jira_error_with_reason():
            raise JIRAError(
                "error",
                status_code=500,
                url="foo.bar.baz",
                request=Mock(),
                response=Mock(
                    json=Mock(return_value={}),
                    reason="blah!"
                ),
            )

        with pytest.raises(Exception) as exc:
            jira_error_with_reason()

        assert jira_error_with_reason.is_decorated_with_spinner
        assert "jira error with reason returned an error: 'blah!'" in str(exc)

        @spinner.run("Testing")
        def jira_error_with_json():
            raise JIRAError(
                "error",
                status_code=404,
                url="foo.bar.baz",
                request=Mock(),
                response=Mock(
                    json=Mock(return_value={"errorMessages": ["page not found"]}),
                ),
            )

        with pytest.raises(Exception) as exc:
            jira_error_with_json()

        assert jira_error_with_json.is_decorated_with_spinner
        assert "page not found" in str(exc)

        @spinner.run("Testing")
        def non_jira_error():
            raise Exception("non jira exception")

        with pytest.raises(Exception) as exc:
            non_jira_error()

        assert non_jira_error.is_decorated_with_spinner
        assert "non jira exception" in str(exc)
