from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class JiraConfig:
    JIRA_SERVER: str
    JIRA_EMAIL: str
    JIRA_TOKEN: str
    JIRA_PROJECT_KEY: str

    def __post_init__(self):
        self.JIRA_SERVER = self._sanitize_server(self.JIRA_SERVER)
        self.JIRA_EMAIL = self._validate_email(self.JIRA_EMAIL)

    @classmethod
    def from_dict(cls, config: dict) -> JiraConfig:
        return cls(
            JIRA_SERVER=config["JIRA_SERVER"],
            JIRA_EMAIL=config["JIRA_EMAIL"],
            JIRA_TOKEN=config["JIRA_TOKEN"],
            JIRA_PROJECT_KEY=config["JIRA_PROJECT_KEY"],
        )

    @staticmethod
    def _sanitize_server(server):
        server = re.sub(r"^https?://", "", server)
        if not server or " " in server or "." not in server:
            raise ValueError(f"Invalid server name: {server!r}")
        return server

    @staticmethod
    def _validate_email(email):
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            raise ValueError(f"Invalid email: {email}")
        return email.lower()
