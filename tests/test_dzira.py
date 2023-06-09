import os
import pathlib
import sys
from unittest.mock import Mock, PropertyMock, call, patch, sentinel

import pytest
import click
from click.testing import CliRunner

from dzira.dzira import (
    CONFIG_DIR_NAME,
    DOTFILE,
    add_worklog,
    calculate_seconds,
    cli,
    establish_action,
    establish_issue,
    get_board_by_name,
    get_board_name,
    get_config,
    get_config_from_file,
    get_current_sprint,
    get_current_sprint_with_issues,
    get_jira,
    get_sprint_issues,
    get_sprints,
    get_worklog,
    is_valid_hour,
    is_valid_time,
    log,
    ls,
    main,
    prepare_payload,
    update_worklog,
    validate_hour,
    validate_time,
)


@pytest.fixture
def config(mocker):
    mock_dotenv_values = mocker.patch("dzira.dzira.dotenv_values")
    mock_dotenv_values.return_value = {
        "JIRA_SERVER": "foo.bar.com",
        "JIRA_EMAIL": "name@example.com",
        "JIRA_TOKEN": "asdf1234",
        "JIRA_BOARD": "XYZ",
    }
    return mock_dotenv_values


class TestGetConfigFromFile:
    def test_looks_for_config_file_in_default_locations_when_path_not_provided(
        self, mocker, config
    ):
        mocker.patch.dict(os.environ, {"HOME": "/home/foo"}, clear=True)
        mock_env_get = mocker.patch("dzira.dzira.os.environ.get")
        mock_path = mocker.patch("dzira.dzira.Path")

        get_config_from_file()

        mock_env_get.assert_called_once_with("XDG_CONFIG_HOME", "/home/foo")
        mock_path.assert_called_once_with(mock_env_get.return_value)
        assert mock_path.return_value.__truediv__.call_args_list == [
            call(CONFIG_DIR_NAME),
            call(DOTFILE),
        ]
        assert mock_path.is_file.call_args_list == []

    def test_looks_for_config_file_in_provided_location(self, config):
        mock_dotenv_values = config

        get_config_from_file(sentinel.path)

        mock_dotenv_values.assert_called_once_with(sentinel.path)

    def test_returns_empty_dict_when_no_file_found(self, mocker):
        mocker.patch.object(pathlib.Path, "is_file", lambda _: False)

        result = get_config_from_file()

        assert result == {}


@patch("dzira.dzira.REQUIRED_KEYS", ("FOO", "BAR", "BAZ"))
@patch("dzira.dzira.get_config_from_file")
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
        cfg = config()
        mock_get_jira = mocker.patch("dzira.dzira.JIRA")

        get_jira(cfg)

        mock_get_jira.assert_called_once_with(
            server=f"https://{cfg['JIRA_SERVER']}",
            basic_auth=(cfg["JIRA_EMAIL"], cfg["JIRA_TOKEN"]),
        )


class TestGetBoardName:
    def test_returns_value_from_config(self):
        assert get_board_name({"JIRA_BOARD": "XYZ"}) == "XYZ board"


class TestGetBoardByName:
    def test_returns_first_board_got_from_jira(self):
        mock_jira = Mock(boards=Mock(return_value=[sentinel.one, sentinel.two]))

        result = get_board_by_name(mock_jira, sentinel.name)

        assert result == sentinel.one
        mock_jira.boards.assert_called_once_with(name=sentinel.name)

    def test_raises_when_jira_could_not_find_any_board(self):
        mock_jira = Mock(boards=Mock(return_value=[]))

        with pytest.raises(Exception) as exc_info:
            get_board_by_name(mock_jira, "XYZ")

        assert str(exc_info.value) == "could not find any board matching 'XYZ'"


class TestGetSprints:
    def test_returns_sprints_found_by_jira_with_provided_board_and_state(self):
        mock_jira = Mock(sprints=Mock(return_value=[sentinel.sprint]))
        mock_board = Mock(id=1)

        result = get_sprints(mock_jira, mock_board, sentinel.state)

        assert result == [sentinel.sprint]
        mock_jira.sprints.assert_called_once_with(board_id=1, state=sentinel.state)

    def test_returns_sprints_found_by_jira_with_provided_board_and_default_active(self):
        mock_jira = Mock(sprints=Mock(return_value=[sentinel.sprint]))
        mock_board = Mock(id=1)

        result = get_sprints(mock_jira, mock_board)

        assert result == [sentinel.sprint]
        mock_jira.sprints.assert_called_once_with(board_id=1, state="active")

    def test_raises_when_jira_could_not_find_sprints(self):
        mock_jira = Mock(sprints=Mock(return_value=[]))
        mock_board = Mock(id=1, name="ZZZ")

        with pytest.raises(Exception) as exc_info:
            get_sprints(mock_jira, mock_board, "foo")

        assert f"could not find any sprints for board {mock_board.name!r}" in str(
            exc_info.value
        )


