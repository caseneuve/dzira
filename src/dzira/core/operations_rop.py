from __future__ import annotations

from jira import JIRA

from .models_rop import JiraConfig
from .result import safe


@safe
def create_jira_connection(config: JiraConfig) -> JIRA:
    return JIRA(
        server=f"https://{config.JIRA_SERVER}", basic_auth=(config.JIRA_EMAIL, config.JIRA_TOKEN)
    )
