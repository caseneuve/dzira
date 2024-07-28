import sys
from unittest.mock import Mock, patch, sentinel

from jira.exceptions import JIRAError
import pytest

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

    @pytest.mark.xfail
    def test_todo_run(self):
        assert False, "Need to write tests"

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

        assert "page not found" in str(exc)

        @spinner.run("Testing")
        def non_jira_error():
            raise Exception("non jira exception")

        with pytest.raises(Exception) as exc:
            non_jira_error()

        assert "non jira exception" in str(exc)
