from itertools import combinations
from unittest.mock import patch

import pytest

from dzira.core.models_rop import JiraConfig


EXAMPLE_DATA = dict(
    JIRA_SERVER="company.atlassian.net",
    JIRA_EMAIL="user@example.com",
    JIRA_TOKEN="abc123",
    JIRA_PROJECT_KEY="FOO"
)


class TestJiraConfig:
    def test_creates_config_with_all_fields(self):
        config = JiraConfig(**EXAMPLE_DATA)

        assert config.JIRA_SERVER == EXAMPLE_DATA["JIRA_SERVER"]
        assert config.JIRA_EMAIL == EXAMPLE_DATA["JIRA_EMAIL"]
        assert config.JIRA_TOKEN == EXAMPLE_DATA["JIRA_TOKEN"]
        assert config.JIRA_PROJECT_KEY == EXAMPLE_DATA["JIRA_PROJECT_KEY"]

    def test_equality(self):
        config1 = JiraConfig(**EXAMPLE_DATA)
        config2 = JiraConfig(**EXAMPLE_DATA)
        config3 = JiraConfig(**{**EXAMPLE_DATA, "JIRA_EMAIL": "other@email.com"})

        assert config1 == config2
        assert config1 != config3

    @pytest.mark.parametrize(
        "args",
        [
            {k: EXAMPLE_DATA[k] for k in combo}
            for r in range(0, len(EXAMPLE_DATA))
            for combo in combinations(EXAMPLE_DATA.keys(), r)
        ]
    )
    def test_requires_all_fields(self, args):
        with pytest.raises(TypeError):
            JiraConfig(*args)

    def test_from_dict_method_is_safe_for_data_with_other_keys(self):
        extended_data = {**EXAMPLE_DATA, "extra": "key"}

        assert JiraConfig.from_dict(extended_data) == JiraConfig(**EXAMPLE_DATA)  # should not raise

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
    def test_validates_server_and_email(self, mock_sanitize_server, mock_validate_email):
        config = JiraConfig(**EXAMPLE_DATA)

        mock_sanitize_server.assert_called_once()
        assert config.JIRA_SERVER == mock_sanitize_server.return_value
        mock_validate_email.assert_called_once()
        assert config.JIRA_EMAIL == mock_validate_email.return_value
