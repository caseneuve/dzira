import datetime
import os
import sys
from unittest.mock import Mock, PropertyMock, call, patch, sentinel
from jira.exceptions import JIRAError

import pytest
import click
from click.testing import CliRunner

from src.dzira.dzira import (
    CONFIG_DIR_NAME,
    D,
    DOTFILE,
    VALIDATE_DATE_FORMATS,
    Result,
    _get_sprints,
    _update_worklog,
    add_worklog,
    c,
    calculate_seconds,
    cli,
    establish_issue,
    get_board,
    get_config,
    get_config_from_file,
    get_issues,
    get_issues,
    get_jira,
    get_sprint,
    get_sprint_and_issues,
    get_worklog,
    hide_cursor,
    is_valid_hour,
    log,
    ls,
    main,
    matches_time_re,
    perform_log_action,
    process_sprint_out,
    sanitize_params,
    show_cursor,
    update_worklog,
    validate_date,
    validate_hour,
    validate_time,
)


@pytest.fixture
def config(mocker):
    mock_dotenv_values = mocker.patch("src.dzira.dzira.dotenv_values")
    mock_dotenv_values.return_value = {
        "JIRA_SERVER": "foo.bar.com",
        "JIRA_EMAIL": "name@example.com",
        "JIRA_TOKEN": "asdf1234",
        "JIRA_PROJECT_KEY": "XYZ",
    }
    return mock_dotenv_values


class TestC:
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
        assert c(test_input) == expected

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
        assert c(*test_input) == expected


class TestCursorHelpers:
    def test_hides_cursor(self, mocker):
        mock_print = mocker.patch("src.dzira.dzira.print")

        hide_cursor()

        mock_print.assert_called_once_with("\033[?25l", end="", flush=True)

    def test_shows_cursor(self, mocker):
        mock_print = mocker.patch("src.dzira.dzira.print")

        show_cursor()

        mock_print.assert_called_once_with("\033[?25h", end="", flush=True)


class TestResult:
    def test_instantiates_with_default_values_for_result_and_stdout(self):
        result = Result()

        assert result.result is None
        assert result.stdout == ""

    def test_instantiates_with_given_values(self):
        result = Result(result=sentinel.result, stdout="foo")

        assert result.result == sentinel.result
        assert result.stdout == "foo"


class TestD:
    d = D(a=1, b=2, c=3)

    def test_inherits_from_dict(self):
        assert isinstance(D(), dict)

    @pytest.mark.parametrize(
        "input,expected",
        [
            (("a", "c"), [1, 3]),
            (("a",), [1]),
            (("b", "x"), [2, None])
        ]

    )
    def test_call_returns_unpacked_values_of_selected_keys_or_none(self, input, expected):
        assert self.d(*input) == expected

    def test_update_returns_self_with_key_of_given_value(self):
        assert self.d.update("a", 99) == D({**self.d, "a": 99})
        assert self.d.update("x", 77) == D({**self.d, "x": 77})

    def test_update_accepts_multiple_key_value_pairs(self):
        assert self.d.update("d", 4, "e", 5) == D({**self.d, "d": 4, "e": 5})
        assert self.d.update(d=4, e=5) == D({**self.d, "d": 4, "e": 5})

    def test_update_raises_when_odd_number_of_args_given(self):
        with pytest.raises(Exception) as exc_info:
            self.d.update("a")

        assert "Provide even number of key-value args, need a value for key: 'a'" in str(exc_info.value)

    def test_has_returns_boolean_showing_if_key_has_a_value(self):
        assert self.d.has("a")
        assert self.d.has("foo") is False

    def test_repr(self):
        assert repr(D(a=1)) == "betterdict({'a': 1})"


class TestSpinIt:
    @pytest.mark.xfail
    def test_todo(self):
        assert False, "Need to write tests"


