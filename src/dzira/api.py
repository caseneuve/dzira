from jira import JIRA


def connect_to_jira(server: str, email: str, token: str) -> JIRA:
    return JIRA(server=f"https://{server}", basic_auth=(email, token))
