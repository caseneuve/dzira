from datetime import datetime, timedelta
from typing import List, Optional

from jira import JIRA
from jira.resources import (
    Board   as JiraBoard,
    Sprint  as JiraSprint,
    Issue   as JiraIssue,
    Worklog as JiraWorklog,
)

from .models import User, Board, Sprint, Issue, Worklog, WorklogEntry
from .result import Result, success, failure, safe


# Connection


def create_jira_connection(
    server: str, email: str, token: str
) -> Result[JIRA, Exception]:
    return safe(
        lambda: JIRA(server=f"https://{server}", basic_auth=(email, token))
    )().with_data(server=server)


# Raw API calls
def fetch_current_user(jira):
    return jira.current_user()


def fetch_user_display_name(jira):
    return jira.current_user("displayName")


def fetch_boards(jira, project):
    return jira.boards(projectKeyOrID=project)


def fetch_sprints(jira, board_id, state=None):
    return jira.sprints(board_id=board_id, state=state)


def fetch_sprint(jira, sprint_id):
    return jira.sprint(sprint_id)


def fetch_issue(jira, issue_key, fields=None):
    return jira.issue(issue_key, fields=fields)


def fetch_worklogs(jira, issue_id):
    return jira.worklogs(issue_id)


def search_issues(jira, jql, fields=None):
    """Search issues - unified implementation."""
    return list(jira.search_issues(jql_str=jql, fields=fields))


# Worklog operations
def add_worklog(jira, issue, time_seconds, comment, started):
    return jira.add_worklog(
        issue=issue,
        timeSpentSeconds=int(time_seconds),
        comment=comment,
        started=started,
    )


def fetch_worklog(jira, issue, worklog_id):
    return jira.worklog(issue=issue, id=worklog_id)


# Conversion functions


def convert_user(user_id: str, display_name: str) -> User:
    return User(id=user_id, display_name=display_name)


def convert_board(jira_board: JiraBoard, project_key: str) -> Board:
    return Board(id=jira_board.id, name=jira_board.name, project_key=project_key)