class TestGetConfigFromFile:
    def test_looks_for_config_file_in_default_locations_when_path_not_provided(
            self, mocker, config
    ):
        mocker.patch.dict(os.environ, {"HOME": "/home/foo"}, clear=True)
        mock_env_get = mocker.patch("src.dzira.dzira.os.environ.get")
        mock_os_path = mocker.patch("src.dzira.dzira.os.path")
        mock_dotenv_values = config

        get_config_from_file()

        mock_env_get.assert_called_once_with("XDG_CONFIG_HOME", "/home/foo")
        assert mock_os_path.join.call_args_list == [
            call(mock_env_get.return_value, CONFIG_DIR_NAME, "env"),
            call(mock_env_get.return_value, DOTFILE),
            call(os.environ["HOME"], ".config", CONFIG_DIR_NAME, "env"),
            call(os.environ["HOME"], ".config", DOTFILE)
        ]
        mock_dotenv_values.assert_called_once()

    def test_picks_up_first_matching_path_when_no_file_provided(self, mocker, config):
        mocker.patch.dict(os.environ, {"HOME": "/home/foo"}, clear=True)
        mock_os_path_isfile = mocker.patch("src.dzira.dzira.os.path.isfile")
        mock_os_path_isfile.side_effect = [False, True]
        mock_dotenv_values = config

        get_config_from_file()

        mock_dotenv_values.assert_called_once_with(f"/home/foo/{DOTFILE}")

    def test_looks_for_config_file_in_provided_location(self, config):
        mock_dotenv_values = config

        get_config_from_file(sentinel.path)

        mock_dotenv_values.assert_called_once_with(sentinel.path)

    def test_returns_empty_dict_when_no_file_found(self, mocker):
        mocker.patch("src.dzira.dzira.os.path.isfile", lambda _: False)

        result = get_config_from_file()

        assert result == {}


@patch("src.dzira.dzira.REQUIRED_KEYS", ("FOO", "BAR", "BAZ"))
@patch("src.dzira.dzira.get_config_from_file")
class TestGetConfig:
    def test_uses_user_provided_values_entirely(self, mock_config_from_file):
        override_conf = {"FOO": "123", "BAR": "abc", "BAZ": "zab"}

        result = get_config(override_conf)

        assert result == override_conf
        mock_config_from_file.assert_not_called()

    def test_uses_config_files_as_fallback(self, mock_config_from_file):
        mock_config_from_file.return_value = {"BAR": "abc", "BAZ": "999", "FOO": "321"}

        result = get_config({"BAR": "from override"})

        assert result == {"FOO": "321", "BAR": "from override", "BAZ": "999"}

    def test_uses_provided_file_instead_of_default_ones(self, mock_config_from_file):
        mock_config_from_file.return_value = {"FOO": "123", "BAR": "abc", "BAZ": "zab"}

        result = get_config({"file": "/path/to/file"})

        assert result == {
            "FOO": "123",
            "BAR": "abc",
            "BAZ": "zab",
            "file": "/path/to/file",
        }
        mock_config_from_file.assert_called_once_with("/path/to/file")

    def test_raises_when_required_values_not_found_in_compiled_config(
        self, mock_config_from_file
    ):
        mock_config_from_file.return_value = {"BAR": "abc"}
        with pytest.raises(Exception) as exc_info:
            get_config({})

        assert str(exc_info.value) == "could not find required config values: BAZ, FOO"


class TestGetJira:
    def test_jira_is_instantiated_with_provided_config_values(self, config, mocker):
        mock_get_jira = mocker.patch("src.dzira.dzira.JIRA")

        get_jira(config)

        mock_get_jira.assert_called_once_with(
            server=f"https://{config['JIRA_SERVER']}",
            basic_auth=(config["JIRA_EMAIL"], config["JIRA_TOKEN"]),
        )


class TestGetBoard:
    def test_is_decorated_correctly(self):
        assert get_board.is_decorated_with_spin_it

    def test_calls_jira_boards_and_wraps_the_result(self):
        board = Mock(raw={"location": {"displayName": "Foo"}})
        mock_jira = Mock(boards=Mock(return_value=[board]))

        result = get_board(mock_jira, sentinel.key)

        mock_jira.boards.assert_called_once_with(projectKeyOrID=sentinel.key)
        assert result.result == board
        assert "Foo" in result.stdout

    def test_raises_when_no_board_found(self):
        wrong_project_key = "foobar"
        mock_jira = Mock(
            boards=Mock(
                side_effect=JIRAError(text=f"No project with key {wrong_project_key!r}")
            )
        )
        with pytest.raises(Exception) as exc_info:
            get_board(mock_jira, wrong_project_key)

        assert "No project with key 'foobar'" in str(exc_info)

    def test_raises_when_more_than_one_board_found(self):
        ambiguous_key = "board"
        mock_jira = Mock(
            boards=Mock(
                return_value=[Mock(raw={"location": {"displayName": f"Foo{n}"}}) for n in (1, 2)]
            )
        )

        with pytest.raises(Exception) as exc_info:
            get_board(mock_jira, ambiguous_key)

        mock_jira.boards.assert_called_once_with(projectKeyOrID=ambiguous_key)
        assert f"Found more than one board matching {ambiguous_key!r}" in str(exc_info)
        assert f"Foo1, Foo2" in str(exc_info)


