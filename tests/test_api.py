import os
import time
from datetime import datetime
from unittest.mock import Mock, sentinel

import pytest

from dzira.api import (
    connect_to_jira,
    get_board_by_key,
    get_closed_sprints_issues,
    get_current_sprint_issues,
    get_current_user_id,
    get_current_user_name,
    get_future_sprint_issues,
    get_issue_worklogs_by_user_and_date,
    get_issues_by_work_logged_on_date,
    get_sprint_by_id,
    get_sprint_issues,
    get_sprints_by_board,
    get_worklog,
    log_work,
    search_issues_with_sprint_info,
)


# fixtures:

@pytest.fixture()
def issues_default_fields():
    return ["Sprint,status,summary,timespent,timeestimate,timetracking"]


@pytest.fixture()
def mock_jira(mocker):
    return mocker.patch("dzira.api.JIRA")


@pytest.fixture
def mock_board():
    return Mock(id=sentinel.board_id)


@pytest.fixture
def mock_sprint():
    return Mock(id=sentinel.id, name="SprintName")


# tests

def test_connect_to_jira(mock_jira):
    result = connect_to_jira("server", "email", "token")

    mock_jira.assert_called_once_with(server=f"https://server", basic_auth=("email", "token"))
    assert result == mock_jira.return_value


def test_should_return_board_when_single_board_matches_key(mock_jira):
    expected_board = Mock()
    expected_board.id = 123
    expected_board.name = "Test Board"
    mock_jira.boards.return_value = [expected_board]

    result = get_board_by_key(mock_jira, "TEST")

    assert result.id == 123
    assert result.name == "Test Board"


def test_should_raise_exception_when_multiple_boards_match_key(mock_jira):
    mock_jira.boards.return_value = [
        Mock(raw={"location": {"displayName": "board1"}}),
        Mock(raw={"location": {"displayName": "board2"}})
    ]

    with pytest.raises(Exception) as exc:
        get_board_by_key(mock_jira, "key")

    assert "Found more than one board matching 'key'" in str(exc.value)
    assert "board1" in str(exc.value) and "board2" in str(exc.value)


def test_should_return_current_user_id(mock_jira):
    expected_user_id = "user123"
    mock_jira.current_user.return_value = expected_user_id

    result = get_current_user_id(mock_jira)

    assert result == "user123"


def test_should_return_current_user_display_name(mock_jira):
    expected_name = "John Doe"
    mock_jira.current_user.return_value = expected_name

    result = get_current_user_name(mock_jira)

    assert result == "John Doe"


def test_should_return_sprints_filtered_by_board_and_state(mock_jira, mock_board):
    sprint1 = Mock()
    sprint1.id = 1
    sprint1.name = "Sprint 1"
    sprint2 = Mock()
    sprint2.id = 2
    sprint2.name = "Sprint 2"
    expected_sprints = [sprint1, sprint2]
    mock_jira.sprints.return_value = expected_sprints

    result = get_sprints_by_board(mock_jira, mock_board, state="active")

    assert len(result) == 2
    assert result[0].name == "Sprint 1"
    assert result[1].name == "Sprint 2"


def test_should_return_sprint_by_id(mock_jira):
    expected_sprint = Mock()
    expected_sprint.id = 42
    expected_sprint.name = "Test Sprint"
    mock_jira.sprint.return_value = expected_sprint

    result = get_sprint_by_id(mock_jira, 42)

    assert result.id == 42
    assert result.name == "Test Sprint"


def test_should_return_issues_for_given_sprint(mock_jira, mock_sprint):
    expected_issues = [Mock(key="TEST-1"), Mock(key="TEST-2")]
    mock_jira.search_issues.return_value = expected_issues

    result = get_sprint_issues(mock_jira, mock_sprint)

    assert len(result) == 2
    assert result[0].key == "TEST-1"
    assert result[1].key == "TEST-2"


