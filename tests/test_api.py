import os
import time
from datetime import datetime
from unittest.mock import Mock, sentinel

import pytest

from dzira.api import (
    ISSUES_DEAFAULT_FIELDS,
    connect_to_jira,
    get_board_by_key,
    get_closed_sprints_issues,
    get_current_sprint_issues,
    get_current_user_id,
    get_current_user_name,
    get_future_sprint_issues,
    get_issue_worklogs_by_user_and_date,
    get_issues_by_work_logged_on_date,
    get_sprint_issues,
    get_sprints_by_board,
    get_worklog,
    log_work,
    search_issues_with_sprint_info,
)


# fixtures:

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


def test_get_board_by_key_happy_path(mock_jira):
    mock_jira.boards.return_value = [sentinel.board]

    result = get_board_by_key(mock_jira, sentinel.key)

    assert result == sentinel.board
    mock_jira.boards.assert_called_once_with(projectKeyOrID=sentinel.key)


def test_get_board_by_key_raises_when_more_than_one_board_found(mock_jira):
    mock_jira.boards.return_value = [
        Mock(raw={"location": {"displayName": "board1"}}),
        Mock(raw={"location": {"displayName": "board2"}})
    ]

    with pytest.raises(Exception) as exc:
        get_board_by_key(mock_jira, "key")

    assert "Found more than one board matching 'key'" in str(exc)


def test_get_current_user_id(mock_jira):
    result = get_current_user_id(mock_jira)

    mock_jira.current_user.assert_called_once()
    assert result == mock_jira.current_user.return_value


def test_get_current_user_name(mock_jira):
    result = get_current_user_name(mock_jira)

    mock_jira.current_user.assert_called_once_with("displayName")
    assert result == mock_jira.current_user.return_value


def test_get_sprints_by_board(mock_jira, mock_board):
    result = get_sprints_by_board(mock_jira, mock_board, state=sentinel.state)

    mock_jira.sprints.assert_called_once_with(board_id=mock_board.id, state=sentinel.state)
    assert result == mock_jira.sprints.return_value


def test_get_sprint_issues(mock_jira, mock_sprint):
    result = get_sprint_issues(mock_jira, mock_sprint)

    assert result == list(mock_jira.search_issues.return_value)
    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"Sprint = {mock_sprint.id}"
    )


def test_get_current_sprint_issues(mock_jira):
    result = get_current_sprint_issues(mock_jira, "KEY")

    assert result == list(mock_jira.search_issues.return_value)
    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = 'KEY' AND sprint in openSprints()"
    )


def test_get_future_sprint_issues(mock_jira):
    result = get_future_sprint_issues(mock_jira, "KEY")

    assert result == list(mock_jira.search_issues.return_value)
    mock_jira.search_issues.assert_called_once_with(
        jql_str="project = 'KEY' AND sprint in futureSprints()"
    )


def test_get_closed_sprints_issues(mock_jira):
    result = get_closed_sprints_issues(mock_jira,"KEY")

    assert result == list(mock_jira.search_issues.return_value)
    mock_jira.search_issues.assert_called_once_with(
        jql_str="project = 'KEY' AND sprint in closedSprints()"
    )


def test_log_work_happy_path(mock_jira):
    result = log_work(
        mock_jira, sentinel.issue, 3600, comment=sentinel.comment, date=sentinel.date
    )

    assert result == mock_jira.add_worklog.return_value
    mock_jira.add_worklog.assert_called_once_with(
        issue=sentinel.issue,
        timeSpentSeconds=3600,
        comment=sentinel.comment,
        started=sentinel.date
    )


def test_log_work_raises_when_wrong_number_of_seconds(mock_jira):
    with pytest.raises(ValueError) as exc:
        log_work(mock_jira, sentinel.issue, 30, comment=sentinel.comment, date=sentinel.date)

    assert "30 seconds is too low to log" in str(exc)


def test_get_worklog(mock_jira):
    result = get_worklog(mock_jira, sentinel.issue, sentinel.worklog_id)

    assert result == mock_jira.worklog.return_value
    mock_jira.worklog.assert_called_once_with(issue=sentinel.issue, id=sentinel.worklog_id)


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


def test_search_issues_with_sprint_info_uses_sprint_id(mock_jira):
    sprint_id = "123"

    result = search_issues_with_sprint_info(
        mock_jira, project_key=Mock(), sprint_id=sprint_id
    )

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"sprint = {sprint_id}",
        fields=",".join(ISSUES_DEAFAULT_FIELDS)
    )
    assert result == list(mock_jira.search_issues_with_sprint_info.return_value)


def test_search_issues_with_sprint_info_sprint_id_has_precedence(mock_jira):
    sprint_id = "123"

    search_issues_with_sprint_info(
        mock_jira, project_key=Mock(), sprint_id=sprint_id, state="foo"
    )

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"sprint = {sprint_id}",
        fields=",".join(ISSUES_DEAFAULT_FIELDS)
    )


def test_search_issues_with_sprint_info_uses_default_state(mock_jira):
    project_key = "ABC-123"

    search_issues_with_sprint_info(mock_jira, project_key=project_key)

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = {project_key} AND sprint in openSprints()",
        fields=",".join(ISSUES_DEAFAULT_FIELDS)
    )


@pytest.mark.parametrize(
    "state,fn",
    [
        ("active", "openSprints()"),
        ("closed", "closedSprints()"),
        ("future", "futureSprints()"),
     ]
)
def test_search_issues_with_sprint_info_uses_provided_state(mock_jira, state, fn):
    project_key = "ABC-123"

    search_issues_with_sprint_info(mock_jira, project_key=project_key, state=state)

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = {project_key} AND sprint in {fn}",
        fields=",".join(ISSUES_DEAFAULT_FIELDS)
    )


def test_search_issues_with_sprint_info_fetches_extra_fields(mock_jira):
    project_key = "ABC-123"

    search_issues_with_sprint_info(mock_jira, project_key=project_key, extra_fields=["Foo", "Bar"])

    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = {project_key} AND sprint in openSprints()",
        fields=",".join(["Foo", "Bar"] + ISSUES_DEAFAULT_FIELDS)
    )
