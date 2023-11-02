from __future__ import annotations
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from itertools import cycle
from pathlib import Path
from typing import Any, Iterable
import concurrent.futures

import click
from dotenv import dotenv_values
from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Board, Issue, Sprint, Worklog
from tabulate import tabulate


CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"
REQUIRED_KEYS = "JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_BOARD"

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


@dataclass
class Result:
    result: Any = None
    stdout: str = ""


class D(dict):
    def __call__(self, *keys) -> Iterable:
        if keys:
            return [self.get(k) for k in keys]
        else:
            return self.values()

    def update(self, k, v) -> D:
        self[k] = v
        return self

    def __repr__(self):
        return f"betterdict({dict(self)})"


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
                if out:=result.stdout:
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
                    end=f": {error_msg}\n", flush=True,
                )
                print(dir(exc))
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


def get_board_name(config: dict) -> str:
    return f'{config["JIRA_BOARD"]} board'


def _get_board_by_name(jira: JIRA, name: str) -> Board:
    if boards := jira.boards(name=name):
        return boards[0]
    raise Exception(f"could not find any board matching {name!r}")


@spin_it("Getting board")
def get_board_by_name(jira: JIRA, name: str) -> Result:
    board = _get_board_by_name(jira, name)
    return Result(
        result=board,
        stdout=f'{board.raw["location"]["displayName"]}'
    )


def get_sprints(jira: JIRA, board: Board, state: str = "active") -> list:
    if sprints := jira.sprints(board_id=board.id, state=state):
        return sprints
    raise Exception(f"could not find any sprints for board {board.name!r}")


@spin_it("Getting sprint")
def get_current_sprint(jira: JIRA, board: Board) -> Result:
    sprint = get_sprints(jira, board)[0]
    fmt = lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%a, %b %d")
    return Result(
        result=sprint,
        stdout=f"{sprint.name} [{fmt(sprint.startDate)} -> {fmt(sprint.endDate)}]",
    )


def _get_sprint_issues(jira: JIRA, sprint: Sprint) -> list:
    if issues := jira.search_issues(jql_str=f"Sprint = {sprint.name!r}"):
        return list(issues)
    raise Exception(f"could not find any issues for sprint {sprint.name!r}")


@spin_it("Getting issues")
def get_sprint_issues(jira: JIRA, sprint: Sprint) -> Result:
    issues = _get_sprint_issues(jira, sprint)
    return Result(result=issues)


# TODO: catch errors and properly process them in Result (stderr?)
@spin_it("Adding worklog")
def add_worklog(jira: JIRA, issue, time=None, comment=None, seconds=None, **_) -> Result:
    work_log = jira.add_worklog(
        issue=issue, timeSpent=time, timeSpentSeconds=seconds, comment=comment
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


def _update_worklog(worklog: Worklog, time: str | None, comment: str | None) -> None:
    if not (time or comment):
        raise Exception(
            "at least one of <time> or <comment> fields needed to perform the update!"
        )
    fields = {k: v for k, v in zip(["timeSpent", "comment"], [time, comment]) if v}
    worklog.update(fields=fields)


@spin_it("Updating worklog")
def update_worklog(worklog: Worklog, time: str, comment: str, **_) -> Result:
    _update_worklog(worklog, time, comment)
    return Result(stdout=f"{worklog.id} updated!")


##################################################
#  CLI wrapper
##################################################


@click.group()
@click.option("-f", "--file", help=f"Config file path", type=click.Path())
@click.option("-o", "--board", help="JIRA_BOARD value", envvar="JIRA_BOARD")
@click.option("-k", "--token", help="JIRA_TOKEN value", envvar="JIRA_TOKEN")
@click.option("-m", "--email", help="JIRA_EMAIL value", envvar="JIRA_EMAIL")
@click.option("-d", "--server", help="JIRA_SERVER value", envvar="JIRA_SERVER")
@click.option("--spin/--no-spin", help="Control the spinner", default=True)
@click.help_option("-h", "--help")
@click.pass_context
def cli(ctx, file, board, token, email, server, spin):
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
    - JIRA_BOARD (the default Jira board to use)
    """
    global use_spinner; use_spinner = spin

    ctx.ensure_object(dict)
    cfg = {
        k: v
        for k, v in dict(
            file=file,
            JIRA_BOARD=board,
            JIRA_TOKEN=token,
            JIRA_EMAIL=email,
            JIRA_SERVER=server,
        ).items()
        if v is not None
    }
    ctx.obj.update(cfg)


##################################################
#  LS command
##################################################


def get_current_sprint_with_issues(config: dict) -> list[Issue]:
    config = get_config(config=config)
    jira = get_jira(config).result
    board = get_board_by_name(jira, get_board_name(config)).result
    sprint = get_current_sprint(jira, board).result
    return get_sprint_issues(jira, sprint).result


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
@click.help_option("-h", "--help")
def ls(ctx):
    """
    List issues from the current sprint
    """
    show_issues(get_current_sprint_with_issues(ctx.obj))


##################################################
#  LOG command
##################################################

### Validators

def is_valid_time(time: str) -> bool:
    return (
        re.match(r"^(([1-9]|1\d|2[0-3])h)?(\s+(?=\d))?(([1-5]\d|[1-9])m)?$", time)
        is not None
    )


def is_valid_hour(hour):
    return re.match(r"^(([01]?\d|2[0-3])[:.h,])+([0-5]?\d)$", hour) is not None


def validate_time(_, __, time):
    if time is None or is_valid_time(time):
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
    if value is None or is_valid_hour(value):
        return value
    raise click.BadParameter(
        "start/end time has to be in format '[H[H]][:.h,][M[M]]', e.g. '2h3', '12:03', '3,59'"
    )


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

    t2 = (
        datetime.now()
        if end is None
        else datetime.strptime(re.sub(r"[,.h]", ":", end), "%H:%M")
    )
    t1 = datetime.strptime(re.sub(r"[,.h]", ":", start), "%H:%M")

    if t2 < t1:
        raise click.BadParameter("start time cannot be later than end time")
    else:
        delta_seconds = (t2 - t1).total_seconds()
        return payload.update("seconds", str(int(delta_seconds)))


def establish_issue(jira: JIRA, config: dict, payload: D) -> D:
    board = config.get("JIRA_BOARD")
    issue = payload.get("issue", "")

    if issue.isdigit():
        return payload.update("issue", f"{board}-{issue}")

    jira_board = get_board_by_name(jira, board).result
    sprint = get_current_sprint(jira, jira_board)
    sprint_issues = get_sprint_issues(jira, sprint.result).result
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
@click.option("-c", "--comment", help="Comment added to logged time")
@click.option(
    "-w", "--worklog", "worklog_id", type=int, help="Id of the worklog to be updated"
)
@click.option("--spin/--no-spin", default=True)
@click.help_option("-h", "--help")
def log(ctx, **_):
    """
    Log time spent on ISSUE number or ISSUE with description containing
    matching string.

    TIME spent should be in format '[Nh] [Nm]'; or it can be calculated
    when START time is be provided;

    END time is optional, both should match 'H:M' format.

    Optionally a COMMENT text can be added.

    When WORKLOG id is present, it will update an existing log,
    rather then create a new one.
    """
    payload = sanitize_params(D(ctx.params))
    config = get_config(config=ctx.obj)
    jira = get_jira(config).result
    payload = establish_issue(jira, config, payload)
    perform_log_action(jira, payload)


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
