from src.dzira.api import (
    connect_to_jira
)


def test_connect_to_jira(mocker):
    mock_jira = mocker.patch("src.dzira.api.JIRA")

    result = connect_to_jira("server", "email", "token")

    mock_jira.assert_called_once_with(server=f"https://server", basic_auth=("email", "token"))
    assert result == mock_jira.return_value
