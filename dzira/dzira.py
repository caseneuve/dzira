from __future__ import annotations
import os
import re
import sys
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Callable

import click
from dotenv import dotenv_values
from jira import JIRA
from jira.resources import Board, Sprint, Worklog
from tabulate import tabulate


C = dict(
    purple="\033[95m",
    cyan="\033[96m",
    darkcyan="\033[36m",
    blue="\033[94m",
    green="\033[92m",
    yellow="\033[93m",
    red="\033[91m",
    bold="\033[1m",
    underline="\033[4m",
    reset="\033[0m",
)

CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"
REQUIRED_KEYS = "JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_BOARD"


def get_config_from_file(config_file: str | Path | None = None) -> dict:
    if config_file is None:
        config_file_dir = Path(os.environ.get("XDG_CONFIG_HOME", os.environ["HOME"]))
        for path in (
            (config_file_dir / CONFIG_DIR_NAME / "env"),
            (config_file_dir / DOTFILE),
        ):
            if path.is_file():
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


def get_jira(config: dict) -> JIRA:
    return JIRA(
        server=f"https://{config['JIRA_SERVER']}",
        basic_auth=(config["JIRA_EMAIL"], config["JIRA_TOKEN"]),
    )


def get_board_name(config: dict) -> str:
    return f'{config["JIRA_BOARD"]} board'


def get_board_by_name(jira: JIRA, name: str) -> Board:
    if boards := jira.boards(name=name):
        return boards[0]
    raise Exception(f"could not find any board matching {name!r}")


def get_sprints(jira: JIRA, board: Board, state: str = "active") -> list:
    if sprints := jira.sprints(board_id=board.id, state=state):
        return sprints
    raise Exception(f"could not find any sprints for board {board.name!r}")


def get_current_sprint(jira: JIRA, board: Board) -> Sprint:
    return get_sprints(jira, board)[0]


def get_sprint_issues(jira: JIRA, sprint: Sprint) -> list:
    if issues := jira.search_issues(jql_str=f"Sprint = {sprint.name!r}"):
        return list(issues)
    raise Exception(f"could not find any issues for sprint {sprint.name!r}")


def add_worklog(
    jira: JIRA,
    issue: str | int,
    time: str | None = None,
    seconds: str | None = None,
    comment: str | None = None,
) -> None:
    work_log = jira.add_worklog(
        issue=issue, timeSpent=time, timeSpentSeconds=seconds, comment=comment
    )
    print(
        f"Spent {work_log.raw['timeSpent']} in {issue} "
        f"({work_log.issueId}) [worklog {work_log.id}]"
    )


def get_worklog(
    jira: JIRA, issue: str | int, worklog_id: str | int
) -> Worklog:
    if work_log := jira.worklog(issue=issue, id=str(worklog_id)):
        return work_log
    raise Exception(f"could not find worklog {worklog_id} for issue {issue!r}")


def update_worklog(
    worklog: Worklog, time: str | None = None, comment: str | None = None, **kwargs
) -> None:
    fields = {}
    if time:
        fields["timeSpent"] = time
    if comment:
        fields["comment"] = comment
    if not fields:
        raise Exception(
            f"at least one of <time> or <comment> fields needed to perform the update!"
        )
    worklog.update(fields=fields)
    print(f"Worklog {worklog.id} updated!")


##################################################
#  CLI wrapper
##################################################

@click.group()
@click.option("-f", "--file", help=f"Config file path", type=click.File())
@click.option("-o", "--board", help="JIRA_BOARD value", envvar="JIRA_BOARD")
@click.option("-k", "--token", help="JIRA_TOKEN value", envvar="JIRA_TOKEN")
@click.option("-m", "--email", help="JIRA_EMAIL value", envvar="JIRA_EMAIL")
@click.option("-d", "--server", help="JIRA_SERVER value", envvar="JIRA_SERVER")
@click.pass_context
def cli(ctx, file, board, token, email, server):
    """
    Configure JIRA connection by using config files
    (XDG_CONFIG_HOME/dzira/env or ~/.dzira),
    environment variables, or options below:
    """
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