class TestGetCurrentSprint:
    def test_returns_first_element_of_the_list_found_by_get_sprints(self, mocker):
        mock_jira = Mock()
        mock_board = Mock()
        mock_get_sprints = mocker.patch("dzira.dzira.get_sprints")
        mock_get_sprints.return_value = [sentinel.sprint1, sentinel.sprint2]

        result = get_current_sprint(mock_jira, mock_board)

        assert result == sentinel.sprint1
        mock_get_sprints.assert_called_once_with(mock_jira, mock_board)


class TestGetSprintIssues:
    def test_returns_list_of_issues(self):
        mock_jira = Mock(search_issues=Mock(return_value=(sentinel.issue,)))
        mock_sprint = Mock(name="foo")

        result = get_sprint_issues(mock_jira, mock_sprint)

        assert result == [sentinel.issue]
        mock_jira.search_issues.assert_called_once_with(
            jql_str=f"Sprint = {mock_sprint.name!r}"
        )

    def test_raises_when_jira_could_not_find_matching_issues(self):
        mock_jira = Mock(search_issues=Mock(return_value=tuple()))
        mock_sprint = Mock(name="foo")

        with pytest.raises(Exception) as exc_info:
            get_sprint_issues(mock_jira, mock_sprint)

        assert f"could not find any issues for sprint {mock_sprint.name!r}" in str(
            exc_info.value
        )


class TestAddWorklog:
    def test_calls_jira_add_worklog_with_provided_values(self, mocker):
        mock_worklog = Mock(raw={"timeSpent": "2h"}, issueId="123", id=321)
        mock_jira = Mock(add_worklog=Mock(return_value=mock_worklog))
        mock_print = mocker.patch("dzira.dzira.print")

        add_worklog(mock_jira, "333", time="2h")
        add_worklog(mock_jira, "333", seconds=f"{60 * 60 * 2}", comment="blah!")

        assert mock_jira.add_worklog.has_calls(
            [
                call(issue="333", timeSpent="2h", timeSpentSeconds=None, comment=None),
                call(
                    issue="333",
                    timeSpent=None,
                    timeSpentSeconds="7200",
                    comment="blah!",
                ),
            ]
        )

        assert mock_print.has_calls(
            [
                call("Spent 2h in 333 (123) [worklog 321]"),
                call("Spent 2h in 333 (123) [worklog 321]"),
            ]
        )


class TestGetWorklog:
    def test_returns_worklog_if_found_by_jira_with_given_specs(self):
        mock_jira = Mock(worklog=Mock())

        result = get_worklog(mock_jira, "123", 999)

        assert result == mock_jira.worklog.return_value
        mock_jira.worklog.assert_called_once_with(issue="123", id="999")

    def test_raises_when_jira_could_not_find_worklog(self):
        mock_jira = Mock(worklog=Mock(return_value=None))

        with pytest.raises(Exception) as exc_info:
            get_worklog(mock_jira, "123", "999")

        assert "could not find worklog 999 for issue '123'" in str(exc_info)


class TestUpdateWorklog:
    def test_updates_given_worklog_with_provided_fields(self):
        mock_worklog = Mock(update=Mock())

        update_worklog(mock_worklog, time="2h", comment="blah!")

        mock_worklog.update.assert_called_once_with(
            fields={"timeSpent": "2h", "comment": "blah!"}
        )

    def test_raises_when_no_fields_provided(self):
        mock_worklog = Mock(update=Mock())

        with pytest.raises(Exception) as exc_info:
            update_worklog(mock_worklog)

        assert "at least one of <time> or <comment> fields needed" in str(exc_info)
        mock_worklog.update.assert_not_called()


