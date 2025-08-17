from __future__ import annotations

from jira import JIRA

from ..betterdict import D
from .models_rop import JiraConfig
from .result import safe


@safe
def create_jira_connection(config: D) -> D:
    assert isinstance(jc := config.jira_config, JiraConfig)
    return config.assoc(
        "jira",
        JIRA(server=f"https://{jc.JIRA_SERVER}", basic_auth=(jc.JIRA_EMAIL, jc.JIRA_TOKEN))
    )
