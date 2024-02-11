from unittest.mock import Mock, sentinel

import pytest

from src.dzira.api import (
    connect_to_jira,
    get_board_by_key,
    get_closed_sprints_issues,
    get_current_sprint_issues,
    get_future_sprint_issues,
    get_sprint_issues,
    get_sprints_by_board,
    get_worklog,
    log_work,
)


# fixtures:

@pytest.fixture
def mock_jira(mocker):
    return mocker.patch("src.dzira.api.JIRA")


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

    assert result == list(mock_jira.search_isseus.return_value)
    mock_jira.search_issues.assert_called_once_with(
        jql_str=f"project = 'KEY' AND sprint in openSprints()"
    )


def test_get_future_sprint_issues(mock_jira):
    result = get_future_sprint_issues(mock_jira, "KEY")

    assert result == list(mock_jira.search_isseus.return_value)
    mock_jira.search_issues.assert_called_once_with(
        jql_str="project = 'KEY' AND sprint in futureSprints()"
    )


def test_get_closed_sprints_issues(mock_jira):
    result = get_closed_sprints_issues(mock_jira,"KEY")

    assert result == list(mock_jira.search_isseus.return_value)
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