class TestCalculateSeconds:
    def test_uses_current_time_if_only_start_parameter_provided(self, mocker):
        mock_datetime = mocker.patch("dzira.dzira.datetime")
        mock_datetime.strptime.return_value.__gt__ = Mock(return_value=False)

        calculate_seconds(start="9.00")

        mock_datetime.now.assert_called()
        mock_datetime.strptime.return_value.__gt__.assert_called_once_with(
            mock_datetime.now.return_value
        )

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            ("8:59", "9:00", "60"),
            ("8:00", "8:59", f"{59 * 60}"),
            ("8:00", "18:00", f"{10 * 60 * 60}"),
        ],
    )
    def test_returns_seconds_delta_of_end_and_start(self, start, end, expected):
        assert calculate_seconds(start, end) == expected

    def test_accepts_multiple_separators_in_input(self, mocker):
        mock_sub = mocker.patch("dzira.dzira.re.sub")
        mock_datetime = mocker.patch("dzira.dzira.datetime")
        mock_datetime.strptime.return_value.__gt__ = Mock(return_value=False)

        calculate_seconds("2,10", "3.01")

        mock_sub.assert_has_calls(
            [call("[,.h]", ":", "3.01"), call("[,.h]", ":", "2,10")]
        )
        assert mock_datetime.strptime.call_args_list == [
            call(mock_sub.return_value, "%H:%M"),
            call(mock_sub.return_value, "%H:%M"),
        ]

    def test_raises_when_end_time_prior_than_start_time(self, mocker):
        mock_datetime = mocker.patch("dzira.dzira.datetime")
        mock_datetime.strptime.return_value.__gt__ = Mock(return_value=True)

        with pytest.raises(click.BadParameter) as exc_info:
            calculate_seconds("18h00", "8h00")

        assert "start time cannot be later than end time" in str(exc_info.value)


class TestGetCurrentSprintWithIssues:
    def test_runs_with_config_from_file_by_default(self, mocker):
        mock_get_config = mocker.patch("dzira.dzira.get_config")
        mock_config = mock_get_config.return_value
        mock_get_jira = mocker.patch("dzira.dzira.get_jira")
        mock_get_board_name = mocker.patch("dzira.dzira.get_board_name")
        mock_get_board_by_name = mocker.patch("dzira.dzira.get_board_by_name")
        mock_get_current_sprint = mocker.patch("dzira.dzira.get_current_sprint")
        mock_get_sprint_issues = mocker.patch("dzira.dzira.get_sprint_issues")
        jira = mock_get_jira.return_value
        board = mock_get_board_by_name.return_value
        sprint = mock_get_current_sprint.return_value

        (
            expected_sprint,
            expected_issues,
            expected_board,
        ) = get_current_sprint_with_issues({})

        assert expected_sprint == sprint
        assert expected_issues == mock_get_sprint_issues.return_value
        assert expected_board == board
        mock_get_config.assert_called_once()
        mock_get_jira.assert_called_once_with(mock_config)
        mock_get_board_name.assert_called_once_with(mock_config)
        mock_get_board_by_name.assert_called_once_with(
            jira, mock_get_board_name.return_value
        )
        mock_get_current_sprint.assert_called_once_with(jira, board)
        mock_get_sprint_issues.assert_called_once_with(jira, sprint)


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
        mock_get_current_sprint_with_issues = mocker.patch(
            "dzira.dzira.get_current_sprint_with_issues"
        )
        mock_get_current_sprint_with_issues.return_value = (
            sentinel.sprint,
            sentinel.issues,
            sentinel.board,
        )
        mock_show_sprint_info = mocker.patch("dzira.dzira.show_sprint_info")
        mock_show_issues = mocker.patch("dzira.dzira.show_issues")

        result = runner.invoke(cli, ["--token", "foo", "ls"])

        assert result.exit_code == 0
        mock_show_issues.assert_called_once_with(sentinel.issues)
        mock_show_sprint_info.assert_called_once_with(sentinel.sprint, sentinel.board)
        mock_get_current_sprint_with_issues.assert_called_once_with(
            {"JIRA_TOKEN": "foo"}
        )

    @patch.dict(os.environ, {"JIRA_BOARD": "XYZ"}, clear=True)
    @patch("dzira.dzira.get_current_sprint_with_issues")
    def test_has_access_to_context_provided_by_cli_group(self, mock_get_current_sprint_with_issues):
        runner.invoke(cli, ["--email", "foo@bar.com", "ls"])

        mock_get_current_sprint_with_issues.assert_called_once_with(
            {"JIRA_BOARD": "XYZ", "JIRA_EMAIL": "foo@bar.com"}
        )


