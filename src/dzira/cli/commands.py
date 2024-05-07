from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

import click
from jira import JIRA
from jira.resources import Board, Sprint, Worklog
from tabulate import tabulate

from dzira import api
from dzira.betterdict import D
from dzira.cli.output import (
    Colors,
    Result,
    Spinner,
    hide_cursor,
    show_cursor,
)
from .config import (
    DEFAULT_OUTPUT_FORMAT,
    VALID_OUTPUT_FORMATS,
    get_config,
)


colors = Colors()
c = colors.c
spinner = Spinner(c)


##################################################
#  JIRA wrapper
##################################################


@spinner.run("Getting client")
def get_jira(config: D) -> Result:
    server, email, token = config("JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN")
    msg = f"connecting to {server}"
    jira: JIRA = api.connect_to_jira(server, email, token)
    return Result(stdout=msg, result=jira)


@spinner.run("Getting board")
def get_board(jira: JIRA, key: str) -> Result:
    board: Board = api.get_board_by_key(jira, key)
    return Result(
        result=board,
        stdout=f'{board.raw["location"]["displayName"]}'
    )


# TODO: -> move to data
def process_sprint_out(sprint: Sprint | D) -> str:
    fmt = lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%a, %b %d")
    return f"{sprint.name} • id: {sprint.id} • {fmt(sprint.startDate)} -> {fmt(sprint.endDate)}"


@spinner.run("Getting sprint")
def get_sprint(jira: JIRA, payload: D) -> Result:
    sprint_id, board, state = payload("sprint_id", "board", "state")
    try:
        warning = ""
        if sprint_id:
            sprint = api.get_sprint_by_id(jira, sprint_id)
        else:
            sprints = api.get_sprints_by_board(jira, board, state)
            if len(sprints) > 1:
                warning = f" (showing most recent sprint matching {state!r})"
            sprint = sprints[-1]
    except:
        raise Exception("Could not find sprint matching given criteria")
    out = process_sprint_out(sprint)
    return Result(result=sprint, stdout=f"{out}{warning}")


@spinner.run("Adding worklog")
def add_worklog(
        jira: JIRA,
        issue: str,
        seconds: int,
        comment: str | None = None,
        date: datetime | None = None,
        **_
) -> Result:
    work_log: Worklog = api.log_work(jira, issue, seconds, comment, date)
    return Result(
        stdout=(
            f"spent {work_log.raw['timeSpent']} in {issue} "
            f"[worklog {work_log.id}] at {datetime.now():%H:%M:%S}"
        )
    )


@spinner.run("Getting worklog")
def get_worklog(jira: JIRA, issue: str, worklog_id: str | int, **_) -> Result:
    work_log: Worklog = api.get_worklog(jira, issue=issue, worklog_id=str(worklog_id))
    created = datetime.strptime(
        work_log.created, "%Y-%m-%dT%H:%M:%S.%f%z"
    ).astimezone().strftime("%a, %b %d, %H:%M:%S")
    author = work_log.author.displayName
    return Result(result=work_log, stdout=f"{work_log.id}, created by {author} on {created}")


def _update_worklog(
        worklog: Worklog, time: str | None, comment: str | None, date: datetime | None
) -> D:
    if not (time or comment):
        raise Exception(
            "at least one of <time> or <comment> fields needed to perform the update!"
        )
    fields = {
        k: v
        for k, v in zip(["timeSpentSeconds", "comment", "started"], [time, comment, date])
        if v
    }
    worklog.update(fields=fields)
    return D(fields)


# TODO: we can't update worklog to change the issue
# * add delete option to worklog !!!
@spinner.run("Updating worklog")
def update_worklog(
        worklog: Worklog, time: str, comment: str, date: datetime | None = None, **_
) -> Result:
    info = _update_worklog(worklog, time, comment, date)
    for k in info.copy():
        if k == "timeSpentSeconds":
            info.pop(k)
            k = "timeSpent"
        info.update(k, worklog.raw[k])
    return Result(stdout=f"updated: {info}")


##################################################
#  CLI wrapper
##################################################


def set_spinner_use(with_spinner: bool):
    spinner.use = with_spinner and sys.stdin.isatty()


