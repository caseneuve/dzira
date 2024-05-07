import datetime
import os
import sys
import time
from collections import namedtuple
from unittest.mock import Mock, PropertyMock, call, patch, sentinel

import click
import pytest
import tabulate
from click.testing import CliRunner

from dzira.cli.commands import (
    D,
    DEFAULT_OUTPUT_FORMAT,
    VALIDATE_DATE_FORMATS,
    VALID_OUTPUT_FORMATS,
    Result,
    _seconds_to_hour_minute_fmt,
    _update_worklog,
    add_worklog,
    c,
    calculate_seconds,
    cli,
    colors,
    establish_issue,
    get_board,
    get_issues,
    get_issues,
    get_issues,
    get_issues_with_work_logged_on_date,
    get_jira,
    get_sprint,
    get_user_id,
    get_user_worklogs_from_date,
    get_worklog,
    is_valid_hour,
    log,
    ls,
    main,
    matches_time_re,
    perform_log_action,
    process_sprint_out,
    report,
    sanitize_params,
    set_color_use,
    set_spinner_use,
    show_issues,
    show_report,
    spinner,
    update_worklog,
    validate_date,
    validate_hour,
    validate_output_format,
    validate_time,
)


@pytest.fixture
def mock_print(mocker):
    return mocker.patch("dzira.cli.commands.print")


@pytest.fixture
def mock_tabulate(mocker):
    return mocker.patch("dzira.cli.commands.tabulate")


@pytest.fixture
def mock_json(mocker):
    return mocker.patch("dzira.cli.commands.json")


@pytest.fixture
def mock_csv(mocker):
    return mocker.patch("dzira.cli.commands.csv")


@pytest.fixture
def mock_isatty(mocker):
    return mocker.patch("dzira.cli.commands.sys.stdin.isatty", Mock(return_value=True))


@pytest.fixture
def mock_set_color_use(mocker):
    return mocker.patch("dzira.cli.commands.set_color_use")


@pytest.fixture
def mock_set_spinner_use(mocker):
    return mocker.patch("dzira.cli.commands.set_spinner_use")


@pytest.fixture
def mock_get_sprint(mocker):
    return mocker.patch("dzira.cli.commands.get_sprint")


@pytest.fixture
def mock_get_issues(mocker):
    return mocker.patch("dzira.cli.commands.get_issues")


@pytest.fixture
def mock_get_board(mocker):
    return mocker.patch("dzira.cli.commands.get_board")


@pytest.fixture
def mock_process_sprint_out(mocker):
    return mocker.patch("dzira.cli.commands.process_sprint_out")


@pytest.fixture
def mock_connect_to_jira(mocker):
    return mocker.patch("dzira.cli.commands.api.connect_to_jira")


@pytest.fixture
def mock_get_board_by_key(mocker):
    return mocker.patch(
        "dzira.cli.commands.api.get_board_by_key",
        Mock(return_value=Mock(raw={"location": {"displayName": "BoardName"}}))
    )


@pytest.fixture
def mock_get_sprint_by_id(mocker):
    return mocker.patch("dzira.cli.commands.api.get_sprint_by_id")


@pytest.fixture
def mock_get_sprints_by_board(mocker):
    return mocker.patch(
        "dzira.cli.commands.api.get_sprints_by_board",
        Mock(return_value=[sentinel.sprint1])
    )


class TestGetJira:
    config = D({"JIRA_SERVER": "server", "JIRA_EMAIL": "email", "JIRA_TOKEN": "token"})

    def test_is_decorated_correctly(self):
        assert get_jira.is_decorated_with_spin_it

    def test_returns_result(self, mock_connect_to_jira):
        result = get_jira(self.config)

        assert type(result) == Result
        assert result.result == mock_connect_to_jira.return_value
        assert "server" in result.stdout

    def test_jira_connection_is_established_using_provided_config(
            self, mock_connect_to_jira
    ):
        get_jira(self.config)

        mock_connect_to_jira.assert_called_once_with("server", "email", "token")


class TestGetBoard:
    def test_is_decorated_correctly(self):
        assert get_board.is_decorated_with_spin_it

    def test_gets_board(self, mock_get_board_by_key):
        mock_jira = Mock()

        result = get_board(mock_jira, sentinel.key)

        mock_get_board_by_key.assert_called_once_with(mock_jira, sentinel.key)
        assert type(result) == Result
        assert result.result == mock_get_board_by_key.return_value
        assert "BoardName" in result.stdout


class TestGetSprint:
    def test_is_decorated_correctly(self):
        assert get_sprint.is_decorated_with_spin_it

    def test_finds_sprint_from_id(self, mock_get_sprint_by_id, mock_process_sprint_out):
        mock_payload = D(sprint_id=sentinel.sprint_id)

        result = get_sprint(sentinel.jira, mock_payload)

        assert type(result) == Result
        assert result.result == mock_get_sprint_by_id.return_value
        mock_get_sprint_by_id.assert_called_once_with(sentinel.jira, sentinel.sprint_id)
        mock_process_sprint_out.assert_called_once_with(mock_get_sprint_by_id.return_value)

    def test_finds_sprint_using_state(self, mock_get_sprints_by_board, mock_process_sprint_out):
        mock_payload = D(state=sentinel.state, board=sentinel.board)

        result = get_sprint(sentinel.jira, mock_payload)

        assert type(result) == Result
        mock_get_sprints_by_board.assert_called_once_with(sentinel.jira, sentinel.board, sentinel.state)
        expected_sprint = mock_get_sprints_by_board.return_value[0]
        assert result.result == expected_sprint
        mock_process_sprint_out.assert_called_once_with(expected_sprint)

    def test_raises_when_not_one_sprint_found(self, mock_get_sprint_by_id):
        mock_get_sprint_by_id.side_effect = Exception

        with pytest.raises(Exception) as exc:
            get_sprint(sentinel.jira, D(sprint_id=sentinel.id))

        assert "Could not find sprint matching given criteria" in str(exc)