class TestGetSprints:
    def test_returns_sprints_found_by_jira_with_provided_board_and_state(self):
        mock_jira = Mock(sprints=Mock(return_value=[sentinel.sprint]))
        mock_board = Mock(id=1)

        result = _get_sprints(mock_jira, mock_board, sentinel.state)

        assert result == [sentinel.sprint]
        mock_jira.sprints.assert_called_once_with(board_id=1, state=sentinel.state)

    def test_raises_when_jira_could_not_find_sprints(self):
        mock_jira = Mock(sprints=Mock(return_value=[]))
        mock_board = Mock(id=1, name="ZZZ")

        with pytest.raises(Exception) as exc_info:
            _get_sprints(mock_jira, mock_board, "foo")

        assert f"could not find any sprints for board {mock_board.name!r}" in str(
            exc_info.value
        )


class TestGetSprint:
    def test_is_decorated_correctly(self):
        assert get_sprint.is_decorated_with_spin_it

    def test_finds_sprint_from_id(self, mocker):
        mock_get_sprint_from_id = mocker.patch("src.dzira.dzira._get_sprint_from_id")
        mock_get_first_sprint_matching_state = mocker.patch("src.dzira.dzira._get_first_sprint_matching_state")
        mock_process_sprint_out = mocker.patch("src.dzira.dzira.process_sprint_out", Mock(return_value=""))
        mock_payload = D(sprint_id=sentinel.sprint_id)

        get_sprint(sentinel.jira, mock_payload)

        mock_get_sprint_from_id.assert_called_once_with(sentinel.jira, **mock_payload)
        assert not mock_get_first_sprint_matching_state.called
        mock_process_sprint_out.assert_called_once_with(mock_get_sprint_from_id.return_value)

    def test_finds_sprint_using_state(self, mocker):
        mock_get_sprint_from_id = mocker.patch("src.dzira.dzira._get_sprint_from_id")
        mock_get_first_sprint_matching_state = mocker.patch("src.dzira.dzira._get_first_sprint_matching_state")
        mock_process_sprint_out = mocker.patch("src.dzira.dzira.process_sprint_out", Mock(return_value=""))
        mock_payload = D(state="foo")

        get_sprint(sentinel.jira, mock_payload)

        mock_get_first_sprint_matching_state.assert_called_once_with(sentinel.jira, **mock_payload)
        assert not mock_get_sprint_from_id.called
        mock_process_sprint_out.assert_called_once_with(mock_get_first_sprint_matching_state.return_value)

    def test_returns_result_class_instance(self, mocker):
        mocker.patch("src.dzira.dzira._get_sprint_from_id")
        mocker.patch("src.dzira.dzira._get_first_sprint_matching_state")
        mocker.patch("src.dzira.dzira.process_sprint_out", Mock(return_value=""))

        assert type(get_sprint(sentinel.jira, D())) == Result


class TestGetIssuesPublic:
    def test_is_decorated_correctly(self):
        assert get_issues.is_decorated_with_spin_it

    def test_calls_private_function_and_wraps_the_result(self, mocker):
        mock_private = mocker.patch("src.dzira.dzira._get_sprint_issues")

        result = get_issues(sentinel.jira, sentinel.sprint)

        mock_private.assert_called_once_with(sentinel.jira, sentinel.sprint)
        assert type(result) == Result
        assert result.result == mock_private.return_value


class TestAddWorklog:
    def test_calls_jira_add_worklog_with_provided_values(self):
        mock_worklog = Mock(raw={"timeSpent": "2h"}, issueId="123", id=321)
        mock_jira = Mock(add_worklog=Mock(return_value=mock_worklog))

        result1 = add_worklog(mock_jira, "333", time="2h", date=sentinel.date)
        result2 = add_worklog(mock_jira, "333", seconds=f"{60 * 60 * 2}", comment="blah!")

        assert mock_jira.add_worklog.call_args_list == (
            [
                call(
                    issue="333",
                    timeSpent="2h",
                    timeSpentSeconds=None,
                    comment=None,
                    started=sentinel.date,
                ),
                call(
                    issue="333",
                    timeSpent=None,
                    timeSpentSeconds="7200",
                    comment="blah!",
                    started=None,
                ),
            ]
        )
        assert "spent 2h in 333 [worklog 321]" in result1.stdout
        assert "spent 2h in 333 [worklog 321]" in result2.stdout