def set_color_use(with_color: bool):
    colors.use = with_color and sys.stdin.isatty()


@click.group()
@click.option("-f", "--file", help=f"Config file path", type=click.Path())
@click.option("-k", "--key", help="JIRA_PROJECT_KEY value", envvar="JIRA_PROJECT_KEY")
@click.option("-t", "--token", help="JIRA_TOKEN value", envvar="JIRA_TOKEN")
@click.option("-m", "--email", help="JIRA_EMAIL value", envvar="JIRA_EMAIL")
@click.option("-s", "--server", help="JIRA_SERVER value", envvar="JIRA_SERVER")
@click.option("--spin/--no-spin", help="Control the spinner", default=True, show_default=True)
@click.option("--color/--no-color", help="Control colors", default=True, show_default=True)
@click.help_option("-h", "--help", help="Show this message and exit")
@click.version_option(help="Show the version and exit")
@click.pass_context
def cli(ctx, file, key, token, email, server, spin, color):
    """
    Configure JIRA connection by using default config files, environment
    variables, or options below. The discovery of default config files uses
    paths in the following order:

    \b
    - $XDG_CONFIG_HOME or $HOME/dzira/env
    - $XDG_CONFIG_HOME or $HOME/.dzira
    - $HOME/.config/dzira/env
    - $HOME/.config/.dzira

    Configuration requires setting values for:

    \b
    - JIRA_SERVER (the servers where your Jira instance is hosted on),
    - JIRA_EMAIL (the email you use to log into Jira),
    - JIRA_TOKEN (your Jira token),
    - JIRA_PROJECT_KEY (your team's project key)
    """
    set_spinner_use(spin)
    set_color_use(color)

    ctx.ensure_object(dict)
    cfg = {
        k: v
        for k, v in dict(
                file=file,
                JIRA_EMAIL=email,
                JIRA_PROJECT_KEY=key,
                JIRA_SERVER=server,
                JIRA_TOKEN=token,
        ).items()
        if v is not None
    }
    ctx.obj.update(cfg)


##################################################
#  LS command
##################################################

# TODO:
# add --sprints/--issues
# return {sprints: [], issues: []} and process accordingly
# jira.sprints(board_id) -> need board OR jira.sprint(id) or sprint_info(sprint_id=id)


@spinner.run("Getting issues")
def get_issues(jira: JIRA, payload: D) -> Result:
    project_key, sprint_id, state = payload("JIRA_PROJECT_KEY", "sprint_id", ("state", "active"))
    issues: list = api.search_issues_with_sprint_info(
        jira, project_key=project_key, sprint_id=sprint_id, state=state
    )
    if issues:
        # TODO: should use func from dzira.data
        sprint_info = D(issues[0].raw["fields"]["Sprint"][0])
        out = process_sprint_out(sprint_info)
    else:
        out = "No issues found"
        sprint_info = {}
    return Result(result=D(sprint=sprint_info, issues=issues), stdout=out)


# TODO: move data processing to data
def show_issues(sprint_and_issues: D, format: str) -> None:
    if format in ("json", "csv"):
        colors.use = False

    fmt = lambda t: str(timedelta(seconds=t)) if t else None
    state_clr = {"To Do": "^magenta", "In Progress": "^yellow", "Done": "^green"}
    clr = lambda s: c(state_clr.get(s, "^reset"), "^bold", s)

    def _estimate(i):
        try:
            remining = i.fields.timetracking.remainingEstimate
            original = i.fields.timetracking.originalEstimate
            return f"{remining} ({original})" if remining != original else original
        except Exception:
            return fmt(i.fields.timeestimate)

    headers = ["key", "summary", "state", "spent", "estimated"]
    processed_issues = [
        [
            c("^blue", i.key),
            i.fields.summary,
            clr(i.fields.status.name),
            fmt(i.fields.timespent),
            _estimate(i),
        ]
        for i in reversed(sorted(sprint_and_issues["issues"], key=lambda i: i.fields.status.name))
    ]

    if format == "json":
        sprint = sprint_and_issues["sprint"]
        json_dict = {
            "sprint": {
                "name": sprint.name,
                "id": sprint.id,
                "start": sprint.startDate,
                "end": sprint.endDate,
            },
            "issues": [dict(zip(headers, issue)) for issue in processed_issues]
        }
        print(json.dumps(json_dict))
    elif format == "csv":
        headers.insert(0, "sprint_id")
        sprint = sprint_and_issues["sprint"]
        processed_issues = [[sprint.id] + i for i in processed_issues]
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        writer.writerows([dict(zip(headers, issue)) for issue in processed_issues])
    else:
        print(
            tabulate(
                processed_issues,
                headers=headers,
                colalign=("right", "left", "left", "right", "right"),
                maxcolwidths=[None, 35, None, None, None],
                tablefmt=format,
            )
        )


