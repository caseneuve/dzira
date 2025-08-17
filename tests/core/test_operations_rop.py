from unittest.mock import Mock, patch

import pytest
from jira import JIRA
from jira.exceptions import JIRAError

from dzira.betterdict import D
from dzira.core.models_rop import JiraConfig
from dzira.core.operations_rop import create_jira_connection
from dzira.core.result import Result


@pytest.fixture(scope="class")
def mock_jira():
    with patch("dzira.core.operations_rop.JIRA") as mock:
        mock_client = Mock(spec=JIRA)
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def config_with_jira_config(config):
    jira_config = JiraConfig.from_dict(config)
    return D({"jira_config": jira_config})


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

    def test_returns_result_type(self, config_with_jira_config):
        result = create_jira_connection(config_with_jira_config)

        assert isinstance(result, Result)
        assert hasattr(result, "is_success")
        assert hasattr(result, "is_failure")

    def test_success_with_valid_config(self, config_with_jira_config):
        result = create_jira_connection(config_with_jira_config)

        assert result.is_success and result.value
        assert result.value.jira_config == config_with_jira_config.jira_config
        assert hasattr(result.value, "jira")
        self.mock_jira.assert_called_once_with(
            **self.expected_call_args(config_with_jira_config.jira_config)
        )

    def test_success_preserves_existing_config_data(self, config_with_jira_config):
        config_with_extra = config_with_jira_config.assoc("extra_key", "extra_value")

        result = create_jira_connection(config_with_extra)

        assert result.is_success and result.value
        assert result.value.extra_key == "extra_value"
        assert result.value.jira_config == config_with_extra.jira_config

    def test_success_with_sanitized_server_url(self, config):
        config["JIRA_SERVER"] = "https://test.atlassian.net"
        jira_config = JiraConfig.from_dict(config)
        config_d = D({"jira_config": jira_config})

        result = create_jira_connection(config_d)

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
    def test_failure_scenarios(self, config_with_jira_config, exception, message):
        error = exception(message)
        self.mock_jira.side_effect = error

        result = create_jira_connection(config_with_jira_config)

        assert result.is_failure
        assert result.error == error

    def test_uses_correct_authentication_method(self, config_with_jira_config):
        create_jira_connection(config_with_jira_config)

        call_args = self.mock_jira.call_args[1]
        assert call_args["basic_auth"] == (
            config_with_jira_config.jira_config.JIRA_EMAIL,
            config_with_jira_config.jira_config.JIRA_TOKEN,
        )

    @pytest.mark.parametrize(
        "server_format",
        ["test.atlassian.net", "https://test.atlassian.net", "http://test.atlassian.net"],
    )
    def test_handles_various_server_url_formats(self, config, server_format):
        config["JIRA_SERVER"] = server_format
        jira_config = JiraConfig.from_dict(config)
        config_d = D({"jira_config": jira_config})

        result = create_jira_connection(config_d)

        assert result.is_success
        self.mock_jira.assert_called_once_with(**self.expected_call_args(jira_config))

    def test_preserves_original_config_object(self, config):
        original_token = config["JIRA_TOKEN"]
        jira_config = JiraConfig.from_dict(config)
        config_d = D({"jira_config": jira_config})

        create_jira_connection(config_d)

        assert config_d.jira_config.JIRA_TOKEN == original_token

    def test_raises_assertion_error_when_jira_config_missing(self):
        config_without_jira = D({"other_key": "other_value"})

        result = create_jira_connection(config_without_jira)

        assert result.is_failure
        assert isinstance(result.error, KeyError)

    def test_raises_assertion_error_when_jira_config_wrong_type(self):
        config_with_wrong_type = D({"jira_config": "not a JiraConfig object"})

        result = create_jira_connection(config_with_wrong_type)

        assert result.is_failure
        assert isinstance(result.error, AssertionError)