class TestAddWorklog:
    def test_calls_log_work_with_provided_values(self):
        mock_worklog = Mock(raw={"timeSpent": "2h"}, issueId="123", id=321)
        mock_jira = Mock(add_worklog=Mock(return_value=mock_worklog))

        result1 = add_worklog(mock_jira, "333", seconds=7200, date=sentinel.date)
        result2 = add_worklog(mock_jira, "333", seconds=60 * 60 * 2, comment="blah!")

        assert mock_jira.add_worklog.call_args_list == (
            [
                call(
                    issue="333",
                    timeSpentSeconds=7200,
                    comment=None,
                    started=sentinel.date,
                ),
                call(
                    issue="333",
                    timeSpentSeconds=7200,
                    comment="blah!",
                    started=None,
                ),
            ]
        )
        assert "spent 2h in 333 [worklog 321]" in result1.stdout
        assert "spent 2h in 333 [worklog 321]" in result2.stdout


class TestGetWorklog:
    def test_is_decorated_correctly(self):
        assert get_worklog.is_decorated_with_spin_it

    @patch("dzira.cli.commands.datetime", Mock())
    def test_returns_worklog(self, mocker):
        mock_api = mocker.patch("dzira.cli.commands.api.get_worklog")

        result = get_worklog(sentinel.jira, issue="123", worklog_id=999)

        assert type(result) == Result
        assert result.result == mock_api.return_value
        mock_api.assert_called_once_with(sentinel.jira, issue="123", worklog_id="999")



class TestUpdateWorklogPrivate:
    def test_updates_given_worklog_with_provided_fields_and_returns_info_about_updated_fields(self):
        mock_worklog = Mock(update=Mock(), id="42")
        fields = {"timeSpentSeconds": "3600", "comment": "blah!", "started": sentinel.date}

        result = _update_worklog(mock_worklog, time="3600", comment="blah!", date=sentinel.date)

        mock_worklog.update.assert_called_once_with(fields=fields)
        assert type(result) == D
        assert result == D(fields)

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
        mock_private = mocker.patch("dzira.cli.commands._update_worklog")

        result = update_worklog(mock_worklog, time="3600", comment="blah!", date=None)

        mock_private.assert_called_once_with(mock_worklog, "3600", "blah!", None)
        assert type(result) == Result
        assert "updated" in result.stdout


class TestCalculateSeconds:
    def test_returns_the_unchanged_payload_with_extra_key_seconds_if_no_start_time(self):
        input = D({"start": None, "end": None, "foo": "bar"})

        assert calculate_seconds(input) == input.update("seconds", None)

    def test_copies_value_of_time_to_seconds_if_time_provided(self):
        input = D({"time": 3600, "end": None, "foo": "bar"})

        assert calculate_seconds(input) == input.update("seconds", 3600)

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            ("8:59", "9:00", 60),
            ("8:00", "8:59", 59 * 60),
            ("8:00", "18:00", 10 * 60 * 60),
        ],
    )
    def test_returns_seconds_delta_of_end_and_start(self, start, end, expected):
        assert calculate_seconds(D(start=start, end=end))["seconds"] == expected

    def test_returns_seconds_delta_of_start_and_now_when_end_is_none(self, mocker):
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        start = "8:00"
        fake_now = "8:07"
        mock_datetime.strptime.side_effect = [
            datetime.datetime.strptime(fake_now, "%H:%M"),
            datetime.datetime.strptime(start, "%H:%M")
        ]
        assert calculate_seconds(D(start=start, end=None))["seconds"] == 7 * 60

    def test_accepts_multiple_separators_in_input(self, mocker):
        mock_sub = mocker.patch("dzira.cli.commands.re.sub")
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
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
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
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


class TestGetIssues:
    def test_is_decorated_correctly(self):
        assert get_issues.is_decorated_with_spin_it

    def test_gets_sprint_and_issues_using_api(self, mocker, mock_process_sprint_out):
        mock_api = mocker.patch("dzira.cli.commands.api.search_issues_with_sprint_info")
        mock_payload = D(sprint_id=sentinel.id, JIRA_PROJECT_KEY=sentinel.key, state=sentinel.state)
        mock_process_sprint_out.return_value = "output"
        mock_sprint_info = {"a": 1}
        mock_api.return_value = [Mock(raw={"fields": {"Sprint": [mock_sprint_info]}})]

        result = get_issues(sentinel.jira, mock_payload)

        mock_api.assert_called_once_with(
            sentinel.jira, project_key=sentinel.key, sprint_id=sentinel.id, state=sentinel.state
        )
        assert result == Result(
            result=D(sprint=D(mock_sprint_info), issues= mock_api.return_value),
            stdout="output"
        )