def validate_output_format(_, __, value):
    if value.lower() in VALID_OUTPUT_FORMATS:
        return value.lower()
    raise click.BadParameter(f"format should be one of: {', '.join(VALID_OUTPUT_FORMATS)}")


@cli.command()
@click.pass_context
@click.option(
    "-s", "--state",
    type=click.Choice(["active", "closed", "future"]), default="active", show_default=True,
    help="Sprint state used for filtering",
)
@click.option(
    "-i", "--sprint-id",
    type=int,
    help=(
        "Sprint id to get unambiguous result, helpful when multiple active sprints; "
        "has precedence over --state"
    )
)
@click.option(
    "-f", "--format",
    default=DEFAULT_OUTPUT_FORMAT,
    show_default=True,
    help="Output format: supports TABULATE formats + CSV and JSON",
    callback=validate_output_format,
)
@click.help_option("-h", "--help")
def ls(ctx, state, sprint_id, format):
    """
    List issues from the current sprint.

    'Current sprint' is understood as the first 'active' sprint found.
    To avoid ambiguity, use --sprint-id option.

    Format can be one of supported TABULATE formats or CSV, JSON.

    Examples of parsable formats:

    \b
    CSV format:
      sprint_id,key,summary,state,spent,estimated
      42,XY-250,New feature,To Do,,4h
      42,XY-214,Upgrade foo to 9.99,In Progress,0:30:00,2d 7h 30m (3d)

    \b
    JSON format:
      {
        "sprint": {
          "name": "Iteration 42",
          "id": 42,
          "start": "2024-01-01T08:00:00.000Z",
          "end": "2024-01-14T16:00:00.000Z"
        },
        "issues": [
          {
            "key": "XY-250",
            "summary": "New feature",
            "state": "To Do",
            "spent": null,
            "estimated": 4h
          }
        ]
      }
    """
    config: D = get_config(config=ctx.obj)
    jira: JIRA = get_jira(config).result
    issues: D = get_issues(jira, D(state=state, sprint_id=sprint_id, **config)).result
    show_issues(issues, format=format)


##################################################
#  LOG command
##################################################

### Validators

def matches_time_re(time: str) -> D:
    """
    Allows strings '[h][ [m]]' with or without format indicators 'h/m',
    not greater than 8h 59m, or only minutes not greater than 499m.
    """
    only_mins = re.compile(r"^(?P<m>(\d{2}|[1-4]\d{2}))m$")
    hours_and_mins = re.compile(r"^(?P<h>([1-8]))h(\s*(?=\d))?((?P<m>([1-5]\d|[1-9]))m?)?$")
    m = only_mins.match(time) or hours_and_mins.match(time)
    return D(m.groupdict() if m is not None else {})


def is_valid_hour(hour) -> bool:
    return re.match(r"^(([01]?\d|2[0-3])[:.h,])+([0-5]?\d)$", hour) is not None


def validate_time(_, __, time) -> int:
    if time is None:
        return 0
    if (match := matches_time_re(time)):
        return sum(int(t) * s for t, s in zip(match("h", "m"), [3600, 60]) if t)
    raise click.BadParameter(
        (
            "time cannot be greater than 8h (1 day), "
            "and has to be in format '[Nh][ N[m]]' or 'Nm', "
            "e.g. '2h', '91m', '4h 37m', '1h59'."
        )
    )


