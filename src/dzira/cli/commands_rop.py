import sys

import click


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


def main():
    try:
        cli()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