class TestCorrectTimeFormats:
    @pytest.mark.parametrize(
        "input, expected",
        [
            ("1h 1m", True),
            ("1h 59m", True),
            ("1h 0m", False),
            ("1h 60m", False),
            ("23h 1m", True),
            ("24h 1m", False),
            ("0h 1m", False),
            ("2h", True),
            ("42m", True),
        ],
    )
    def test_evaluates_time_format(self, input, expected):
        assert expected == is_valid_time(input)

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


@patch("dzira.dzira.is_valid_time")
class TestValidateTime:
    def test_passes_when_time_is_none(self, mock_is_valid_time):
        result = validate_time(Mock(), Mock(), None)

        assert result is None
        mock_is_valid_time.assert_not_called()

    def test_passes_when_validator_passes(self, mock_is_valid_time):
        mock_is_valid_time.return_value = True

        result = validate_time(Mock(), Mock(), "2h")

        assert result == "2h"
        mock_is_valid_time.assert_called_with("2h")

    def test_raises_otherwise(self, mock_is_valid_time):
        mock_is_valid_time.return_value = False

        with pytest.raises(click.BadParameter) as exc_info:
            validate_time(Mock(), Mock(), "invalid")

        mock_is_valid_time.assert_called_with("invalid")
        assert "time has" in str(exc_info)


@patch("dzira.dzira.is_valid_hour")
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

    def test_passes_when_validator_passes(self, mock_is_valid_hour):
        mock_ctx = Mock(params={"start": "16h42"})
        mock_param = Mock()
        type(mock_param).name = PropertyMock(return_value="end")
        mock_is_valid_hour.return_value = True

        result = validate_hour(mock_ctx, mock_param, "17h23")

        assert result == "17h23"
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


class TestPreparePaload:
    def test_uses_time_and_comment_if_provided(self, mocker):
        mock_calculate_seconds = mocker.patch("dzira.dzira.calculate_seconds")
        result = prepare_payload("2h", sentinel.start, sentinel.end, sentinel.comment)

        assert result == dict(time="2h", comment=sentinel.comment)
        mock_calculate_seconds.assert_not_called()

    def test_uses_time_and_start_end_when_time_not_provided(self, mocker):
        mock_calculate_seconds = mocker.patch("dzira.dzira.calculate_seconds")
        result = prepare_payload(None, sentinel.start, sentinel.end, sentinel.comment)

        assert result == dict(
            seconds=mock_calculate_seconds.return_value, comment=sentinel.comment
        )
        mock_calculate_seconds.assert_called_once_with(
            start=sentinel.start, end=sentinel.end
        )


@patch("dzira.dzira.get_sprint_issues")
@patch("dzira.dzira.get_current_sprint")
@patch("dzira.dzira.get_board_by_name")
@patch("dzira.dzira.get_board_name")
class TestEstablishIssue:
    def test_returns_early_if_issue_is_digits_and_board_provided(
        self,
        mock_get_board_name,
        mock_get_board_by_name,
        mock_get_current_sprint,
        mock_get_sprint_issues,
    ):
        result = establish_issue(Mock(), {"JIRA_BOARD": "XYZ"}, "123")

        assert result == "XYZ-123"
        mock_get_board_name.assert_not_called()
        mock_get_board_by_name.assert_not_called()
        mock_get_current_sprint.assert_not_called()
        mock_get_sprint_issues.assert_not_called()

    def test_returns_early_if_issue_is_digits_and_board_not_provided(
        self,
        mock_get_board_name,
        mock_get_board_by_name,
        mock_get_current_sprint,
        mock_get_sprint_issues,
    ):
        result = establish_issue(Mock(), {"JIRA_BOARD": "XYZ"}, "123")

        assert result == "XYZ-123"
        mock_get_board_name.assert_not_called()
        mock_get_board_by_name.assert_not_called()
        mock_get_current_sprint.assert_not_called()
        mock_get_sprint_issues.assert_not_called()

    def test_raises_when_no_matching_issue_in_current_sprint(
        self, _, __, ___, mock_get_sprint_issues
    ):
        mock_get_sprint_issues.return_value = []

        with pytest.raises(Exception) as exc_info:
            establish_issue(Mock(), {}, "some description")

        assert "could not find any matching issues" in str(exc_info)

    def test_raises_when_more_than_one_matching_issue_in_current_sprint(
        self, _, __, ___, mock_get_sprint_issues
    ):
        mock_get_sprint_issues.return_value = [
            Mock(key="1", fields=Mock(summary="I have some description")),
            Mock(key="2", fields=Mock(summary="Need some description")),
        ]

        with pytest.raises(Exception) as exc_info:
            establish_issue(Mock(), {}, "some description")

        assert "found more than one matching issue" in str(exc_info)

    def test_returns_issue_key_when_found_in_sprint(
        self,
        _,
        __,
        ___,
        mock_get_sprint_issues,
    ):
        mock_get_sprint_issues.return_value = [
            Mock(key="1", fields=Mock(summary="I have some description")),
            Mock(key="2", fields=Mock(summary="I don't have any matching phrases")),
        ]

        result = establish_issue(Mock(), {}, "some description")

        assert result == "1"