def validate_hour(ctx, param, value):
    if (
        param.name == "end"
        and value
        and not (ctx.params.get("start") or ctx.params.get("time"))
    ):
        raise click.BadParameter("start time required to process end time")
    if value is None:
        return
    if is_valid_hour(value):
        return re.sub(r"[,.h]", ":", value)
    raise click.BadParameter(
        "start/end time has to be in format '[H[H]][:.h,][M[M]]', e.g. '2h3', '12:03', '3,59'"
    )


VALIDATE_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M")


def validate_date(ctx, _, value):
    if value is None:
        return

    if re.match(r"^\d{4}-\d{2}-\d{2}$", value) and (start:=ctx.params.get("start")) is not None:
        value = f"{value} {start}"

    given_date = None
    for fmt in VALIDATE_DATE_FORMATS:
        try:
            given_date = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d":
                given_date = datetime.combine(datetime.date(given_date), datetime.now().time())
            break
        except ValueError:
            pass

    if not isinstance(given_date, datetime):
        raise click.BadParameter(
            f"date has to match one of supported ISO formats: {', '.join(VALIDATE_DATE_FORMATS)}"
        )
    now = datetime.now()
    if given_date > now:
        raise click.BadParameter("worklog date cannot be in future!")
    if (now - given_date).days > 14:
        raise click.BadParameter("worklog date cannot be older than 2 weeks!")

    if (utc_offset:=datetime.utcnow().astimezone().utcoffset()):
        return given_date - utc_offset
    else:
        return given_date


def sanitize_params(args: D) -> D:
    time, start, worklog_id, comment = args("time", "start", "worklog_id", "comment")

    if (time or start) or (worklog_id and comment):
        return calculate_seconds(args)

    if worklog_id and (comment is None):
        msg = "to update a worklog, either time spent or a comment is needed"
    else:
        msg = (
            "cannot spend without knowing working time or when work has started: \n"
            "provide valid --time or --start options"
        )
    raise click.UsageError(msg)


### Payload

def calculate_seconds(payload: D) -> D:
    start, end = payload("start", "end")

    if start is None:
        return payload.update("seconds", payload.get("time"))

    fmt = "%H:%M"
    unify = lambda t: datetime.strptime(re.sub(r"[,.h]", ":", t), fmt)
    t2 = (
        datetime.strptime(datetime.now().strftime("%H:%M"), fmt)
        if end is None else unify(end)
    )
    t1 = unify(start)

    if t2 < t1:
        raise click.BadParameter("start time cannot be later than end time")
    else:
        delta_seconds = (t2 - t1).total_seconds()
        return payload.update("seconds", int(delta_seconds))


def establish_issue(jira: JIRA, payload: D) -> D:
    key = payload["JIRA_PROJECT_KEY"]
    issue = payload.get("issue", "")

    if issue.isdigit():
        return payload.update("issue", f"{key}-{issue}")

    sprint_issues = get_issues(jira, payload).result
    candidates = [i for i in sprint_issues.issues if issue.lower() in i.fields.summary.lower()]

    if not candidates:
        raise Exception("could not find any matching issues")
    if len(candidates) > 1:
        msg = "\n".join(f" * {i.key}: {i.fields.summary}" for i in candidates)
        raise Exception("found more than one matching issue:\n" + msg)

    return payload.update("issue", candidates[0].key)


def perform_log_action(jira: JIRA, payload: D) -> None:
    if payload["worklog_id"] is not None:
        worklog: Worklog = get_worklog(jira, **payload).result
        update_worklog(worklog, **payload)
    else:
        add_worklog(jira, **payload)