class TestShowIssues:
    def setup_method(self, _):
        status = namedtuple("status", ["name"])
        self.sprint = Mock(
            name="Iteration 42",
            id=42,
            startDate=datetime.datetime.strptime("2024-01-01T08:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"),
            endDate=datetime.datetime.strptime("2024-01-14T18:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ")
        )
        issue1 = Mock(
            key="XYZ-1",
            fields=Mock(
                summary="description 1",
                status=status("In Progress"),
                timespent=3600*4,
                timetracking=Mock(
                    remainingEstimate="1d",
                    originalEstimate="2d"
                )
            )
        )
        issue2 = Mock(
            key="XYZ-2",
            fields=Mock(
                summary="description 2",
                status=status(name="To Do"),
                timespent=3600*2,
                timetracking=Mock(
                    remainingEstimate="3d",
                    originalEstimate="3d"
                )
            )
        )
        self.issues = [issue1, issue2]
        self.sprint_and_issues = D(sprint=self.sprint, issues=self.issues)
        self.headers = ["key", "summary", "state", "spent", "estimated"]
        self.processed_issues = [
            ["XYZ-2", "description 2", "To Do", str(datetime.timedelta(seconds=3600*2)), "3d"],
            ["XYZ-1", "description 1", "In Progress", str(datetime.timedelta(seconds=3600*4)), "1d (2d)"]
        ]
        colors.use = False

    def test_shows_data_extracted_from_jira_issues(self, mock_print, mock_tabulate):
        show_issues(self.sprint_and_issues, format=sentinel.fmt)

        mock_tabulate.assert_called_once_with(
            self.processed_issues,
            headers=self.headers,
            colalign=("right", "left", "left", "right", "right"),
            maxcolwidths=[None, 35, None, None, None],
            tablefmt=sentinel.fmt
        )
        mock_print.assert_called_once_with(mock_tabulate.return_value)

    @pytest.mark.parametrize("fmt", tabulate.tabulate_formats)
    def test_uses_tabulate_if_format_other_than_csv_or_json(
            self, fmt, mock_tabulate, mock_json, mock_csv
    ):
        show_issues(self.sprint_and_issues, format=fmt)

        mock_tabulate.assert_called()
        assert not mock_json.dumps.called
        assert not mock_csv.DictWriter.called

    def test_prints_json(self, mock_tabulate, mock_json, mock_csv):
        show_issues(self.sprint_and_issues, format="json")

        expected_json_dict = {
            "sprint": {
                "name": self.sprint.name,
                "id": self.sprint.id,
                "start": self.sprint.startDate,
                "end": self.sprint.endDate,
            },
            "issues": [dict(zip(self.headers, i)) for i in self.processed_issues]
        }
        mock_json.dumps.assert_called_once_with(expected_json_dict)
        assert not mock_tabulate.called
        assert not mock_csv.DictWriter.called

    def test_prints_csv(self, mock_tabulate, mock_json, mock_csv):
        show_issues(self.sprint_and_issues, format="csv")

        expected_headers = ["sprint_id"] + self.headers
        mock_csv.DictWriter.assert_called_once_with(sys.stdout, fieldnames=expected_headers)
        mock_csv.DictWriter.return_value.writeheader.assert_called_once()
        mock_csv.DictWriter.return_value.writerows.assert_called_once_with(
            [dict(zip(expected_headers, [42] + i)) for i in self.processed_issues]
        )
        assert not mock_tabulate.called
        assert not mock_json.dumps.called


class TestSetColorUse:
    @pytest.mark.parametrize(
        "input,isatty,expected",
        [(True, True, True), (False, True, False), (True, False, False)]
    )
    def test_sets_color_option_using_user_input_and_interactivity_state(
            self, mocker, input, isatty, expected
    ):
        mocker.patch("dzira.cli.commands.sys.stdin.isatty", Mock(return_value=isatty))

        set_color_use(input)

        assert colors.use is expected


class TestSetSpinnerUse:
    @pytest.mark.parametrize(
        "input,isatty,expected",
        [(True, True, True), (False, True, False), (True, False, False)]
    )
    def test_sets_spinner_option_using_user_input_and_interactivity_state(
            self, mocker, input, isatty, expected
    ):
        mocker.patch("dzira.cli.commands.sys.stdin.isatty", Mock(return_value=isatty))

        set_spinner_use(input)

        assert spinner.use is expected


class CliTest:
    runner = CliRunner()


class TestCli(CliTest):
    def test_help(self):
        result = self.runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Configure JIRA connection" in result.output

    def test_by_default_uses_colorful_output(self, mock_set_color_use):
        result = self.runner.invoke(cli, ["log", "-h"])

        assert result.exit_code == 0
        mock_set_color_use.assert_called_once_with(True)

    def test_supports_option_to_set_use_color(self, mock_set_color_use):
        result = self.runner.invoke(cli, ["--no-color", "log", "-h"])

        assert result.exit_code == 0
        mock_set_color_use.assert_called_once_with(False)

    def test_by_default_uses_spinner(self, mock_set_spinner_use):
        result = self.runner.invoke(cli, ["log", "-h"])

        assert result.exit_code == 0
        mock_set_spinner_use.assert_called_once_with(True)

    def test_supports_option_to_set_spinner(self, mock_set_spinner_use):
        result = self.runner.invoke(cli, ["--no-spin", "log", "-h"])

        assert result.exit_code == 0
        mock_set_spinner_use.assert_called_once_with(False)


class TestValidateOutputFormat:
    @pytest.mark.parametrize(
        "fmt", VALID_OUTPUT_FORMATS + list(map(str.upper, VALID_OUTPUT_FORMATS))
    )
    def test_returns_lowered_format_if_valid(self, fmt):
        validate_output_format(Mock(), Mock(), fmt)

    def test_raises_when_format_invalid(self):
        with pytest.raises(click.BadParameter) as exc_info:
            validate_output_format(Mock(), Mock(), "invalid")

        assert f"format should be one of" in str(exc_info)


