from __future__ import annotations

import concurrent.futures
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import wraps
from itertools import cycle
from pathlib import Path
from typing import Any, Iterable

import click
from dotenv import dotenv_values
from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Board, Sprint, User, Worklog
from tabulate import tabulate


CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"
REQUIRED_KEYS = "JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT_KEY"

use_spinner = True


def c(*args):
    C = {k: f"\033[{v}m" for k, v in (("^reset", 0),
                                      ("^bold", 1),
                                      ("^red", 91),
                                      ("^green", 92),
                                      ("^yellow", 93),
                                      ("^blue", 94),
                                      ("^magenta", 95),
                                      ("^cyan", 96))}
    return "".join([C.get(a, a) for a in args]) + C["^reset"]


def hide_cursor():
    print("\033[?25l", end="", flush=True)


def show_cursor():
    print("\033[?25h", end="", flush=True)


class D(dict):
    def __call__(self, *keys) -> Iterable:
        if keys:
            return [self.get(k) for k in keys]
        else:
            return self.values()

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'D' object has no attribute {key!r}")

    def _update(self, k, v):
        self[k] = v(self.get(k)) if callable(v) else v

    def update(self, *args, **kwargs):
        if len(args) % 2 != 0:
            raise Exception(
                f"Provide even number of key-value args, need a value for key: {args[-1]!r}"
            )
        for i in range(0, len(args), 2):
            self._update(args[i], args[i + 1])
        for k, v in kwargs.items():
            self._update(k, v)
        return self

    def has(self, k):
        return self.get(k) is not None

    def without(self, *args):
        return D({k: v for k, v in self.items() if k not in args})

    def __repr__(self):
        return f"betterdict({dict(self)})"


@dataclass
class Result:
    result: Any = None
    stdout: str = ""
    data: D = field(default_factory=D)


def spin_it(msg="", done="✓", fail="✗"):
    spinner = cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    separator = "  "
    connector = ":\t"

    def decorator(func):
        func.is_decorated_with_spin_it = True

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not use_spinner:
                result = func(*args, **kwargs)
                if out := result.stdout:
                    print(c("^green", done, separator, "^reset", out), flush=True)
                return result

            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(func, *args, **kwargs)

                    while future.running():
                        print(
                            c("\r", "^magenta", next(spinner), separator, msg),
                            end="", flush=True,
                        )
                        time.sleep(0.1)

                    r: Result = future.result()
                    print(
                        c("\r", "^green", done, separator, msg, "^reset", connector, r.stdout),
                        flush=True
                    )
                    return r
            except Exception as exc:
                if type(exc) == JIRAError:
                    error_msg = exc.response.json()["errors"]
                else:
                    error_msg = exc
                print(
                    c("\r", "^red", fail, separator, msg),
                    end=":\n", flush=True,
                )
                raise Exception(error_msg)
        return wrapper
    return decorator


def get_config_from_file(config_file: str | Path | None = None) -> dict:
    if config_file is None:
        config_file_dir = os.environ.get("XDG_CONFIG_HOME", os.environ["HOME"])
        for path in (
                os.path.join(config_file_dir, CONFIG_DIR_NAME, "env"),
                os.path.join(config_file_dir, DOTFILE),
                os.path.join(os.environ["HOME"], ".config", CONFIG_DIR_NAME, "env"),
                os.path.join(os.environ["HOME"], ".config", DOTFILE),
        ):
            if os.path.isfile(path):
                config_file = path
                break

    return dotenv_values(config_file)


def get_config(config: dict = {}) -> dict:
    for cfg_fn in (
        lambda: get_config_from_file(config.get("file")),
        lambda: (_ for _ in ()).throw(
            Exception(
                "could not find required config values: "
                f"{', '.join(sorted(set(REQUIRED_KEYS).difference(set(config))))}"
            )
        ),
    ):
        if set(REQUIRED_KEYS).issubset(config.keys()):
            break
        config = {**cfg_fn(), **config}

    return config


##################################################
#  JIRA wrapper
##################################################


@spin_it("Getting client")
def get_jira(config: dict) -> Result:
    jira = JIRA(
        server=f"https://{config['JIRA_SERVER']}",
        basic_auth=(config["JIRA_EMAIL"], config["JIRA_TOKEN"]),
    )
    msg = f"connecting to {config['JIRA_SERVER']}"
    return Result(stdout=msg, result=jira)