@cli.command()
@click.pass_context
@click.argument("issue", required=True)
@click.option(
    "-t",
    "--time",
    help="Time to spend in JIRA accepted format, e.g. '2h 10m'",
    type=click.UNPROCESSED,
    is_eager=True,
    callback=validate_time,
)
@click.option(
    "-s",
    "--start",
    help="Time when the work started, e.g. '10:30', '12.45'",
    type=click.UNPROCESSED,
    is_eager=True,
    callback=validate_hour,
)
@click.option(
    "-e",
    "--end",
    help="Time when the work ended, e.g. '14:50', '16.10'",
    type=click.UNPROCESSED,
    callback=validate_hour,
)
@click.option(
    "-d",
    "--date",
    help=(
        "Date when the work was done in ISO format, e.g. 2023-11-24, 2023-11-24 8:19, "
        "defaults to now; "
        "when date matches %Y-%m-%d, time will be added from the --start option, if present, "
        "or current time will be used"
    ),
    type=click.UNPROCESSED,
    callback=validate_date,
)
@click.option("-c", "--comment", help="Comment added to logged time")
@click.option(
    "-w", "--worklog", "worklog_id", type=int, help="Id of the worklog to be updated"
)
@click.help_option("-h", "--help")
def log(ctx, **_):
    """
    Log time spent on ISSUE number or ISSUE with description containing
    matching string.

    TIME spent should be in format '[[Nh][ ]][Nm]'; or it can be
    calculated when START time is be provided; it's assumed that time
    spent for a single task cannot be greater than 1 day (8 hours).

    END time is optional, both should match 'H:M' format.

    Optionally a COMMENT text can be added.

    When WORKLOG id is present, it will update an existing log,
    rather then create a new one.  ISSUE is still required.

    To log work done in the past (but no older as 2 weeks), use --date option.
    It accepts the following patterns:

    \b
      "YYYY-mm-dd", "YYYY-mm-ddTHH:MM", "YYYY-mm-dd HH:MM".

    \b
    Time is calculated from the START option, if present, and date is
    not specifying it.  The script will try to figure out local
    timezone and adjust the log started time accordingly.
    """
    payload = sanitize_params(D(ctx.params))
    config = get_config(config=ctx.obj)
    jira = get_jira(config).result
    payload = establish_issue(jira, payload.update(**config))
    perform_log_action(jira, payload)


##################################################
#  REPORT command
##################################################


@spinner.run("Getting user id")
def get_user_id(jira: JIRA) -> Result:
    return Result(result=api.get_current_user_id(jira))


@spinner.run("Getting issues")
def get_issues_with_work_logged_on_date(
        jira: JIRA,
        project_key: str,
        report_date: datetime | None,
) -> Result:
    issues = api.get_issues_by_work_logged_on_date(jira, project_key, report_date)
    if report_date is None:
        report_date = datetime.combine(date.today(), datetime.min.time())
    return Result(
        result=issues,
        data=D(report_date=report_date),
        stdout=(
            f"Found {len(issues)} issue{'s' if len(issues) != 1 else ''} "
            f"with work logged on {report_date:%a, %b %d}"
        )
    )


@spinner.run("Getting worklogs")
def get_user_worklogs_from_date(jira: JIRA, user_email: str, issues: Result) -> Result:
    worklogs = D(counter=0)
    for issue in issues.result:
        report_date = issues.data.report_date
        assert type(report_date) == datetime, f"Got unexpected report_date type {type(report_date)}"
        matching: list = api.get_issue_worklogs_by_user_and_date(
            jira, issue, user_email, report_date
        )
        if matching:
            worklogs[issue.id] = D(key=issue.key, summary=issue.fields.summary, worklogs=matching)
            worklogs.update(counter=lambda x: x + (len(matching)))

    return Result(
        result=worklogs.without("counter"),
        stdout=(
            f"Found {worklogs.counter} worklog{'s' if worklogs.counter != 1 else ''} "
            "matching author and date"
        )
    )


def _seconds_to_hour_minute_fmt(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes:02}m"