class TestLs(CliTest):
    def test_help(self):
        result = self.runner.invoke(ls, ["--help"])

        assert result.exit_code == 0
        assert "List issues from the current sprint" in result.output

    def test_happy_run(self, mocker):
        mock_config = {}
        mocker.patch("dzira.cli.commands.get_config", return_value=mock_config)
        mocker.patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
        mock_get_issues = mocker.patch(
            "dzira.cli.commands.get_issues", Mock(return_value=Mock(result=sentinel.issues))
        )
        mock_show_issues = mocker.patch("dzira.cli.commands.show_issues")

        result = self.runner.invoke(cli, ["--token", "foo", "ls"])

        assert result.exit_code == 0
        mock_get_issues.assert_called_once_with(
            sentinel.jira,
            D(state="active", sprint_id=None, **mock_config)
        )
        mock_show_issues.assert_called_once_with(sentinel.issues, format=DEFAULT_OUTPUT_FORMAT)

    @patch.dict(os.environ, {"JIRA_PROJECT_KEY": "XYZ"}, clear=True)
    @patch("dzira.cli.commands.get_issues")
    def test_has_access_to_context_provided_by_cli_group(self, mock_get_issues, mocker):
        mock_config = {"JIRA_PROJECT_KEY": "XYZ", "JIRA_EMAIL": "foo@bar.com"}
        mock_get_config = mocker.patch("dzira.cli.commands.get_config")
        mocker.patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=sentinel.jira)))

        self.runner.invoke(cli, ["--email", "foo@bar.com", "ls"])

        mock_get_issues.assert_called_once_with(
            sentinel.jira, D(state="active", sprint_id=None, **mock_get_config.return_value)
        )
        mock_get_config.assert_called_once_with(config=mock_config)

    @pytest.mark.parametrize("state", ["active", "closed", "future"])
    def test_uses_state_option(self, mocker, state):
        mock_get_config = mocker.patch("dzira.cli.commands.get_config")
        mocker.patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
        mock_get_issues = mocker.patch("dzira.cli.commands.get_issues")
        mock_get_issues.return_value = Result(result=sentinel.issues)
        mocker.patch("dzira.cli.commands.show_issues")

        result = self.runner.invoke(cli, ["ls", "--state", state])

        assert result.exit_code == 0
        mock_get_issues.assert_called_once_with(
            sentinel.jira, D(state=state, sprint_id=None, **mock_get_config.return_value)
        )

    def test_uses_sprint_id_option(self, mocker):
        mock_get_config = mocker.patch("dzira.cli.commands.get_config")
        mocker.patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
        mock_get_issues = mocker.patch("dzira.cli.commands.get_issues")
        mock_get_issues.return_value = Result(result=sentinel.issues)
        mocker.patch("dzira.cli.commands.show_issues")

        result = self.runner.invoke(cli, ["ls", "--sprint-id", "42"])

        assert result.exit_code == 0
        mock_get_issues.assert_called_once_with(
            sentinel.jira, D(state="active", sprint_id=42, **mock_get_config.return_value)
        )

    def test_supports_tabulate_formats_option(self, mocker):
        mocker.patch("dzira.cli.commands.get_config")
        mocker.patch("dzira.cli.commands.get_jira")
        mock_issues = mocker.patch("dzira.cli.commands.get_issues")
        mock_show_issues = mocker.patch("dzira.cli.commands.show_issues")

        result = self.runner.invoke(cli, ["ls", "--format", "orgtbl"])

        assert result.exit_code == 0
        mock_show_issues.assert_called_once_with(mock_issues.return_value.result, format="orgtbl")