class TestGetWorklog:
    def test_returns_worklog_if_found_by_jira_with_given_specs(self):
        mock_jira = Mock(worklog=Mock())

        result = get_worklog(mock_jira, issue="123", worklog_id=999)

        assert result == mock_jira.worklog.return_value
        mock_jira.worklog.assert_called_once_with(issue="123", id="999")

    def test_raises_when_jira_could_not_find_worklog(self):
        mock_jira = Mock(worklog=Mock(return_value=None))

        with pytest.raises(Exception) as exc_info:
            get_worklog(mock_jira, issue="123", worklog_id="999")

        assert "could not find worklog 999 for issue '123'" in str(exc_info)


class TestUpdateWorklogPrivate:
    def test_updates_given_worklog_with_provided_fields(self):
        mock_worklog = Mock(update=Mock(), id="42")

        _update_worklog(mock_worklog, time="2h", comment="blah!", date=sentinel.date)

        mock_worklog.update.assert_called_once_with(
            fields={"timeSpent": "2h", "comment": "blah!", "started": sentinel.date}
        )

    def test_raises_when_no_time_nor_comment_fields_provided(self):
        mock_worklog = Mock(update=Mock())

        with pytest.raises(Exception) as exc_info:
            _update_worklog(mock_worklog, time=None, comment=None, date=None)

        assert "at least one of <time> or <comment> fields needed" in str(exc_info)
        mock_worklog.update.assert_not_called()


class TestUpdateWorklogPublic:
    def test_is_decorated_correctly(self):
        assert update_worklog.is_decorated_with_spin_it

    def test_calls_private_function_and_wraps_the_result(self, mocker):
        mock_worklog = Mock(id="42")
        mock_private = mocker.patch("src.dzira.dzira._update_worklog")

        result = update_worklog(mock_worklog, time="2h", comment="blah!", date=None)

        mock_private.assert_called_once_with(mock_worklog, "2h", "blah!", None)
        assert type(result) == Result
        assert "42" in result.stdout


class TestCalculateSeconds:
    def test_returns_the_unchanged_payload_if_no_start_time(self):
        input = D({"start": None, "end": None, "foo": "bar"})

        assert calculate_seconds(input) == input

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            ("8:59", "9:00", "60"),
            ("8:00", "8:59", f"{59 * 60}"),
            ("8:00", "18:00", f"{10 * 60 * 60}"),
        ],
    )
    def test_returns_seconds_delta_of_end_and_start(self, start, end, expected):
        assert calculate_seconds(D(start=start, end=end))["seconds"] == expected

    def test_returns_seconds_delta_of_start_and_now_when_end_is_none(self, mocker):
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        start = "8:00"
        fake_now = "8:07"
        mock_datetime.strptime.side_effect = [
            datetime.datetime.strptime(fake_now, "%H:%M"),
            datetime.datetime.strptime(start, "%H:%M")
        ]
        assert calculate_seconds(D(start=start, end=None))["seconds"] == str(7*60)

    def test_accepts_multiple_separators_in_input(self, mocker):
        mock_sub = mocker.patch("src.dzira.dzira.re.sub")
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_datetime.strptime.return_value.__gt__ = Mock(return_value=False)

        calculate_seconds(D(start="2,10", end="3.01"))

        mock_sub.assert_has_calls(
            [call("[,.h]", ":", "3.01"), call("[,.h]", ":", "2,10")]
        )
        assert mock_datetime.strptime.call_args_list == [
            call(mock_sub.return_value, "%H:%M"),
            call(mock_sub.return_value, "%H:%M"),
        ]

    def test_raises_when_end_time_prior_than_start_time(self, mocker):
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_datetime.strptime.return_value.__gt__ = Mock(return_value=True)

        with pytest.raises(click.BadParameter) as exc_info:
            calculate_seconds(D(start="18h00", end="8h00"))

        assert "start time cannot be later than end time" in str(exc_info.value)


class TestProcessSprintOut:
    def test_shows_info_about_sprint(self):
        mock_sprint = Mock(
            name="Foo",
            id=123,
            startDate="2023-10-23T8:10:00.123Z",
            endDate="2023-11-23T8:10:00.123Z"
        )

        result = process_sprint_out(mock_sprint)

        for str in ("Foo", "id: 123", "Mon, Oct 23", "Thu, Nov 23"):
            assert str in result