class TestSprintIssueFiltering:
    def test_should_return_issues_from_current_active_sprints(self, mock_jira):
        expected_issues = [Mock(key="KEY-1"), Mock(key="KEY-2")]
        mock_jira.search_issues.return_value = expected_issues

        result = get_current_sprint_issues(mock_jira, "KEY")

        assert len(result) == 2
        assert all(issue.key.startswith("KEY-") for issue in result)

    def test_should_return_issues_from_future_sprints(self, mock_jira):
        expected_issues = [Mock(key="KEY-10"), Mock(key="KEY-11")]
        mock_jira.search_issues.return_value = expected_issues

        result = get_future_sprint_issues(mock_jira, "KEY")

        assert len(result) == 2
        assert all(issue.key.startswith("KEY-") for issue in result)

    def test_should_return_issues_from_closed_sprints(self, mock_jira):
        expected_issues = [Mock(key="KEY-100")]
        mock_jira.search_issues.return_value = expected_issues

        result = get_closed_sprints_issues(mock_jira, "KEY")

        assert len(result) == 1
        assert result[0].key == "KEY-100"


def test_should_create_worklog_when_valid_time_provided(mock_jira):
    expected_worklog = Mock(id="123", raw={"timeSpent": "1h"})
    mock_jira.add_worklog.return_value = expected_worklog

    result = log_work(mock_jira, "TEST-1", 3600, comment="test comment", date=None)

    assert result.id == "123"
    assert result.raw["timeSpent"] == "1h"


def test_should_reject_worklog_when_time_less_than_minimum(mock_jira):
    with pytest.raises(ValueError) as exc:
        log_work(mock_jira, "TEST-1", 299)  # Less than 5 minutes

    assert "299 seconds is too low to log" in str(exc.value)


def test_should_accept_worklog_at_minimum_time_boundary(mock_jira):
    expected_worklog = Mock(id="123", raw={"timeSpent": "5m"})
    mock_jira.add_worklog.return_value = expected_worklog

    result = log_work(mock_jira, "TEST-1", 300)  # Exactly 5 minutes

    assert result.id == "123"


def test_should_return_specific_worklog_by_id(mock_jira):
    expected_worklog = Mock(id="456", raw={"timeSpent": "2h", "comment": "work done"})
    mock_jira.worklog.return_value = expected_worklog

    result = get_worklog(mock_jira, "TEST-1", "456")

    assert result.id == "456"
    assert result.raw["timeSpent"] == "2h"
    assert result.raw["comment"] == "work done"


def test_get_issues_by_work_logged_on_date_uses_date_and_default_fields(mock_jira):
    report_date = datetime(2024, 2, 11, 10, 24)
    project_key = "FOO"

    result = get_issues_by_work_logged_on_date(
        mock_jira, project_key, report_date
    )

    assert result == mock_jira.search_issues.return_value
    mock_jira.search_issues.assert_called_once_with(
        "worklogDate = 2024-02-11 AND project = 'FOO'", fields="worklog,summary"
    )


def test_get_issues_by_work_logged_on_date_uses_today_as_fallback(mock_jira):
    project_key = "FOO"

    result = get_issues_by_work_logged_on_date(
        mock_jira, project_key, fields=sentinel.fields
    )

    assert result == mock_jira.search_issues.return_value
    mock_jira.search_issues.assert_called_once_with(
        "worklogDate >= startOfDay() AND project = 'FOO'", fields=sentinel.fields
    )


