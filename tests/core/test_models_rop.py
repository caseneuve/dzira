from itertools import combinations

import pytest

from dzira.core.models_rop import JiraConfig


EXAMPLE_DATA = dict(
    JIRA_SERVER="https://company.atlassian.net",
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
        config1 = JiraConfig("server", "email", "token", "project")
        config2 = JiraConfig("server", "email", "token", "project")
        config3 = JiraConfig("server", "different", "token", "project")

        assert config1 == config2
        assert config1 != config3

    def test_repr(self):
        config = JiraConfig("server", "email", "token", "project")
        expected = "JiraConfig(JIRA_SERVER='server', JIRA_EMAIL='email', JIRA_TOKEN='token', JIRA_PROJECT_KEY='project')"

        assert repr(config) == expected

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