@spin_it("Getting board")
def get_board(jira: JIRA, key: str) -> Result:
    try:
        boards = jira.boards(projectKeyOrID=key)
    except JIRAError as exc_info:
        raise Exception(str(exc_info))
    if len(boards) > 1:
        raise Exception(
            f"Found more than one board matching {key!r}:\n"
            f"{', '.join(b.raw['location']['displayName'] for b in boards)}"
        )
    return Result(
        result=boards[0],
        stdout=f'{boards[0].raw["location"]["displayName"]}'
    )


def _get_sprints(jira: JIRA, board: Board, state: str) -> list:
    if sprints := jira.sprints(board_id=board.id, state=state):
        return sprints
    raise Exception(f"could not find any sprints for board {board.name!r}")


def _get_first_sprint_matching_state(jira: JIRA, board: Board, state: str = "active", **_) -> Sprint:
    sprints = _get_sprints(jira, board, state)
    if len(sprints) > 1:
        info = "\n".join([f"\t - {s.name}, id: {s.id}" for s in sprints])
        raise Exception(
            f"Found more than one {state} sprint:\n{info}\n"
            "Use sprint id to get unambiguous result"
        )
    return sprints[0]


def _get_sprint_from_id(jira: JIRA, sprint_id: int, **_) -> Sprint:
    try:
        return jira.sprint(sprint_id)
    except JIRAError as exc:
        raise Exception(str(exc))


@spin_it("Getting sprint")
def get_sprint(jira: JIRA, payload: D) -> Result:
    fn = _get_sprint_from_id if payload.has("sprint_id") else _get_first_sprint_matching_state
    sprint = fn(jira, **payload)
    out = process_sprint_out(sprint)
    return Result(result=sprint, stdout=out)


def _get_sprint_issues(jira: JIRA, sprint: Sprint) -> list:
    if issues := jira.search_issues(jql_str=f"Sprint = {sprint.name!r}"):
        return list(issues)
    raise Exception(f"could not find any issues for sprint {sprint.name!r}")


@spin_it("Getting issues")
def get_issues(jira: JIRA, sprint: Sprint) -> Result:
    issues = _get_sprint_issues(jira, sprint)
    return Result(result=issues)


# TODO: catch errors and properly process them in Result (stderr?) // update tests for new param
@spin_it("Adding worklog")
def add_worklog(
        jira: JIRA,
        issue: str,
        time: str | None = None,
        comment: str | None = None,
        seconds: int | None = None,
        date: datetime | None = None,
        **_
) -> Result:
    work_log = jira.add_worklog(
        issue=issue, timeSpent=time, timeSpentSeconds=seconds, comment=comment, started=date
    )
    return Result(
        stdout=(
            f"spent {work_log.raw['timeSpent']} in {issue} "
            f"[worklog {work_log.id}] at {datetime.now():%H:%M:%S}"
        )
    )


def get_worklog(jira: JIRA, issue: str, worklog_id: str | int, **_) -> Worklog:
    if work_log := jira.worklog(issue=issue, id=str(worklog_id)):
        return work_log
    raise Exception(f"could not find worklog {worklog_id} for issue {issue!r}")


def _update_worklog(
        worklog: Worklog, time: str | None, comment: str | None, date: datetime | None
) -> None:
    if not (time or comment):
        raise Exception(
            "at least one of <time> or <comment> fields needed to perform the update!"
        )
    fields = {
        k: v
        for k, v in zip(["timeSpent", "comment", "started"], [time, comment, date])
        if v
    }
    worklog.update(fields=fields)


# TODO: we can't update worklog to change the issue
# * add delete option to worklog !!!
# * catch error when someone tries to update worklog in wrong ticket! => test it
@spin_it("Updating worklog")
def update_worklog(
        worklog: Worklog, time: str, comment: str, date: datetime | None = None, **_
) -> Result:
    try:
       _update_worklog(worklog, time, comment, date)
    except JIRAError as exc:
        raise Exception(str(exc))
    return Result(stdout=f"{worklog.id} updated!")


##################################################
#  CLI wrapper
##################################################


@click.group()
@click.option("-f", "--file", help=f"Config file path", type=click.Path())
@click.option("-k", "--key", help="JIRA_PROJECT_KEY value", envvar="JIRA_PROJECT_KEY")
@click.option("-t", "--token", help="JIRA_TOKEN value", envvar="JIRA_TOKEN")
@click.option("-m", "--email", help="JIRA_EMAIL value", envvar="JIRA_EMAIL")
@click.option("-s", "--server", help="JIRA_SERVER value", envvar="JIRA_SERVER")
@click.option("--spin/--no-spin", help="Control the spinner", default=True)
@click.help_option("-h", "--help")
@click.pass_context
def cli(ctx, file, key, token, email, server, spin):
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
    global use_spinner; use_spinner = spin

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


