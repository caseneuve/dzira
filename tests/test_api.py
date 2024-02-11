from unittest.mock import Mock, sentinel

import pytest

from src.dzira.api import (
    connect_to_jira,
    get_board_by_key,
    get_sprints_by_board,

)


# fixtures:

@pytest.fixture
def mock_jira(mocker):
    return mocker.patch("src.dzira.api.JIRA")


@pytest.fixture
def mock_board():
    return Mock(id=sentinel.board_id)


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
