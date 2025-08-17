import sys

import click

from ..betterdict import D
from ..core.operations_rop import create_jira_connection
from ..core.result import pipe
from .config_rop import get_config_rop


@click.group()
@click.option("-f", "--file", help=f"Config file path", type=click.Path())
@click.option("-k", "--key", help="JIRA_PROJECT_KEY value", envvar="JIRA_PROJECT_KEY")
@click.option("-t", "--token", help="JIRA_TOKEN value", envvar="JIRA_TOKEN")
@click.option("-m", "--email", help="JIRA_EMAIL value", envvar="JIRA_EMAIL")
@click.option("-s", "--server", help="JIRA_SERVER value", envvar="JIRA_SERVER")
@click.help_option("-h", "--help", help="Show this message and exit")
@click.version_option(help="Show the version and exit")
@click.pass_context
def cli(ctx, file, key, token, email, server):
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


@cli.command()
@click.pass_context
def ls(ctx):
    """
    TODO:
    # config rop
    - [X] get_config
    # operations rop
    - [X] get_jira
    - [ ] get_sprints
    # local:
    - [ ] fork if ambiguous (more than one)
    # operations:
    - [ ] get sprint issues
    # procesors
    - [ ] process
    - [ ] show
    """
    pipe(
        D(ctx.obj),
        get_config_rop,
        create_jira_connection,
    )
    # .tee(
    #     lambda x: print(vars(x))
    # )


def main():
    try:
        cli()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