# -> `data`, so it's processing data, and show_func only shows
def show_report(issues_to_worklogs: D, format: str | None) -> None:
    total_time = 0
    csv_rows = []
    json_dict = {"issues": [], "total_time": None, "total_seconds": None}
    tables = []
    for issue_id in issues_to_worklogs:
        key, summary, worklogs = issues_to_worklogs[issue_id]("key", "summary", "worklogs")
        issue_total_time = 0
        issue_worklogs = []
        for w in worklogs:
            started, time_spent, comment, time_spent_seconds = D(w.raw)(
                "started", "timeSpent", "comment", "timeSpentSeconds"
            )
            total_time += time_spent_seconds
            issue_total_time += time_spent_seconds
            local_timestamp = datetime.strptime(started, '%Y-%m-%dT%H:%M:%S.%f%z').astimezone()
            formatted_time = local_timestamp.strftime('%H:%M:%S')

            if format == "csv":
                processed_worklog = [
                    key, summary, w.id, formatted_time, time_spent, time_spent_seconds, comment
                ]
                csv_rows.append(processed_worklog)
            elif format == "json":
                processed_worklog = {
                    "id": w.id,
                    "started": local_timestamp.strftime("%H:%M:%S"),
                    "spent": time_spent,
                    "spent_seconds": time_spent_seconds,
                    "comment": comment
                }
            else:
                processed_worklog = [f"[{w.id}]", formatted_time, f":{time_spent:>6}", comment or ""]
            issue_worklogs.append(processed_worklog)

        if format == "table":
            header = c(
                "^bold", f"[{key}] {summary} ",
                "^cyan", f"({_seconds_to_hour_minute_fmt(issue_total_time)})"
            )
            tables.append((header, issue_worklogs))
        elif format == "json":
            json_dict["issues"].append(
                {
                    "key": key,
                    "summary": summary,
                    "issue_total_time": _seconds_to_hour_minute_fmt(issue_total_time),
                    "issue_total_spent_seconds": issue_total_time,
                    "worklogs": issue_worklogs
                }
            )

    if format == "csv":
        headers = ["issue", "summary", "worklog", "started", "spent", "spent_seconds", "comment"]
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        writer.writerows([dict(zip(headers, row)) for row in csv_rows])
    elif format == "json":
        json_dict["total_time"] = _seconds_to_hour_minute_fmt(total_time)
        json_dict["total_seconds"] = total_time
        print(json.dumps(json_dict))
    else:
        for header, rows in tables:
            print()
            print(header)
            print(tabulate(rows, maxcolwidths=[None, None, None, 60]))
        if tables:
            print(f"\n{c('^bold', 'Total spent time')}: {_seconds_to_hour_minute_fmt(total_time)}\n")
        else:
            print("No work logged on given date")


# TODO: add sprint option
@cli.command()
@click.pass_context
@click.option("-d", "--date", "report_date", help="Date to show report for", type=click.DateTime())
@click.option(
    "-f", "--format",
    type=click.Choice(["table", "csv", "json"]), default="table", show_default=True,
    help="How to display the report",
)
@click.help_option("-h", "--help", help="Show this message and exit")
def report(ctx, report_date, format):
    """
    Show work logged for today or for DATE using given FORMAT.

    TABLE format (default) will print a table with summary showing
    worklogs for every issue having work logged on given DATE.

    \b
    CSV format:
      issue, summary, worklog, started, spent, spent_seconds, comment
      XY-1,Foo bar,1234,12:45:00,1h 15m,4500,implementing foo in bar

    \b
    JSON format:
      {
        "issues": [
          {
            "key": "XY-1",
            "summary": "Foo bar",
            "issue_total_time": "1h 15m",
            "issue_total_spent_seconds": 4500,
            "worklogs": [
              {
                "id": "1",
                "started": "12:45:00",
                "spent": "1h 15m",
                "spent_seconds": 4500,
                "comment": "implementing foo in bar"
              }
            ]
          },
        ],
        "total_time": "1h 15m",
        "total_seconds": 4500
      }
    """
    config = get_config(config=ctx.obj)
    jira = get_jira(config).result
    issues = get_issues_with_work_logged_on_date(jira, config["JIRA_PROJECT_KEY"], report_date)
    if issues.result:
        worklogs = get_user_worklogs_from_date(jira, config["JIRA_EMAIL"], issues).result
    else:
        worklogs = D()

    show_report(worklogs, format=format)


@cli.command(hidden=True)
@click.pass_context
def shell(ctx):
    config = get_config(config=ctx.obj)
    server, email, token = D(config)(*(f"JIRA_{e}" for e in ["SERVER", "EMAIL", "TOKEN"]))
    show_cursor()
    print(f"Connecting to jira server using provided credentials (ignore the question below)")
    subprocess.run(["jirashell", "-s", f"https://{server}", "-u", email, "-p", token])


def main():
    try:
        if sys.stdin.isatty():
            hide_cursor()
        cli()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    finally:
        if sys.stdin.isatty():
            show_cursor()
