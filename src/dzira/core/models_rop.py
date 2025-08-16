from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JiraConfig:
    JIRA_SERVER: str
    JIRA_EMAIL: str
    JIRA_TOKEN: str
    JIRA_PROJECT_KEY: str

    @classmethod
    def from_dict(cls, config: dict) -> JiraConfig:
        return cls(
            JIRA_SERVER=config["JIRA_SERVER"],
            JIRA_EMAIL=config["JIRA_EMAIL"],
            JIRA_TOKEN=config["JIRA_TOKEN"],
            JIRA_PROJECT_KEY=config["JIRA_PROJECT_KEY"],
        )
