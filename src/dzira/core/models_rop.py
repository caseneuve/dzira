from dataclasses import dataclass


@dataclass
class JiraConfig:
    server: str
    email: str
    token: str