def convert_sprint(jira_sprint: JiraSprint) -> Sprint:
    start_date = None
    end_date = None

    if hasattr(jira_sprint, "startDate") and jira_sprint.startDate:
        try:
            start_date = datetime.fromisoformat(
                jira_sprint.startDate.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            pass

    if hasattr(jira_sprint, "endDate") and jira_sprint.endDate:
        try:
            end_date = datetime.fromisoformat(
                jira_sprint.endDate.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            pass

    return Sprint(
        id=jira_sprint.id,
        name=jira_sprint.name,
        state=getattr(jira_sprint, "state", "unknown"),
        start_date=start_date,
        end_date=end_date,
    )


def convert_issue(jira_issue: JiraIssue) -> Issue:
    sprint_info_dict = {}

    if (
        hasattr(jira_issue.fields, "customfield_10121")
        and jira_issue.fields.customfield_10121
    ):
        sprint_info = jira_issue.fields.customfield_10121
        if isinstance(sprint_info, list) and sprint_info:
            sprint_info_dict = vars(sprint_info[0])

    elif hasattr(jira_issue.fields, "Sprint") and jira_issue.fields.Sprint:
        sprint_info = jira_issue.fields.Sprint
        print(f"Sprint {sprint_info=}")
        if isinstance(sprint_info, list) and sprint_info:
            sprint_info_dict["id"] = getattr(sprint_info[0], "id", None)

    elif (
        hasattr(jira_issue.fields, "customfield_10020")
        and jira_issue.fields.customfield_10020
    ):
        sprint_info = jira_issue.fields.customfield_10020
        if isinstance(sprint_info, list) and sprint_info:
            sprint_info_dict["id"] = getattr(sprint_info[0], "id", None)

    time_spent_display = None
    time_remaining_estimate = None
    time_original_estimate = None

    if hasattr(jira_issue.fields, "timetracking") and jira_issue.fields.timetracking:
        timetracking = jira_issue.fields.timetracking
        if hasattr(timetracking, "raw") and timetracking.raw:
            time_spent_display = timetracking.raw.get("timeSpent")

        time_remaining_estimate = getattr(timetracking, "remainingEstimate", None)
        time_original_estimate = getattr(timetracking, "originalEstimate", None)

    return Issue(
        key=jira_issue.key,
        summary=jira_issue.fields.summary,
        status=jira_issue.fields.status.name,
        sprint_info= sprint_info_dict,
        time_spent_seconds=getattr(jira_issue.fields, "timespent", None),
        time_spent_display=time_spent_display,
        time_estimate_seconds=getattr(jira_issue.fields, "timeoriginalestimate", None),
        time_remaining_estimate=time_remaining_estimate,
        time_original_estimate=time_original_estimate,
    )


def convert_worklog(jira_worklog: JiraWorklog, issue_key: str) -> Worklog:
    return Worklog(
        id=jira_worklog.id,
        issue_key=issue_key,
        time_spent_seconds=jira_worklog.raw.get("timeSpentSeconds", 0),
        comment=jira_worklog.raw.get("comment"),
        started=(
            datetime.fromisoformat(jira_worklog.started.replace("Z", "+00:00"))
            if hasattr(jira_worklog, "started")
            else datetime.now()
        ),
        author_email=(
            getattr(jira_worklog.author, "emailAddress", "")
            if hasattr(jira_worklog, "author")
            else ""
        ),
    )


# Business operations


def get_current_user(jira: JIRA) -> Result[User, Exception]:
    user_id_result: Result = safe(fetch_current_user)(jira)
    display_name_result: Result = safe(fetch_user_display_name)(jira)

    if user_id_result.is_failure:
        return user_id_result
    if display_name_result.is_failure:
        return display_name_result

    return success(
        convert_user(
            str(user_id_result.value),
            str(display_name_result.value)
        )
    )


def get_board_by_key(jira: JIRA, project_key: str) -> Result[Board, Exception]:
    return (
        safe(fetch_boards)(jira, project_key)
        .bind(lambda boards: _validate_single_board(boards, project_key))
        .map(lambda board: convert_board(board, project_key))
    )


def get_sprints_by_board(
    jira: JIRA, board: Board, state: Optional[str] = None
) -> Result[List[Sprint], Exception]:
    return safe(fetch_sprints)(
        jira, board.id, state
    ).map(
        lambda sprints: [convert_sprint(sprint) for sprint in sprints]
    )


def get_sprint_by_id(jira: JIRA, sprint_id: int) -> Result[Sprint, Exception]:
    return safe(fetch_sprint)(
        jira, sprint_id
    ).map(convert_sprint)


def get_sprint_issues(jira: JIRA, sprint: Sprint) -> Result[List[Issue], Exception]:
    jql = f"Sprint = {sprint.id}"
    return safe(search_issues)(jira, jql).map(
        lambda issues: [convert_issue(issue) for issue in issues]
    )


def get_issues_by_sprint_state(
    jira: JIRA, project_key: str, state: str
) -> Result[List[Issue], Exception]:
    sprint_functions = {
        "active": "openSprints()",
        "future": "futureSprints()",
        "closed": "closedSprints()",
    }
    jql = f"project = {project_key!r} AND sprint in {sprint_functions[state]}"

    # ===================================================================
    # TODO: fields should be injected, so one could prepend custom fields
    # ===================================================================
    fields = "customfield_10121,status,summary,timespent,timeestimate,timetracking"

    return safe(search_issues)(
        jira, jql, fields
    ).map(
        lambda issues: [convert_issue(issue) for issue in issues]
    )


# Convenience functions for backward compatibility
def get_current_sprint_issues(
    jira: JIRA, project_key: str
) -> Result[List[Issue], Exception]:
    """Get issues in active sprints."""
    return get_issues_by_sprint_state(jira, project_key, "active")


def get_future_sprint_issues(
    jira: JIRA, project_key: str
) -> Result[List[Issue], Exception]:
    """Get issues in future sprints."""
    return get_issues_by_sprint_state(jira, project_key, "future")


def get_closed_sprint_issues(
    jira: JIRA, project_key: str
) -> Result[List[Issue], Exception]:
    """Get issues in closed sprints."""
    return get_issues_by_sprint_state(jira, project_key, "closed")


def search_issues_with_sprint_info(
    jira: JIRA,
    project_key: str,
    state: str = "active",
    sprint_id: Optional[str] = None,
    extra_fields: Optional[List[str]] = None,
) -> Result[List[Issue], Exception]:
    # Build JQL query
    if sprint_id:
        jql = f"sprint = {sprint_id}"
    else:
        sprint_fn = {
            "active": "openSprints()",
            "closed": "closedSprints()",
            "future": "futureSprints()",
        }[state]
        jql = f"project = {project_key} AND sprint in {sprint_fn}"

    # Build fields
    default_fields = [
        "customfield_10121,Sprint,status,summary,timespent,timeestimate,timetracking"
    ]
    fields = ",".join((extra_fields or []) + default_fields)

    return safe(search_issues)(jira, jql, fields).map(
        lambda issues: [convert_issue(issue) for issue in issues]
    )


def get_issues_by_work_logged_on_date(
    jira: JIRA, project_key: str, report_date: Optional[datetime] = None
) -> Result[List[Issue], Exception]:
    """Get issues with work logged on specific date."""
    if report_date is not None:
        date_query = f"worklogDate = {report_date:%Y-%m-%d}"
    else:
        date_query = "worklogDate >= startOfDay()"

    jql = f"{date_query} AND project = {project_key!r}"
    return safe(search_issues)(jira, jql, "worklog,summary").map(
        lambda issues: [convert_issue(issue) for issue in issues]
    )


def log_work(jira: JIRA, entry: WorklogEntry) -> Result[Worklog, Exception]:
    """Create worklog entry."""
    if entry.time_spent_seconds < (5 * 60):
        return failure(
            ValueError(f"{entry.time_spent_seconds} seconds is too low to log")
        )

    return safe(add_worklog)(
        jira, entry.issue_key, entry.time_spent_seconds, entry.comment, entry.started
    ).map(lambda worklog: convert_worklog(worklog, entry.issue_key))


def get_worklog(
    jira: JIRA, issue_key: str, worklog_id: str
) -> Result[Worklog, Exception]:
    """Get specific worklog."""
    return safe(fetch_worklog)(jira, issue_key, worklog_id).map(
        lambda worklog: convert_worklog(worklog, issue_key)
    )


def get_issue_worklogs_by_user_and_date(
    jira: JIRA, issue: Issue, user_email: str, report_date: datetime
) -> Result[List[Worklog], Exception]:
    """Get worklogs for issue by user and date."""
    return (
        safe(fetch_issue)(jira, issue.key, "worklog")
        .bind(lambda jira_issue: _get_worklogs_from_issue(jira, jira_issue))
        .map(
            lambda worklogs: _filter_worklogs_by_user_and_date(
                worklogs, user_email, report_date, issue.key
            )
        )
    )


# Helper functions


def _validate_single_board(
    boards: List[JiraBoard], project_key: str
) -> Result[JiraBoard, Exception]:
    if len(boards) > 1:
        board_names = [b.raw["location"]["displayName"] for b in boards]
        return failure(
            Exception(
                f"Found more than one board matching {project_key!r}:\n{', '.join(board_names)}"
            )
        )
    return success(boards[0])


def _get_worklogs_from_issue(
    jira: JIRA, jira_issue: JiraIssue
) -> Result[List[JiraWorklog], Exception]:
    try:
        worklog_count = len(jira_issue.fields.worklog.worklogs)
    except (AttributeError, TypeError):
        return success([])

    if worklog_count == 0:
        return success([])
    elif worklog_count < 20:
        return success(jira_issue.fields.worklog.worklogs)
    else:
        return safe(fetch_worklogs)(jira, jira_issue.id)


def _filter_worklogs_by_user_and_date(
    worklogs: List[JiraWorklog], user_email: str, report_date: datetime, issue_key: str
) -> List[Worklog]:
    report_date = report_date.astimezone()
    matching = []

    for worklog in worklogs:
        started = datetime.strptime(worklog.started, "%Y-%m-%dT%H:%M:%S.%f%z")
        if (
            worklog.author.emailAddress == user_email
            and report_date <= started < report_date + timedelta(days=1)
        ):
            matching.append(convert_worklog(worklog, issue_key))

    return matching