class TestGetSprintAndIssues:
    def test_gets_sprint_and_issues_using_sprint_id(self, mocker):
        mock_get_board = mocker.patch("src.dzira.dzira.get_board")
        mock_get_sprint = mocker.patch("src.dzira.dzira.get_sprint")
        mock_get_issues = mocker.patch("src.dzira.dzira.get_issues")
        mock_payload = D(sprint_id="foo")

        result = get_sprint_and_issues(sentinel.jira, mock_payload)

        mock_get_sprint.assert_called_once_with(sentinel.jira, mock_payload)
        mock_get_issues.assert_called_once_with(sentinel.jira, mock_get_sprint.return_value.result)
        assert not mock_get_board.called
        assert result == mock_get_issues.return_value.result

    def test_gets_sprint_and_issues_using_board(self, mocker):
        mock_get_board = mocker.patch("src.dzira.dzira.get_board")
        mock_get_sprint = mocker.patch("src.dzira.dzira.get_sprint")
        mock_get_issues = mocker.patch("src.dzira.dzira.get_issues")
        mock_payload = D(JIRA_PROJECT_KEY=sentinel.key)

        result = get_sprint_and_issues(sentinel.jira, mock_payload)

        mock_get_sprint.assert_called_once_with(
            sentinel.jira, mock_payload.update("board", mock_get_board.return_value.result)
        )
        mock_get_issues.assert_called_once_with(sentinel.jira, mock_get_sprint.return_value.result)
        mock_get_board.assert_called_once_with(sentinel.jira, sentinel.key)
        assert result == mock_get_issues.return_value.result


runner = CliRunner()


class TestCli:
    def test_help(self):
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Configure JIRA connection" in result.output


