from unittest.mock import Mock, patch

import pytest
from jira import JIRA
from jira.exceptions import JIRAError

from dzira.core.models_rop import JiraConfig
from dzira.core.operations_rop import create_jira_connection
from dzira.core.result import Result


@pytest.fixture(scope="class")
def mock_jira():
    with patch("dzira.core.operations_rop.JIRA") as mock:
        mock_client = Mock(spec=JIRA)
        mock.return_value = mock_client
        yield mock


class TestCreateJiraConnection:
    @pytest.fixture(autouse=True)
    def setup(self, mock_jira):
        self.mock_jira = mock_jira
        yield
        self.mock_jira.reset_mock()
        self.mock_jira.side_effect = None

    def expected_call_args(self, jira_config):
        return {
            "server": f"https://{jira_config.JIRA_SERVER}",
            "basic_auth": (jira_config.JIRA_EMAIL, jira_config.JIRA_TOKEN),
        }

    def test_returns_result_type(self, jira_config):
        result = create_jira_connection(jira_config)

        assert isinstance(result, Result)
        assert hasattr(result, "is_success")
        assert hasattr(result, "is_failure")

    def test_success_with_valid_config(self, jira_config):
        result = create_jira_connection(jira_config)

        assert result.is_success
        assert result.value == self.mock_jira.return_value
        self.mock_jira.assert_called_once_with(**self.expected_call_args(jira_config))

    def test_success_with_sanitized_server_url(self, config):
        config["JIRA_SERVER"] = "https://test.atlassian.net"
        jira_config = JiraConfig.from_dict(config)

        result = create_jira_connection(jira_config)

        assert result.is_success
        self.mock_jira.assert_called_once_with(**self.expected_call_args(jira_config))

    @pytest.mark.parametrize(
        "exception,message",
        [
            (JIRAError, "401: Authentication failed"),
            (ConnectionError, "Failed to connect to server"),
            (Exception, "Unexpected error"),
            (ValueError, "Invalid configuration"),
        ],
    )
    def test_failure_scenarios(self, jira_config, exception, message):
        error = exception(message)
        self.mock_jira.side_effect = error

        result = create_jira_connection(jira_config)

        assert result.is_failure
        assert result.error == error

    def test_uses_correct_authentication_method(self, jira_config):
        create_jira_connection(jira_config)

        call_args = self.mock_jira.call_args[1]
        assert call_args["basic_auth"] == (jira_config.JIRA_EMAIL, jira_config.JIRA_TOKEN)

    @pytest.mark.parametrize(
        "server_format",
        ["test.atlassian.net", "https://test.atlassian.net", "http://test.atlassian.net"],
    )
    def test_handles_various_server_url_formats(self, config, server_format):
        config["JIRA_SERVER"] = server_format
        jira_config = JiraConfig.from_dict(config)

        result = create_jira_connection(jira_config)

        assert result.is_success
        self.mock_jira.assert_called_once_with(**self.expected_call_args(jira_config))

    def test_preserves_original_config_object(self, config):
        original_token = config["JIRA_TOKEN"]
        jira_config = JiraConfig.from_dict(config)

        create_jira_connection(jira_config)

        assert jira_config.JIRA_TOKEN == original_token
