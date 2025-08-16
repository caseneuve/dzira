import pytest

from dzira.core.models_rop import JiraConfig
from tests.factories import JiraConfigFactory


@pytest.fixture
def config():
    return JiraConfigFactory()


@pytest.fixture
def jira_config(config):
    return JiraConfig.from_dict(config)