class TestLs:
    def test_help(self):
        result = runner.invoke(ls, ["--help"])

        assert result.exit_code == 0
        assert "List issues from the current sprint" in result.output

    def test_happy_run(self, mocker):
        mock_config = {}
        mocker.patch("src.dzira.dzira.get_config", return_value=mock_config)
        mocker.patch("src.dzira.dzira.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
        mock_get_sprint_and_issues = mocker.patch(
            "src.dzira.dzira.get_sprint_and_issues", Mock(return_value=sentinel.issues)
        )
        mock_show_issues = mocker.patch("src.dzira.dzira.show_issues")

        result = runner.invoke(cli, ["--token", "foo", "ls"])

        assert result.exit_code == 0
        mock_show_issues.assert_called_once_with(sentinel.issues)
        mock_get_sprint_and_issues.assert_called_once_with(
            sentinel.jira, D(state="active", sprint_id=None, **mock_config)
        )

    @patch.dict(os.environ, {"JIRA_PROJECT_KEY": "XYZ"}, clear=True)
    @patch("src.dzira.dzira.get_sprint_and_issues")
    def test_has_access_to_context_provided_by_cli_group(self, mock_get_sprint_and_issues, mocker):
        mock_config = {"JIRA_PROJECT_KEY": "XYZ", "JIRA_EMAIL": "foo@bar.com"}
        mock_get_config = mocker.patch("src.dzira.dzira.get_config")
        mocker.patch("src.dzira.dzira.get_jira", Mock(return_value=Mock(result=sentinel.jira)))

        runner.invoke(cli, ["--email", "foo@bar.com", "ls"])

        mock_get_sprint_and_issues.assert_called_once_with(
            sentinel.jira, D(state="active", sprint_id=None, **mock_get_config.return_value)
        )
        mock_get_config.assert_called_once_with(config=mock_config)

    def test_uses_state_option(self, mocker):
        mock_get_config = mocker.patch("src.dzira.dzira.get_config")
        mocker.patch("src.dzira.dzira.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
        mock_get_sprint_and_issues = mocker.patch(
            "src.dzira.dzira.get_sprint_and_issues"
        )
        mock_get_sprint_and_issues.return_value = sentinel.issues
        mock_show_issues = mocker.patch("src.dzira.dzira.show_issues")

        result = runner.invoke(cli, ["ls", "--state", "closed"])

        assert result.exit_code == 0
        mock_show_issues.assert_called_once_with(sentinel.issues)
        mock_get_sprint_and_issues.assert_called_once_with(
            sentinel.jira, D(state="closed", sprint_id=None, **mock_get_config.return_value)
        )

    def test_uses_sprint_id_option(self, mocker):
        mock_get_config = mocker.patch("src.dzira.dzira.get_config")
        mocker.patch("src.dzira.dzira.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
        mock_get_sprint_and_issues = mocker.patch(
            "src.dzira.dzira.get_sprint_and_issues"
        )
        mock_get_sprint_and_issues.return_value = sentinel.issues
        mock_show_issues = mocker.patch("src.dzira.dzira.show_issues")

        result = runner.invoke(cli, ["ls", "--sprint-id", "42"])

        assert result.exit_code == 0
        mock_show_issues.assert_called_once_with(sentinel.issues)
        mock_get_sprint_and_issues.assert_called_once_with(
            sentinel.jira, D(state="active", sprint_id=42, **mock_get_config.return_value)
        )


class TestCorrectTimeFormats:
    @pytest.mark.parametrize(
        "input, expected",
        [
            ("1h 1m", D(h="1h", m="1m")),
            ("1h1m", D(h="1h", m="1m")),
            ("1h 59m", D(h="1h", m="59m")),
            ("1h59m", D(h="1h", m="59m")),
            ("1h 0m", D()),
            ("1h 60m", D()),
            ("23h 1m", D(h="23h", m="1m")),
            ("23h1m", D(h="23h", m="1m")),
            ("24h 1m", D()),
            ("0h 1m", D()),
            ("2h", D(h="2h", m=None)),
            ("42m", D(h=None, m="42m")),
        ],
    )
    def test_evaluates_time_format(self, input, expected):
        assert expected == matches_time_re(input)

    @pytest.mark.parametrize(
        "input, expected",
        [
            ("0:0", True),
            ("0:59", True),
            ("0:60", False),
            ("25:0", False),
            ("23:1", True),
            ("10,10", True),
            ("10.10", True),
            ("10h10", True),
            ("12", False),
        ],
    )
    def test_evaluates_hour_time_format(self, input, expected):
        assert expected == is_valid_hour(input)


@patch("src.dzira.dzira.matches_time_re")
class TestValidateTime:
    def test_passes_when_time_is_none(self, mock_matches_time_re):
        result = validate_time(Mock(), Mock(), None)

        assert result is None
        mock_matches_time_re.assert_not_called()

    def test_passes_when_validator_passes(self, mock_matches_time_re):
        mock_matches_time_re.return_value = D(h="2h")

        result = validate_time(Mock(), Mock(), "2h")

        assert result == "2h"
        mock_matches_time_re.assert_called_with("2h")

    def test_raises_otherwise(self, mock_matches_time_re):
        mock_matches_time_re.return_value = False

        with pytest.raises(click.BadParameter) as exc_info:
            validate_time(Mock(), Mock(), "invalid")

        mock_matches_time_re.assert_called_with("invalid")
        assert "time has" in str(exc_info)


@patch("src.dzira.dzira.is_valid_hour")
class TestValidateHour:
    def test_raises_when_end_hour_without_start_hour_or_time_spent(
        self, mock_is_valid_hour
    ):
        mock_ctx = Mock(params={})
        mock_param = Mock()
        type(mock_param).name = PropertyMock(return_value="end")
        with pytest.raises(click.BadParameter) as exc_info:
            validate_hour(mock_ctx, mock_param, "invalid")

        assert "start time required to process end time" in str(exc_info)
        mock_is_valid_hour.assert_not_called()

    def test_passes_when_time_is_none_and_first_check_passed(self, mock_is_valid_hour):
        mock_param = Mock()
        type(mock_param).name = PropertyMock(return_value="start")

        result = validate_hour(Mock(), mock_param, None)

        assert result is None
        mock_is_valid_hour.assert_not_called()

    def test_passes_when_validator_passes_and_returns_unified_value(self, mock_is_valid_hour):
        mock_ctx = Mock(params={"start": "16h42"})
        mock_param = Mock()
        type(mock_param).name = PropertyMock(return_value="end")
        mock_is_valid_hour.return_value = True

        result = validate_hour(mock_ctx, mock_param, "17h23")

        assert result == "17:23"
        mock_is_valid_hour.assert_called_once_with("17h23")

    def test_raises_otherwise(self, mock_is_valid_hour):
        mock_ctx = Mock(params={})
        mock_param = Mock()
        type(mock_param).name = PropertyMock(return_value="start")
        mock_is_valid_hour.return_value = False

        with pytest.raises(click.BadParameter) as exc_info:
            validate_hour(mock_ctx, mock_param, "invalid")

        assert (
            "start/end time has to be in format '[H[H]][:.h,][M[M]]', e.g. '2h3', '12:03', '3,59'"
            in str(exc_info)
        )
        mock_is_valid_hour.assert_called_once_with("invalid")


class TestValidateDate:
    def test_returns_early_when_date_is_none(self):
        assert validate_date(Mock(), Mock(), None) is None

    def test_uses_start_time_when_not_provided_in_date_option(self, mocker):
        mock_ctx = Mock(params={"start": "13:42"})
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_isinstance = mocker.patch("src.dzira.dzira.isinstance")
        mocker.patch("src.dzira.dzira.VALIDATE_DATE_FORMATS", ["%Y-%m-%d %H:%M"])
        mock_isinstance.return_value = True
        mock_datetime.strptime.return_value = datetime.datetime(2023, 11, 23, 13, 42)
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)
        mock_datetime.utcnow.return_value\
            .astimezone.return_value\
            .utcoffset.return_value = None

        result = validate_date(mock_ctx, Mock(), "2023-11-23")

        assert result == datetime.datetime(2023, 11, 23, 13, 42)
        mock_datetime.strptime.assert_called_once_with("2023-11-23 13:42", "%Y-%m-%d %H:%M")

    def test_validates_against_multiple_formats_and_raises_when_none_matches(self, mocker):
        mocker.patch("src.dzira.dzira.isinstance", Mock(return_value=False))
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_datetime.strptime.side_effect = 3 * [ValueError]

        with pytest.raises(click.BadParameter) as exc_info:
            validate_date(Mock(), Mock(), "foo")

        assert "date has to match one of supported ISO formats" in str(exc_info)
        assert ", ".join(VALIDATE_DATE_FORMATS) in str(exc_info)
        for fmt in VALIDATE_DATE_FORMATS:
            mock_datetime.strptime.assert_has_calls([call("foo", fmt)])

    def test_raises_when_date_in_future(self, mocker):
        mocker.patch("src.dzira.dzira.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_datetime.strptime.return_value = datetime.datetime(2055, 11, 23, 13, 42)
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)

        with pytest.raises(click.BadParameter) as exc_info:
            validate_date(Mock(), Mock(), "2055-11-23T13:42")

        assert "worklog date cannot be in future" in str(exc_info)

    def test_raises_when_date_older_than_2_weeks(self, mocker):
        mocker.patch("src.dzira.dzira.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_datetime.strptime.return_value = datetime.datetime(1055, 11, 23, 13, 42)
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)

        with pytest.raises(click.BadParameter) as exc_info:
            validate_date(Mock(), Mock(), "1055-11-23T13:42")

        assert "worklog date cannot be older than 2 weeks" in str(exc_info)

    def test_tries_to_convert_date_to_timezone_aware(self, mocker):
        mocker.patch("src.dzira.dzira.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("src.dzira.dzira.datetime")
        mock_datetime.strptime.return_value = datetime.datetime(2023, 11, 23, 13, 42)
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)
        mock_datetime.utcnow.return_value\
            .astimezone.return_value\
            .utcoffset.return_value = datetime.timedelta(seconds=3600)

        result = validate_date(Mock(), Mock(), "2023-11-23T13:42")

        assert result == datetime.datetime(2023, 11, 23, 12, 42)


class TestSanitizeParams:
    def test_raises_when_no_time_and_missing_comment(self):
        with pytest.raises(click.UsageError) as exc_info:
            sanitize_params(D(worklog_id=999))

        assert "to update a worklog, either time spent or a comment is needed" in str(exc_info)

    def test_raises_when_no_time_or_start(self):
        with pytest.raises(click.UsageError) as exc_info:
            sanitize_params(D())

        assert "cannot spend without knowing working time or when work has started" in str(exc_info)

    @pytest.mark.parametrize(
        "args", [D(time="42m"), D(start="8:30"), D(worklog_id="999", comment="asdf")]
    )
    def test_updates_seconds_when_proper_args_provided(self, mocker, args):
        mock_calculate_seconds = mocker.patch("src.dzira.dzira.calculate_seconds")

        result = sanitize_params(args)

        mock_calculate_seconds.assert_called_once_with(args)
        assert result == mock_calculate_seconds.return_value


@patch("src.dzira.dzira.get_sprint_and_issues")
class TestEstablishIssue:
    config = {"JIRA_PROJECT_KEY": "XYZ"}

    def test_returns_early_if_issue_is_digits_and_key_provided(
            self, mock_get_sprint_and_issues,
    ):
        result = establish_issue(Mock(), D(issue="123", **self.config))

        assert result == D(issue="XYZ-123", **self.config)
        mock_get_sprint_and_issues.assert_not_called()

    def test_returns_early_if_issue_is_digits_and_board_not_provided(
            self, mock_get_sprint_and_issues,
    ):
        result = establish_issue(Mock(), D(issue="123", **self.config))

        assert result == D(issue="XYZ-123", **self.config)
        mock_get_sprint_and_issues.assert_not_called()

    def test_raises_when_no_matching_issue_in_current_sprint(
            self, mock_get_sprint_issues
    ):
        mock_get_sprint_issues.return_value = []

        with pytest.raises(Exception) as exc_info:
            establish_issue(Mock(), D(issue="some description", **self.config))

        assert "could not find any matching issues" in str(exc_info)

    def test_raises_when_more_than_one_matching_issue_in_current_sprint(
            self, mock_get_sprint_and_issues
    ):
        mock_get_sprint_and_issues.return_value = [
            Mock(key="1", fields=Mock(summary="I have some description")),
            Mock(key="2", fields=Mock(summary="Need some description")),
        ]

        with pytest.raises(Exception) as exc_info:
            establish_issue(Mock(), D(issue="some description", **self.config))

        assert "found more than one matching issue" in str(exc_info)

    def test_returns_updated_payload_with_issue_key_when_issue_found_in_the_sprint(
            self, mock_get_sprint_and_issues,
    ):
        mock_get_sprint_and_issues.return_value = [
            Mock(key="1", fields=Mock(summary="I have some description")),
            Mock(key="2", fields=Mock(summary="I don't have any matching phrases")),
        ]

        result = establish_issue(Mock(), D(issue="some description").update(**self.config))

        assert result == D(issue="1", **self.config)


class TestLogAction:
    def test_returns_update_worklog_if_worklog_id_provided(self, mocker):
        mock_get_worklog = mocker.patch("src.dzira.dzira.get_worklog")
        mock_update_worklog = mocker.patch("src.dzira.dzira.update_worklog")
        payload = D(issue=sentinel.issue, worklog_id=sentinel.worklog)

        perform_log_action(sentinel.jira, payload)

        mock_get_worklog.assert_called_once_with(
            sentinel.jira, issue=sentinel.issue, worklog_id=sentinel.worklog
        )
        mock_update_worklog.assert_called_once_with(
            mock_get_worklog.return_value,
            **payload
        )

    def test_returns_add_worklog_if_worklog_id_not_provided(self, mocker):
        mock_get_worklog = mocker.patch("src.dzira.dzira.get_worklog")
        mock_add_worklog = mocker.patch("src.dzira.dzira.add_worklog")
        payload = D(issue=sentinel.issue, worklog_id=None)

        perform_log_action(sentinel.jira, payload)

        mock_get_worklog.assert_not_called()
        mock_add_worklog.assert_called_once_with(sentinel.jira, **payload)


class TestLog:
    def test_help(self):
        result = runner.invoke(log, ["--help"])

        assert "Log time spent" in result.output

    def test_runs_stuff_in_order(self, mocker):
        mocker.patch.dict(
            os.environ, {"JIRA_TOKEN": "token", "JIRA_EMAIL": "email"}, clear=True
        )
        mock_sanitize_params = mocker.patch("src.dzira.dzira.sanitize_params")
        mock_get_config = mocker.patch("src.dzira.dzira.get_config")
        mock_get_jira = mocker.patch("src.dzira.dzira.get_jira")
        mock_establish_issue = mocker.patch("src.dzira.dzira.establish_issue")
        mock_perform_log_action = mocker.patch("src.dzira.dzira.perform_log_action")

        mock_jira = mock_get_jira.return_value.result
        mock_config = mock_get_config.return_value

        result = runner.invoke(cli, ["log", "123", "-t", "2h"])

        assert result.exit_code == 0
        mock_sanitize_params.assert_called_once()
        mock_get_config.assert_called_once_with(
            config=dict(JIRA_TOKEN="token", JIRA_EMAIL="email"),
        )
        mock_get_jira.assert_called_once_with(mock_config)
        mock_establish_issue.assert_called_once_with(
            mock_jira, mock_sanitize_params.return_value.update.return_value
        )
        mock_sanitize_params.return_value.update.assert_called_once_with(
            **mock_get_config.return_value
        )
        mock_perform_log_action.assert_called_once_with(
            mock_jira, mock_establish_issue.return_value
        )


class TestMain:
    def test_runs_cli(self, mocker):
        mock_cli = mocker.patch("src.dzira.dzira.cli")

        main()

        mock_cli.assert_called_once()

    def test_catches_exceptions_and_exits(self, mocker):
        mocker.patch("src.dzira.dzira.hide_cursor")
        mocker.patch("src.dzira.dzira.show_cursor")
        mock_cli = mocker.patch("src.dzira.dzira.cli")
        exc = Exception("foo")
        mock_cli.side_effect = exc
        mock_print = mocker.patch("src.dzira.dzira.print")
        mock_exit = mocker.patch("src.dzira.dzira.sys.exit")

        main()

        mock_print.assert_called_once_with(exc, file=sys.stderr)
        mock_exit.assert_called_once_with(1)

    def test_hides_and_shows_the_cursor(self, mocker):
        mocker.patch("src.dzira.dzira.cli")
        mock_hide = mocker.patch("src.dzira.dzira.hide_cursor")
        mock_show = mocker.patch("src.dzira.dzira.show_cursor")

        main()

        mock_hide.assert_called_once()
        mock_show.assert_called_once()