class TestCorrectTimeFormats:
    @pytest.mark.parametrize(
        "input, expected",
        [
            # valid
            ("1h 1m", D(h="1", m="1")),
            ("1h1m", D(h="1", m="1")),
            ("1h 59m", D(h="1", m="59")),
            ("1h59m", D(h="1", m="59")),
            ("3h1m", D(h="3", m="1")),
            ("2h", D(h="2", m=None)),
            ("42m", D(m="42")),
            ("8h 59", D(h="8", m="59")),
            # invalid
            ("9h 1m", D()),
            ("8 20", D()),
            ("24h 1m", D()),
            ("0h 1m", D()),
            ("1h 0m", D()),
            ("1h 60m", D()),
            ("500m", D()),  # more than 8 h (exactly 8h 19m), invalid
            ("9m", D()),  # less than 10 min, invalid
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


@patch("dzira.cli.commands.matches_time_re")
class TestValidateTime:
    def test_passes_when_time_is_none(self, mock_matches_time_re):
        result = validate_time(Mock(), Mock(), None)

        assert result == 0
        mock_matches_time_re.assert_not_called()

    def test_passes_when_validator_passes(self, mock_matches_time_re):
        mock_matches_time_re.return_value = D(h="2")

        result = validate_time(Mock(), Mock(), "2h")

        assert result == 7200
        mock_matches_time_re.assert_called_with("2h")

    def test_raises_otherwise(self, mock_matches_time_re):
        mock_matches_time_re.return_value = False

        with pytest.raises(click.BadParameter) as exc_info:
            validate_time(Mock(), Mock(), "invalid")

        mock_matches_time_re.assert_called_with("invalid")
        assert "time cannot be greater than" in str(exc_info)
        assert "has to be in format '[Nh][ N[m]]' or 'Nm'" in str(exc_info)


@patch("dzira.cli.commands.is_valid_hour")
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

    @pytest.mark.parametrize("given_time", ["17h23", "17,23", "17.23", "17:23"])
    def test_passes_when_validator_passes_and_returns_unified_value(
            self, mock_is_valid_hour, given_time
    ):
        mock_ctx = Mock(params={"start": "16h42"})
        mock_param = Mock()
        type(mock_param).name = PropertyMock(return_value="end")
        mock_is_valid_hour.return_value = True

        result = validate_hour(mock_ctx, mock_param, given_time)

        assert result == "17:23"
        mock_is_valid_hour.assert_called_once_with(given_time)

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
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        mock_isinstance = mocker.patch("dzira.cli.commands.isinstance")
        mocker.patch("dzira.cli.commands.VALIDATE_DATE_FORMATS", ["%Y-%m-%d %H:%M"])
        mock_isinstance.return_value = True
        mock_datetime.strptime.return_value = datetime.datetime(2023, 11, 23, 13, 42)
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)
        mock_datetime.utcnow.return_value\
            .astimezone.return_value\
            .utcoffset.return_value = None

        result = validate_date(mock_ctx, Mock(), "2023-11-23")

        assert result == datetime.datetime(2023, 11, 23, 13, 42)
        mock_datetime.strptime.assert_called_once_with("2023-11-23 13:42", "%Y-%m-%d %H:%M")

    def test_adds_current_time_when_only_date_provided_in_the_option(self, mocker):
        mocker.patch("dzira.cli.commands.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        mock_given_date = datetime.datetime(2023, 11, 23, 0, 0)
        mock_datetime.strptime.return_value = mock_given_date
        mock_now = datetime.datetime(2023, 11, 24, 18, 5, 43)
        mock_datetime.now.return_value = mock_now
        mock_delta = datetime.timedelta(seconds=3600)
        mock_datetime.utcnow.return_value\
            .astimezone.return_value\
            .utcoffset.return_value = mock_delta
        mock_combine = datetime.datetime(2023, 11, 23, 18, 5, 43)
        mock_datetime.combine.return_value = mock_combine

        result = validate_date(Mock(), Mock(), "2023-11-23")

        assert result == mock_combine - mock_delta
        mock_datetime.combine.assert_called_once_with(mock_datetime.date.return_value, mock_now.time())
        mock_datetime.date.assert_called_once_with(mock_given_date)


    def test_validates_against_multiple_formats_and_raises_when_none_matches(self, mocker):
        mocker.patch("dzira.cli.commands.isinstance", Mock(return_value=False))
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        mock_datetime.strptime.side_effect = 3 * [ValueError]

        with pytest.raises(click.BadParameter) as exc_info:
            validate_date(Mock(), Mock(), "foo")

        assert "date has to match one of supported ISO formats" in str(exc_info)
        assert ", ".join(VALIDATE_DATE_FORMATS) in str(exc_info)
        for fmt in VALIDATE_DATE_FORMATS:
            mock_datetime.strptime.assert_has_calls([call("foo", fmt)])

    def test_raises_when_date_in_future(self, mocker):
        mocker.patch("dzira.cli.commands.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        mock_datetime.strptime.side_effect = [ValueError, datetime.datetime(2055, 11, 23, 13, 42)]
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)

        with pytest.raises(click.BadParameter) as exc_info:
            validate_date(Mock(), Mock(), "2055-11-23T13:42")

        assert "worklog date cannot be in future" in str(exc_info)

    def test_raises_when_date_older_than_2_weeks(self, mocker):
        mocker.patch("dzira.cli.commands.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        mock_datetime.strptime.side_effect = [ValueError, datetime.datetime(1055, 11, 23, 13, 42)]
        mock_datetime.now.return_value = datetime.datetime(2023, 11, 24, 18, 0)

        with pytest.raises(click.BadParameter) as exc_info:
            validate_date(Mock(), Mock(), "1055-11-23T13:42")

        assert "worklog date cannot be older than 2 weeks" in str(exc_info)

    def test_tries_to_convert_date_to_timezone_aware(self, mocker):
        mocker.patch("dzira.cli.commands.isinstance", Mock(return_value=True))
        mock_datetime = mocker.patch("dzira.cli.commands.datetime")
        mock_datetime.strptime.side_effect = [ValueError, datetime.datetime(2023, 11, 23, 13, 42)]
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
        mock_calculate_seconds = mocker.patch("dzira.cli.commands.calculate_seconds")

        result = sanitize_params(args)

        mock_calculate_seconds.assert_called_once_with(args)
        assert result == mock_calculate_seconds.return_value


@patch("dzira.cli.commands.get_issues")
class TestEstablishIssue:
    config = {"JIRA_PROJECT_KEY": "XYZ"}

    def test_returns_early_if_issue_is_digits_and_key_provided(
            self, mock_get_issues,
    ):
        result = establish_issue(Mock(), D(issue="123", **self.config))

        assert result == D(issue="XYZ-123", **self.config)
        mock_get_issues.assert_not_called()

    def test_returns_early_if_issue_is_digits_and_board_not_provided(
            self, mock_get_sprint_and_issues,
    ):
        result = establish_issue(Mock(), D(issue="123", **self.config))

        assert result == D(issue="XYZ-123", **self.config)
        mock_get_sprint_and_issues.assert_not_called()

    def test_raises_when_no_matching_issue_in_current_sprint(
            self, mock_get_issues
    ):
        mock_get_issues.return_value = Result(result=D(issues=[]))

        with pytest.raises(Exception) as exc_info:
            establish_issue(Mock(), D(issue="some description", **self.config))

        assert "could not find any matching issues" in str(exc_info)

    def test_raises_when_more_than_one_matching_issue_in_current_sprint(
            self, mock_get_issues
    ):
        mock_get_issues.return_value = Result(
            result=D(
                issues=[
                    Mock(key="1", fields=Mock(summary="I have some description")),
                    Mock(key="2", fields=Mock(summary="Need some description")),
                ]
            )
        )

        with pytest.raises(Exception) as exc_info:
            establish_issue(Mock(), D(issue="some description", **self.config))

        assert "found more than one matching issue" in str(exc_info)

    def test_returns_updated_payload_with_issue_key_when_issue_found_in_the_sprint(
            self, mock_get_issues,
    ):
        mock_get_issues.return_value = Result(
            result=D(
                issues=[
                    Mock(key="1", fields=Mock(summary="I have some description")),
                    Mock(key="2", fields=Mock(summary="I don't have any matching phrases")),
                ]
            )
        )

        result = establish_issue(Mock(), D(issue="some description").update(**self.config))

        assert result == D(issue="1", **self.config)


class TestPerformLogAction:
    def test_returns_update_worklog_if_worklog_id_provided(self, mocker):
        mock_get_worklog = mocker.patch("dzira.cli.commands.get_worklog")
        mock_update_worklog = mocker.patch("dzira.cli.commands.update_worklog")
        payload = D(issue=sentinel.issue, worklog_id=sentinel.worklog)

        perform_log_action(sentinel.jira, payload)

        mock_get_worklog.assert_called_once_with(
            sentinel.jira, issue=sentinel.issue, worklog_id=sentinel.worklog
        )
        mock_update_worklog.assert_called_once_with(
            mock_get_worklog.return_value.result,
            **payload
        )

    def test_returns_add_worklog_if_worklog_id_not_provided(self, mocker):
        mock_get_worklog = mocker.patch("dzira.cli.commands.get_worklog")
        mock_add_worklog = mocker.patch("dzira.cli.commands.add_worklog")
        payload = D(issue=sentinel.issue, worklog_id=None)

        perform_log_action(sentinel.jira, payload)

        mock_get_worklog.assert_not_called()
        mock_add_worklog.assert_called_once_with(sentinel.jira, **payload)


class TestLog(CliTest):
    def test_help(self):
        result = self.runner.invoke(log, ["--help"])

        assert "Log time spent" in result.output

    def test_runs_stuff_in_order(self, mocker):
        mocker.patch.dict(
            os.environ, {"JIRA_TOKEN": "token", "JIRA_EMAIL": "email"}, clear=True
        )
        mock_sanitize_params = mocker.patch("dzira.cli.commands.sanitize_params")
        mock_get_config = mocker.patch("dzira.cli.commands.get_config")
        mock_get_jira = mocker.patch("dzira.cli.commands.get_jira")
        mock_establish_issue = mocker.patch("dzira.cli.commands.establish_issue")
        mock_perform_log_action = mocker.patch("dzira.cli.commands.perform_log_action")

        mock_jira = mock_get_jira.return_value.result
        mock_config = mock_get_config.return_value

        result = self.runner.invoke(cli, ["log", "123", "-t", "2h"])

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


class TestGetUser:
    def test_is_decorated_correctly(self):
        assert get_user_id.is_decorated_with_spin_it

    def test_uses_api_and_returns_correct_data(self, mocker):
        mock_jira = Mock()
        mock_api = mocker.patch("dzira.cli.commands.api.get_current_user_id")

        result = get_user_id(mock_jira)

        assert isinstance(result, Result)
        assert result.result == mock_api.return_value
        mock_api.assert_called_once_with(mock_jira)


class TestGetIssuesWithWorkLoggedOnDate:
    def test_is_decorated_correctly(self):
        assert get_issues_with_work_logged_on_date.is_decorated_with_spin_it

    def test_calls_api_to_get_issues(self, mocker):
        mock_api = mocker.patch("dzira.cli.commands.api.get_issues_by_work_logged_on_date")
        report_date = datetime.datetime(2024, 2, 11, 10, 31)

        result = get_issues_with_work_logged_on_date(
            sentinel.jira, sentinel.project_key, report_date
        )

        assert result.result == mock_api.return_value
        mock_api.assert_called_once_with(sentinel.jira, sentinel.project_key, report_date)

    def test_passes_date_in_data_field_of_result(self, mocker):
        mocker.patch("dzira.cli.commands.api.get_issues_by_work_logged_on_date")

        result = get_issues_with_work_logged_on_date(
            sentinel.jira, sentinel.project_key, datetime.datetime(2023, 11, 25)
        )

        assert result.data.report_date == datetime.datetime(2023, 11, 25)


@patch("dzira.cli.commands.api.get_issue_worklogs_by_user_and_date")
class TestGetUserWorklogsFromDate:
    def setup_method(self, _):
        self.issue1 = Mock(id=1, key="Issue-1", fields=Mock(summary="Foo bar"))
        self.issue2 = Mock(id=2, key="Issue-2", fields=Mock(summary="Baz quux"))
        self.issues = [self.issue1, self.issue2]

    def test_is_decorated_correctly(self, _):
        assert get_user_worklogs_from_date.is_decorated_with_spin_it

    def test_uses_api_to_fetch_worklogs(self, mock_api):
        report_date = datetime.datetime(2023, 11, 26, 0, 0)

        get_user_worklogs_from_date(
            sentinel.jira,
            sentinel.email,
            Result(result=self.issues, data=D(report_date=report_date))
        )

        assert mock_api.call_args_list == [
            call(sentinel.jira, self.issue1, sentinel.email, report_date),
            call(sentinel.jira, self.issue2, sentinel.email, report_date)
        ]

    def test_returns_mapping_of_issue_to_worklogs(self, mock_api):
        mock_api.side_effect = [[sentinel.worklog1], []]

        result = get_user_worklogs_from_date(
            sentinel.jira,
            sentinel.email,
            Result(result=self.issues, data=D(report_date=datetime.datetime(2023, 11, 26, 0, 0)))
        )

        assert result.result == D(
            {1: D(key="Issue-1", summary="Foo bar", worklogs=[sentinel.worklog1])}
        )
        assert "Found 1 worklog" in result.stdout


class TestSecondsToHourMinutFmt:
    @pytest.mark.parametrize(
        "input,expected",
        [
            (3600, "1h 00m"),
            (3659, "1h 00m"),
            (3660, "1h 01m"),
            (360,  "0h 06m"),
            (361,  "0h 06m"),
        ]
    )
    def test_converts_seconds_to_h_m_format(self, input, expected):
        assert _seconds_to_hour_minute_fmt(input) == expected


class TestShowReport:
    def setup_method(self, _):
        os.environ["TZ"] = "UTC"
        time.tzset()
        self.user = Mock(accountId="123")
        self.worklog1 = Mock(
            raw={
                "started": "2023-11-26T13:42:16.000+0100",
                "timeSpent": "30m",
                "comment": "task a",
                "timeSpentSeconds": 30 * 60,
            },
            author=Mock(accountId="123"),
            id="1"
        )
        self.worklog2 = Mock(
            raw={
                "started":"2023-11-26T15:42:00.000+0100",
                "timeSpent": "1h 15m",
                "comment": "task b",
                "timeSpentSeconds": (60 * 60) + (15 * 60),
            },
            author=Mock(accountId="123"),
            id="2"
        )
        self.worklogs_of_issues = D(
            {
                1: D(key="XY-1", summary="issue 1", worklogs=[self.worklog1]),
                2: D(key="XY-2", summary="issue 2", worklogs=[self.worklog2]),
            }
        )

    def test_uses_tabulate_to_show_the_report_with_worklog_id_timestamp_timespent_and_comment(
            self, mock_tabulate, mock_print, mock_csv, mock_json
    ):
        mock_tabulate.side_effect = [sentinel.t1, sentinel.t2]
        show_report(self.worklogs_of_issues, format="table")

        assert mock_tabulate.call_args_list == [
            call([["[1]", "12:42:16", ":   30m", "task a"]], maxcolwidths=[None, None, None, 60]),
            call([["[2]", "14:42:00", ":1h 15m", "task b"]], maxcolwidths=[None, None, None, 60])
        ]
        mock_print.assert_has_calls(
            [
                call(c("^bold", "[XY-1] issue 1 ", "^cyan", "(0h 30m)")),
                call(sentinel.t1),
                call(c("^bold", "[XY-2] issue 2 ", "^cyan", "(1h 15m)")),
                call(sentinel.t2)
             ],
            any_order=True
        )
        assert not mock_csv.DictWriter.called
        assert not mock_json.dumps.called

    def test_prints_data_in_csv_format(
            self, mock_csv, mock_print, mock_json, mock_tabulate
    ):
        show_report(self.worklogs_of_issues, format="csv")

        headers = ["issue", "summary", "worklog", "started", "spent", "spent_seconds", "comment"]
        processed_worklogs = [
            ["XY-1", "issue 1", "1", "12:42:16", "30m", 30 * 60, "task a"],
            ["XY-2", "issue 2", "2", "14:42:00", "1h 15m", (60 * 60) + (15 * 60), "task b"]
        ]
        mock_csv.DictWriter.assert_called_once_with(sys.stdout, fieldnames=headers)
        mock_csv.DictWriter.return_value.writeheader.assert_called_once()
        mock_csv.DictWriter.return_value.writerows.assert_called_once_with(
            [dict(zip(headers, w)) for w in processed_worklogs]
        )
        assert not mock_tabulate.called
        assert not mock_json.dumps.called
        assert not mock_print.called

    def test_prints_data_in_json_format(
            self, mock_csv, mock_print, mock_json, mock_tabulate
    ):
        show_report(self.worklogs_of_issues, format="json")

        processed_worklogs = {
            "issues": [
                {
                    "key": "XY-1",
                    "summary": "issue 1",
                    "issue_total_time": "0h 30m",
                    "issue_total_spent_seconds": 30 * 60,
                    "worklogs": [
                        {
                            "id": "1",
                            "started": "12:42:16",
                            "spent": "30m",
                            "spent_seconds": 30 * 60,
                            "comment": "task a"
                        }
                    ]
                },
                {
                    "key": "XY-2",
                    "summary": "issue 2",
                    "issue_total_time": "1h 15m",
                    "issue_total_spent_seconds": (60 * 60) + (15 * 60),
                    "worklogs": [
                        {
                            "id": "2",
                            "started": "14:42:00",
                            "spent": "1h 15m",
                            "spent_seconds": (60 * 60) + (15 * 60),
                            "comment": "task b"
                        }
                    ]
                }
            ],
            "total_time": "1h 45m",
            "total_seconds": (30 * 60) + (60 * 60) + (15 * 60)
        }
        mock_json.dumps.assert_called_once_with(processed_worklogs)
        mock_print.assert_called_once_with(mock_json.dumps.return_value)
        assert not mock_csv.DictWriter.called
        assert not mock_tabulate.called


class TestReport(CliTest):
    def test_help(self):
        result = self.runner.invoke(report, ["--help"])

        assert "Show work logged for today or for DATE" in result.output

    @patch("dzira.cli.commands.show_report")
    @patch("dzira.cli.commands.get_user_worklogs_from_date")
    @patch("dzira.cli.commands.get_issues_with_work_logged_on_date")
    @patch("dzira.cli.commands.get_jira")
    @patch("dzira.cli.commands.get_config")
    def test_runs_stuff_in_order(
            self,
            mock_get_config,
            mock_get_jira,
            mock_get_issues_with_work_logged_on_date,
            mock_get_user_worklogs_from_date,
            mock_show_report
    ):
        mock_config = mock_get_config.return_value = {
            "JIRA_EMAIL": sentinel.email, "JIRA_PROJECT_KEY": sentinel.project_key
        }
        mock_jira = mock_get_jira.return_value.result

        result = self.runner.invoke(report, ["--date", "2023-11-26"])

        assert result.exit_code == 0

        mock_get_config.assert_called_once()
        mock_get_jira.assert_called_once_with(mock_config)
        mock_get_issues_with_work_logged_on_date.assert_called_once_with(
            mock_jira,
            sentinel.project_key,
            datetime.datetime(2023, 11, 26, 0, 0)
        )
        mock_get_user_worklogs_from_date.assert_called_once_with(
            mock_jira,
            sentinel.email,
            mock_get_issues_with_work_logged_on_date.return_value
        )
        mock_show_report.assert_called_once_with(
            mock_get_user_worklogs_from_date.return_value.result,
            format="table"
        )

    @patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
    @patch("dzira.cli.commands.get_config")
    @patch("dzira.cli.commands.show_report")
    @patch("dzira.cli.commands.get_user_worklogs_from_date")
    @patch("dzira.cli.commands.get_issues_with_work_logged_on_date")
    def test_runs_show_report_with_empty_dict_when_no_worklogs_found(
            self,
            mock_get_issues_with_work_logged_on_date,
            mock_get_user_worklogs_from_date,
            mock_show_report,
            mock_get_config
    ):
        mock_get_config.return_value = {"JIRA_EMAIL": "email", "JIRA_PROJECT_KEY": "key"}
        mock_get_issues_with_work_logged_on_date.return_value = Result()

        self.runner.invoke(report, ["--date", "2023-11-26"])

        assert not mock_get_user_worklogs_from_date.called
        mock_show_report.assert_called_once_with(D(), format="table")

    @pytest.mark.parametrize("fmt", ["csv", "json", "table"])
    @patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=Mock())))
    @patch(
        "dzira.cli.commands.get_issues_with_work_logged_on_date",
        Mock(return_value=Result(result=Mock()))
    )
    @patch(
        "dzira.cli.commands.get_user_worklogs_from_date",
        Mock(return_value=Result(result=sentinel.worklogs))
    )
    @patch("dzira.cli.commands.get_config")
    @patch("dzira.cli.commands.show_report")
    def test_accepts_format_option(self, mock_show_report, mock_get_config, fmt):
        mock_get_config.return_value = {"JIRA_EMAIL": "email", "JIRA_PROJECT_KEY": "key"}

        result = self.runner.invoke(report, ["--format", fmt])

        assert result.exit_code == 0
        mock_show_report.assert_called_once_with(sentinel.worklogs, format=fmt)

    @patch("dzira.cli.commands.get_jira", Mock(return_value=Mock(result=sentinel.jira)))
    @patch("dzira.cli.commands.get_config", Mock(return_value=Mock(result=Mock())))
    @patch("dzira.cli.commands.show_report")
    @patch("dzira.cli.commands.get_user_worklogs_from_date")
    @patch("dzira.cli.commands.get_issues_with_work_logged_on_date")
    def test_raises_when_wrong_format_option(
            self,
            mock_get_issues_with_work_logged_on_date,
            mock_get_user_worklogs_from_date,
            mock_show_report,
    ):
        mock_get_issues_with_work_logged_on_date.return_value = Result(result=[sentinel.issue])
        mock_worklogs = [Mock()]
        mock_get_user_worklogs_from_date.return_value = Result(result=mock_worklogs)

        result = self.runner.invoke(report, ["--format", "foo"])

        assert result.exit_code == 2
        assert not mock_show_report.called


