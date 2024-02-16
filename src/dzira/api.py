from __future__ import annotations

from datetime import datetime, timedelta

from jira import JIRA, Issue
from jira.resources import Board, Sprint, Worklog


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


def get_current_user_id(jira: JIRA):
    return jira.current_user()


def get_current_user_name(jira: JIRA):
    return jira.current_user("displayName")


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


def log_work(
        jira: JIRA,
        issue: str,
        seconds: int,
        comment: str | None = None,
        date: datetime | None = None
) -> Worklog:
    if seconds < (5 * 60):
        raise ValueError(f"{seconds} seconds is too low to log")
    return jira.add_worklog(
        issue=issue, timeSpentSeconds=int(seconds), comment=comment, started=date
    )


def get_worklog(jira: JIRA, issue: str, worklog_id: str) -> Worklog:
    return jira.worklog(issue=issue, id=worklog_id)


def get_issues_by_work_logged_on_date(jira: JIRA, report_date: datetime | None = None):
    if report_date is not None:
        query = f"worklogDate = {report_date:%Y-%m-%d}"
    else:
        query = f"worklogDate >= startOfDay()"
    return jira.search_issues(query)


def get_issue_worklogs_by_user_and_date(
        issue: Issue, user_email: str, report_date: datetime
) -> list:
    worklogs = issue.fields.worklog.worklogs
    report_date = report_date.astimezone()

    matching = []
    for worklog in worklogs:
        started = datetime.strptime(worklog.started, "%Y-%m-%dT%H:%M:%S.%f%z")
        if worklog.author.emailAddress == user_email and (
                report_date <= started < report_date + timedelta(days=1)
        ):
            matching.append(worklog)

    return matching



# get issues from backlog:
# jira.search_issues(jql_str="project = 'PA' AND sprint is empty")