class TestEstablishAction:
    def test_returns_update_worklog_if_worklog_id_provided(self, mocker):
        mock_get_worklog = mocker.patch("dzira.dzira.get_worklog")
        mock_partial = mocker.patch("dzira.dzira.partial")

        result = establish_action(
            sentinel.jira, {"issue": sentinel.issue}, sentinel.worklog
        )

        assert result == mock_partial.return_value
        mock_partial.assert_called_once_with(
            update_worklog, mock_get_worklog.return_value
        )
        mock_get_worklog.assert_called_once_with(
            sentinel.jira, sentinel.issue, sentinel.worklog
        )

    def test_returns_add_worklog_if_worklog_id_not_provided(self, mocker):
        mock_get_worklog = mocker.patch("dzira.dzira.get_worklog")
        mock_partial = mocker.patch("dzira.dzira.partial")

        result = establish_action(sentinel.jira, {"issue": sentinel.issue}, None)

        assert result == mock_partial.return_value
        mock_partial.assert_called_once_with(add_worklog, sentinel.jira)
        mock_get_worklog.assert_not_called()


class TestLog:
    def test_help(self):
        result = runner.invoke(log, ["--help"])

        assert "Log time spent" in result.output

    def test_raises_when_time_spent_and_start_time_missing(self):
        result = runner.invoke(log, ["123"])

        assert result.exit_code == 2
        assert result.exception
        assert (
            "cannot spend without knowing working time or when work has started"
            in result.stdout
        )

    def test_raises_when_time_spent_and_start_time_and_comment_missing_in_worklog_mode(
        self,
    ):
        result = runner.invoke(log, ["123", "--worklog", "999"])

        assert result.exit_code == 2
        assert result.exception
        assert (
            "to update a worklog, either time spent or a comment is needed"
            in result.stdout
        )

    def test_runs_stuff_in_order(self, mocker):
        mocker.patch.dict(
            os.environ, {"JIRA_TOKEN": "token", "JIRA_EMAIL": "email"}, clear=True
        )
        mock_prepare_payload = mocker.patch("dzira.dzira.prepare_payload")
        mock_get_config = mocker.patch("dzira.dzira.get_config")
        mock_get_jira = mocker.patch("dzira.dzira.get_jira")
        mock_establish_issue = mocker.patch("dzira.dzira.establish_issue")
        mock_establish_action = mocker.patch("dzira.dzira.establish_action")
        mock_jira = mock_get_jira.return_value
        mock_config = mock_get_config.return_value
        args = {"time": "2h"}
        mock_prepare_payload.return_value = args

        result = runner.invoke(cli, ["log", "123", "-t", "2h"])

        assert result.exit_code == 0
        mock_prepare_payload.assert_called_once_with("2h", None, None, None)
        mock_get_config.assert_called_once_with(
            config=dict(JIRA_TOKEN="token", JIRA_EMAIL="email"),
        )
        mock_get_jira.assert_called_once_with(mock_config)
        mock_establish_issue.assert_called_once_with(mock_jira, mock_config, "123")
        mock_establish_action.assert_called_once_with(
            mock_jira, {**args, "issue": mock_establish_issue.return_value}, None
        )


class TestMain:
    def test_runs_cli(self, mocker):
        mock_cli = mocker.patch("dzira.dzira.cli")

        main()

        mock_cli.assert_called_once()

    def test_catches_exceptions_and_exits(self, mocker):
        mock_cli = mocker.patch("dzira.dzira.cli")
        exc = Exception("foo")
        mock_cli.side_effect = exc
        mock_print = mocker.patch("dzira.dzira.print")
        mock_exit = mocker.patch("dzira.dzira.sys.exit")

        main()

        mock_print.assert_called_once_with(exc, file=sys.stderr)
        mock_exit.assert_called_once_with(1)