def test_get_issue_worklogs_by_user_and_date_from_the_issue(mock_jira):
    os.environ["TZ"] = "CET"
    time.tzset()

    email_address = "foo@bar"
    report_date = datetime(2023, 11, 26, 0, 0).astimezone()

    worklog1 = Mock(
        started="2023-11-26T13:42:16.000-0600",
        raw={
            "timeSpent": "30m",
            "comment": "ONLY ONE MATCHING",
            "timeSpentSeconds": 30 * 60,
        },
        author=Mock(emailAddress="foo@bar")
    )
    worklog2 = Mock(
        started="2023-11-25T01:42:00.000-0600",
        raw={
            "timeSpent": "1h 15m",
            "comment": "DATE BEFORE",
            "timeSpentSeconds": (60 * 60) + (15 * 60),
        },
        author=Mock(emailAddress="foo@bar")
    )
    worklog3 = Mock(
        started="2023-11-26T17:24:00.000-0500",
        raw={
            "timeSpent": "2h",
            "comment": "WRONG AUTHOR",
            "timeSpentSeconds": 2 * 60 * 60,
        },
        author=Mock(emailAddress="baz@quux")
    )
    worklog4 = Mock(
        started="2023-11-27T01:42:00.000-0600",
        raw={
            "timeSpent": "1h 15m",
            "comment": "DATE AFTER",
            "timeSpentSeconds": (60 * 60) + (15 * 60),
        },
        author=Mock(emailAddress="foo@bar")
    )
    mock_issue = Mock(fields=Mock(worklog=Mock(worklogs=[worklog1, worklog2, worklog3, worklog4])))

    result = get_issue_worklogs_by_user_and_date(mock_jira, mock_issue, email_address, report_date)

    assert result == [worklog1]
    assert not mock_jira.called


def test_get_issue_worklogs_by_user_and_date_from_jira(mock_jira):
    mock_jira.worklogs = Mock(
        return_value=[
            Mock(
                started="2023-11-26T13:42:16.000-0600",
                raw={
                    "timeSpent": "30m",
                    "comment": "ONLY ONE MATCHING",
                    "timeSpentSeconds": 30 * 60,
                },
                author=Mock(emailAddress="foo@bar")
            )
        ]
    )
    mock_issue = Mock(fields=Mock(worklog=Mock(worklogs=20 * [Mock()])))
    email_address = "foo@bar"
    report_date = datetime(2023, 11, 26, 0, 0).astimezone()

    result = get_issue_worklogs_by_user_and_date(mock_jira, mock_issue, email_address, report_date)

    assert result == mock_jira.worklogs.return_value


def test_get_issue_worklogs_by_user_and_date_exists_early_when_no_worklogs_found(mock_jira):
    mock_issue = Mock(fields=Mock())

    result = get_issue_worklogs_by_user_and_date(
        mock_jira, mock_issue, sentinel.email_address, sentinel.report_date
    )

    assert result == []
    assert not mock_jira.worklogs.called


def test_search_issues_with_sprint_info_uses_sprint_id(mock_jira, issues_default_fields):
    sprint_id = "123"

    result = search_issues_with_sprint_info(
        mock_jira, project_key=Mock(), sprint_id=sprint_id
    )

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"sprint = {sprint_id}",
        fields=",".join(issues_default_fields)
    )
    assert result == list(mock_jira.search_issues_with_sprint_info.return_value)


def test_search_issues_with_sprint_info_sprint_id_has_precedence(mock_jira, issues_default_fields):
    sprint_id = "123"

    search_issues_with_sprint_info(
        mock_jira, project_key=Mock(), sprint_id=sprint_id, state="foo"
    )

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"sprint = {sprint_id}",
        fields=",".join(issues_default_fields)
    )


def test_search_issues_with_sprint_info_uses_default_state(mock_jira, issues_default_fields):
    project_key = "ABC-123"

    search_issues_with_sprint_info(mock_jira, project_key=project_key)

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = {project_key} AND sprint in openSprints()",
        fields=",".join(issues_default_fields)
    )


@pytest.mark.parametrize(
    "state,fn",
    [
        ("active", "openSprints()"),
        ("closed", "closedSprints()"),
        ("future", "futureSprints()"),
     ]
)
def test_search_issues_with_sprint_info_uses_provided_state(
        mock_jira, state, fn, issues_default_fields
):
    project_key = "ABC-123"

    search_issues_with_sprint_info(mock_jira, project_key=project_key, state=state)

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = {project_key} AND sprint in {fn}",
        fields=",".join(issues_default_fields)
    )


def test_search_issues_with_sprint_info_fetches_extra_fields(mock_jira, issues_default_fields):
    project_key = "ABC-123"

    search_issues_with_sprint_info(mock_jira, project_key=project_key, extra_fields=["Foo", "Bar"])

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = {project_key} AND sprint in openSprints()",
        fields=",".join(["Foo", "Bar"] + issues_default_fields)
    )
