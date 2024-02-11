from jira import JIRA
from jira.resources import Board, Sprint


def connect_to_jira(server: str, email: str, token: str) -> JIRA:
    return JIRA(server=f"https://{server}", basic_auth=(email, token))


def get_board_by_key(jira: JIRA, key: str) -> Board:
    boards = jira.boards(projectKeyOrID=key)
    if len(boards) > 1:
        raise Exception(
            f"Found more than one board matching {key!r}:\n"
            f"{', '.join(b.raw['location']['displayName'] for b in boards)}"
        )
    return boards[0]


def get_sprints_by_board(jira: JIRA, board: Board, state: str | None = None) -> list:
    return jira.sprints(board_id=board.id, state=state)


def get_sprint_by_id(jira: JIRA, sprint_id: int) -> Sprint:
    return jira.sprint(sprint_id)


def get_sprint_issues(jira: JIRA, sprint: Sprint) -> list:
    return list(jira.search_issues(jql_str=f"Sprint = {sprint.id}"))


def get_current_sprint_issues(jira: JIRA, project_key: str) -> list:
    return list(
        jira.search_issues(jql_str=f"project = {project_key!r} AND sprint in openSprints()")
    )


def get_future_sprint_issues(jira: JIRA, project_key: str) -> list:
    return list(
        jira.search_issues(jql_str=f"project = {project_key!r} AND sprint in futureSprints()")
    )


def get_closed_sprints_issues(jira: JIRA, project_key: str) -> list:
    return list(
        jira.search_issues(jql_str=f"project = {project_key!r} AND sprint in closedSprints()")
    )
