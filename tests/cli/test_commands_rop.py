import click
from click.testing import CliRunner
import pytest

from dzira.cli.commands_rop import (
    cli,
)
from tests.factories import JiraConfigFactory


@pytest.fixture
def mock_ctx():
    captured_context = {}

    @cli.command("test-cmd")
    @click.pass_context
    def _(ctx):
        captured_context.update(ctx.obj)

    return captured_context


@pytest.fixture
def config():
    return JiraConfigFactory()


class CliTest:
    runner = CliRunner()


class TestCLI(CliTest):

    def test_updates_context(self, mock_ctx):
        result = self.runner.invoke(
            cli, ["--key", "PROJ-123", "--email", "test@example.com", "test-cmd"]
        )

        assert result.exit_code == 0
        assert mock_ctx["JIRA_PROJECT_KEY"] == "PROJ-123"
        assert mock_ctx["JIRA_EMAIL"] == "test@example.com"
        assert "JIRA_TOKEN" not in mock_ctx

    def test_updates_context_with_env_vars(self, mock_ctx, config):
        result = self.runner.invoke(cli, ["test-cmd"], env=config)

        assert result.exit_code == 0
        for k, v in config.items():
            assert mock_ctx[k] == v

    def test_cli_has_precedence_over_env_vars(self, mock_ctx, config):
        result = self.runner.invoke(cli, ["-m", "listy@skrzynka.com", "test-cmd"], env=config)

        assert result.exit_code == 0
        assert mock_ctx["JIRA_EMAIL"] == "listy@skrzynka.com" != config.pop("JIRA_EMAIL")
        for k, v in config.items():
            assert mock_ctx[k] == v
