import pytest

from dzira.core.models_rop import JiraConfig


class TestJiraConfig:
    def test_creates_config_with_all_fields(self):
        config = JiraConfig(
            server="https://company.atlassian.net", email="user@example.com", token="abc123"
        )

        assert config.server == "https://company.atlassian.net"
        assert config.email == "user@example.com"
        assert config.token == "abc123"

    def test_equality(self):
        config1 = JiraConfig("server", "email", "token")
        config2 = JiraConfig("server", "email", "token")
        config3 = JiraConfig("different", "email", "token")

        assert config1 == config2
        assert config1 != config3

    def test_repr(self):
        config = JiraConfig("server", "email", "token")
        expected = "JiraConfig(server='server', email='email', token='token')"

        assert repr(config) == expected

    @pytest.mark.parametrize(
        "args",
        [
            {},
            {"server": "SERVER"},
            {"email": "EMAIL"},
            {"token": "TOKEN"},
            {"server": "SERVER", "email": "EMAIL"},
            {"server": "SERVER", "token": "TOKEN"},
            {"email": "EMAIL", "token": "TOKEN"},
        ],
    )
    def test_requires_all_fields(self, args):
        with pytest.raises(TypeError):
            JiraConfig(*args)
