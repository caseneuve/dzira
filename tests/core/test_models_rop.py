from itertools import combinations
from unittest.mock import patch

import pytest

from dzira.core.models_rop import JiraConfig


@pytest.fixture
def incomplete_configs(config):
    return [
        {k: config[k] for k in combo}
        for r in range(0, len(config))
        for combo in combinations(config.keys(), r)
    ]


class TestJiraConfig:
    def test_creates_config_with_all_fields(self, config):
        jira_config = JiraConfig(**config)

        assert jira_config.JIRA_SERVER in config["JIRA_SERVER"]
        assert jira_config.JIRA_EMAIL == config["JIRA_EMAIL"].lower()
        assert jira_config.JIRA_TOKEN == config["JIRA_TOKEN"]
        assert jira_config.JIRA_PROJECT_KEY == config["JIRA_PROJECT_KEY"]

    def test_equality(self, config):
        config1 = JiraConfig(**config)
        config2 = JiraConfig(**config)
        config3 = JiraConfig(**{**config, "JIRA_EMAIL": "other@email.com"})

        assert config1 == config2
        assert config1 != config3

    def test_requires_all_fields(self, incomplete_configs):
        for args in incomplete_configs:
            with pytest.raises(TypeError):
                JiraConfig(**args)

    def test_from_dict_method_is_safe_for_data_with_other_keys(self, config):
        extended_data = {**config, "extra": "key"}

        assert JiraConfig.from_dict(extended_data) == JiraConfig(**config)  # should not raise

    @pytest.mark.parametrize("protocol", ("https", "http"))
    def test_removes_protocol_from_server(self, protocol):
        assert JiraConfig._sanitize_server(f"{protocol}://foo.bar.baz") == "foo.bar.baz"

    @pytest.mark.parametrize("name", ("foo bar baz", "foobarbaz", ""))
    def test_raises_for_invalid_server_names(self, name):
        with pytest.raises(ValueError) as exc:
            JiraConfig._sanitize_server(name)
        assert "Invalid server name" in str(exc)

    @pytest.mark.parametrize("email", ("foO@BaR.cOm", "foo@bar.com", "FOO@BAR.COM"))
    def test_sanitizes_email(self, email):
        assert JiraConfig._validate_email(email) == "foo@bar.com"

    @pytest.mark.parametrize("email", ("foo bar baz", "foobarbaz", "", "foo@bar", "foo.bar"))
    def test_raises_for_invalid_email(self, email):
        with pytest.raises(ValueError) as exc:
            JiraConfig._validate_email(email)
        assert "Invalid email" in str(exc)

    @patch("dzira.core.models_rop.JiraConfig._validate_email")
    @patch("dzira.core.models_rop.JiraConfig._sanitize_server")
    def test_validates_server_and_email(self, mock_sanitize_server, mock_validate_email, config):
        jira_config = JiraConfig(**config)

        mock_sanitize_server.assert_called_once()
        assert jira_config.JIRA_SERVER == mock_sanitize_server.return_value
        mock_validate_email.assert_called_once()
        assert jira_config.JIRA_EMAIL == mock_validate_email.return_value