class TestMain:
    def test_runs_cli(self, mocker):
        mock_cli = mocker.patch("dzira.cli.commands.cli")

        main()

        mock_cli.assert_called_once()

    def test_catches_exceptions_and_exits(self, mocker, mock_print):
        mocker.patch("dzira.cli.commands.hide_cursor")
        mocker.patch("dzira.cli.commands.show_cursor")
        mock_cli = mocker.patch("dzira.cli.commands.cli")
        exc = Exception("foo")
        mock_cli.side_effect = exc
        mock_exit = mocker.patch("dzira.cli.commands.sys.exit")

        main()

        mock_print.assert_called_once_with(exc, file=sys.stderr)
        mock_exit.assert_called_once_with(1)

    def test_hides_and_shows_the_cursor_when_in_interactive_shell(self, mocker, mock_isatty):
        mocker.patch("dzira.cli.commands.cli")
        mock_hide = mocker.patch("dzira.cli.commands.hide_cursor")
        mock_show = mocker.patch("dzira.cli.commands.show_cursor")

        main()

        mock_hide.assert_called_once()
        mock_show.assert_called_once()

    def test_does_not_hide_or_show_the_cursor_when_in_not_interactive_shell(
            self, mocker, mock_isatty
    ):
        mocker.patch("dzira.cli.commands.cli")
        mock_isatty.return_value = False
        mock_hide = mocker.patch("dzira.cli.commands.hide_cursor")
        mock_show = mocker.patch("dzira.cli.commands.show_cursor")

        main()

        assert not mock_hide.called
        assert not mock_show.called