def process_sprint_out(sprint: Sprint) -> str:
    fmt = lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%a, %b %d")
    return f"{sprint.name} • id: {sprint.id} • {fmt(sprint.startDate)} -> {fmt(sprint.endDate)}"


# TODO: we probably should check board always, as sprint_id may not be matching the team's board...
def get_sprint_and_issues(jira: JIRA, payload: D) -> list:
    if not payload.has("sprint_id"):
        payload.update("board", get_board(jira, payload["JIRA_PROJECT_KEY"]).result)
    sprint = get_sprint(jira, payload).result
    return get_issues(jira, sprint).result


def show_issues(issues: list) -> None:
    fmt = lambda t: timedelta(seconds=t) if t else None
    state_clr = {"To Do": "^magenta", "In Progress": "^yellow", "Done": "^green"}
    clr = lambda s: c(state_clr.get(s, "^reset"), "^bold", s)

    def estimate(i):
        try:
            remining = i.fields.timetracking.remainingEstimate
            original = i.fields.timetracking.originalEstimate
            return f"{remining} ({original})" if remining != original else original
        except Exception:
            return fmt(i.fields.timeestimate)

    issues = [
        (
            c("^blue", i.key),
            i.fields.summary,
            clr(i.fields.status.name),
            fmt(i.fields.timespent),
            estimate(i),
        )
        for i in reversed(sorted(issues, key=lambda i: i.fields.status.name))
    ]
    print(
        tabulate(
            issues,
            headers=("#", "summary", "state", "spent", "estimated"),
            colalign=("right", "left", "left", "right", "right"),
            maxcolwidths=[None, 35, None, None, None],
            tablefmt="grid",
        )
    )