def get_current_sprint_with_issues(config: dict) -> tuple[Sprint, list, Board]:
    config = get_config(config=config)
    jira = get_jira(config)
    board = get_board_by_name(jira, get_board_name(config))
    sprint = get_current_sprint(jira, board)
    return sprint, get_sprint_issues(jira, sprint), board


def show_issues(issues: list) -> None:
    fmt = lambda t: timedelta(seconds=t) if t else None
    state_clr = {"To Do": "purple", "In Progress": "yellow", "Done": "green"}
    clr = lambda s: C[state_clr.get(s, "reset")] + C["bold"] + s + C["reset"]
    issues = [
        (
            C["blue"] + i.key + C["reset"],
            i.fields.summary,
            clr(i.fields.status.name),
            fmt(i.fields.timespent),
            fmt(i.fields.timeestimate),
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


def show_sprint_info(sprint: Sprint, board: Board) -> None:
    project = board.raw["location"]["projectName"]
    fmt = lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%a, %b %d")
    print(
        f"\n{C['bold']}  {sprint.name} by {project}{C['reset']} "
        f"[{fmt(sprint.startDate)} -> {fmt(sprint.endDate)}]\n"
    )


@cli.command()
@click.pass_context
def ls(ctx):
    """
    List issues from the current sprint
    """
    sprint, issues, board = get_current_sprint_with_issues(ctx.obj)
    show_sprint_info(sprint, board)
    show_issues(issues)


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


### Payload


def calculate_seconds(start: str, end: str | None = None) -> str:
    if end is None:
        t2 = datetime.now()
    else:
        t2 = datetime.strptime(re.sub(r"[,.h]", ":", end), "%H:%M")

    t1 = datetime.strptime(re.sub(r"[,.h]", ":", start), "%H:%M")

    if t2 < t1:
        raise click.BadParameter("start time cannot be later than end time")
    else:
        delta_seconds = (t2 - t1).total_seconds()
        return str(int(delta_seconds))


def prepare_payload(
    time: str | None,
    start: str | None,
    end: str | None,
    comment: str | None,
) -> dict:
    payload = dict(comment=comment)
    if time:
        payload["time"] = time
    elif start:
        payload["seconds"] = calculate_seconds(start=start, end=end)
    return payload


def establish_issue(jira: JIRA, config: dict, issue: str) -> str:
    board = config.get("JIRA_BOARD")

    if issue.isdigit():
        return f"{board}-{issue}"

    jira_board = get_board_by_name(jira, board)
    sprint = get_current_sprint(jira, jira_board)
    sprint_issues = get_sprint_issues(jira, sprint)
    candidates = [i for i in sprint_issues if issue.lower() in i.fields.summary.lower()]

    if not candidates:
        raise Exception("could not find any matching issues")
    if len(candidates) > 1:
        msg = "\n".join(f" * {i.key}: {i.fields.summary}" for i in candidates)
        raise Exception("found more than one matching issue:\n" + msg)

    return candidates[0].key


def establish_action(jira: JIRA, payload: dict, worklog_id: str | None) -> Callable:
    if worklog_id:
        worklog = get_worklog(jira, payload["issue"], worklog_id)
        return partial(update_worklog, worklog)
    return partial(add_worklog, jira)


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
def log(ctx, issue, time, start, end, comment, worklog_id):
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
    if not (time or start):
        if worklog_id and comment is None:
            raise click.UsageError(
                "to update a worklog, either time spent or a comment is needed"
            )
        else:
            raise click.UsageError(
                "cannot spend without knowing working time or when work has started: \n"
                "provide valid --time or --start options"
            )

    args = prepare_payload(time, start, end, comment)
    config = get_config(config=ctx.obj)
    jira = get_jira(config)
    args["issue"] = establish_issue(jira, config, issue)
    action = establish_action(jira, args, worklog_id)

    action(**args)


def main():
    try:
        cli()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