@cli.command()
@click.pass_context
@click.option(
    "-s", "--state",
    type=click.Choice(["active", "closed"]), default="active", show_default=True,
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
@click.help_option("-h", "--help")
def ls(ctx, state, sprint_id):
    """
    List issues from the current sprint.

    'Current sprint' is understood as the first 'active' sprint found.
    To avoid ambiguity, use --sprint-id option.
    """
    config = get_config(config=ctx.obj)
    jira = get_jira(config).result
    issues = get_sprint_and_issues(jira, D(state=state, sprint_id=sprint_id, **config))
    show_issues(issues)


##################################################
#  LOG command
##################################################

### Validators

def matches_time_re(time: str) -> D:
    m = re.match(
        r"^(?P<h>([1-9]|1\d|2[0-3])h)?(\s*(?=\d))?(?P<m>([1-5]\d|[1-9])m)?$",
        time
    )
    return D(m.groupdict() if m is not None else {})


def is_valid_hour(hour) -> bool:
    return re.match(r"^(([01]?\d|2[0-3])[:.h,])+([0-5]?\d)$", hour) is not None


def validate_time(_, __, time):
    if time is None:
        return
    if (match := matches_time_re(time)):
        h, m = match("h", "m")
        time = f"{h + ' ' if h is not None else ''}{m or ''}".strip()
        return time
    raise click.BadParameter(
        "time has to be in format '[Nh] [Nm]', e.g. '2h', '30m', '4h 15m'"
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
        return payload

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
        return payload.update("seconds", str(int(delta_seconds)))


def establish_issue(jira: JIRA, payload: D) -> D:
    key = payload["JIRA_PROJECT_KEY"]
    issue = payload.get("issue", "")

    if issue.isdigit():
        return payload.update("issue", f"{key}-{issue}")

    sprint_issues = get_sprint_and_issues(jira, payload)
    candidates = [i for i in sprint_issues if issue.lower() in i.fields.summary.lower()]

    if not candidates:
        raise Exception("could not find any matching issues")
    if len(candidates) > 1:
        msg = "\n".join(f" * {i.key}: {i.fields.summary}" for i in candidates)
        raise Exception("found more than one matching issue:\n" + msg)

    return payload.update("issue", candidates[0].key)


def perform_log_action(jira: JIRA, payload: D) -> None:
    if payload["worklog_id"] is not None:
        worklog = get_worklog(jira, **payload)
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
@click.option("--spin/--no-spin", default=True)
@click.help_option("-h", "--help")
def log(ctx, **_):
    """Log time spent on ISSUE number or ISSUE with description containing
    matching string.

    TIME spent should be in format '[[Nh][ ]][Nm]'; or it can be calculated
    when START time is be provided;

    END time is optional, both should match 'H:M' format.

    Optionally a COMMENT text can be added.

    When WORKLOG id is present, it will update an existing log,
    rather then create a new one.  ISSUE is still required.

    To log work done in the past (but no older as 2 weeks), use --date option.
    It accepts the following patterns:

    \b
      "YYYY-mm-dd", "YYYY-mm-ddTHH:MM", "YYYY-mm-dd HH:MM".

    \b Time is assumed from the START option, if present and date is
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


@spin_it("Getting user")
def get_user(jira: JIRA, config: dict) -> Result:
    try:
        users = jira.search_users(query=config["JIRA_EMAIL"])
    except Exception as exc:
        raise Exception(str(exc))
    if len(users) > 1:
        raise Exception(f"Found more than one user\n{', '.join(u.displayName for u in users)}")
    if users == []:
        raise Exception("Could not find users matching given email address")

    return Result(result=users[0], stdout=users[0].displayName)


@spin_it("Getting issues")
def get_issues_with_work_logged_on_date(jira: JIRA, report_date: datetime | None) -> Result:
    if report_date is not None:
        query = f"worklogDate = {report_date:%Y-%m-%d}"
    else:
        query = f"worklogDate >= startOfDay()"
        report_date = datetime.combine(date.today(), datetime.min.time())
    try:
        issues = jira.search_issues(query)
    except JIRAError as exc:
        raise Exception(str(exc))

    return Result(
        result=issues,
        data=D(report_date=report_date),
        stdout=(
            f"Found {len(issues)} issue{'s' if len(issues) != 1 else ''} "
            f"with work logged on {report_date:%a, %b %d}"
        )
    )


@spin_it("Getting worklogs")
def get_user_worklogs_from_date(jira: JIRA, user: User, issues: Result) -> Result:
    worklogs = D(counter=0)

    for issue in issues.result:
        try:
            issue_worklogs = jira.worklogs(issue.id)
            matching = [
                w for w in issue_worklogs
                if (
                        (w.author.accountId == user.accountId)
                        and (
                            issues.data.report_date
                            <= datetime.strptime(w.started.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                            < (issues.data.report_date + timedelta(days=1))
                        )
                )
            ]
            if matching:
                key = issue.raw["key"]
                summary = issue.raw["fields"]["summary"]
                # worklogs[f"[{key}] {summary}"] = matching
                worklogs.update(f"[{key}] {summary}", matching, counter=lambda x: x + (len(matching)))
        except Exception as exc:
            raise Exception(str(exc))

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


def show_report(worklogs: D) -> None:
    total_time = 0
    for issue in worklogs:
        this_total_time = 0
        rows = []
        for w in worklogs[issue]:
            started, time_spent, comment, time_spent_seconds = D(w.raw)(
                "started", "timeSpent", "comment", "timeSpentSeconds"
            )
            total_time += time_spent_seconds
            this_total_time += time_spent_seconds
            local_timestamp = datetime.strptime(started, '%Y-%m-%dT%H:%M:%S.%f%z').astimezone()
            formatted_time = local_timestamp.strftime('%H:%M:%S')
            row = [f"[{w.id}]", formatted_time, f":{time_spent:>6}", comment or ""]
            rows.append(row)

        print()
        print(c("^bold", issue), f"({_seconds_to_hour_minute_fmt(this_total_time)})")
        print(tabulate(rows, maxcolwidths=[None, None, None, 60]))

    if worklogs:
        print(f"\n{c('^bold', 'Total spent time')}: {_seconds_to_hour_minute_fmt(total_time)}\n")


# TODO:
# - [ ] sprint option
# - [ ] save to csv, json format
@cli.command()
@click.pass_context
@click.option("-d", "--date", "report_date", help="Date to show report for", type=click.DateTime())
@click.help_option("-h", "--help")
def report(ctx, report_date):
    """
    Show work logged for today or for DATE.
    """
    config = get_config(config=ctx.obj)
    jira = get_jira(config).result
    user = get_user(jira, config).result
    issues = get_issues_with_work_logged_on_date(jira, report_date)
    if issues.result:
        worklogs = get_user_worklogs_from_date(jira, user, issues).result
        show_report(worklogs)
    else:
        print("No work logged on given date")


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
        hide_cursor()
        cli()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    finally:
        show_cursor()


if __name__ == "__main__":
    main()


# -*- python-indent-offset: 4 -*-
