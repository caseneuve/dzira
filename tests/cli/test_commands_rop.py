from unittest.mock import patch

import click
from click.testing import CliRunner
import pytest

from dzira.cli.commands_rop import (
    cli,
    ls,
)
from dzira.core.result import success
from tests.factories import JiraConfigFactory


TESTED_MODULE = "dzira.cli.commands_rop"


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


class TestLsSubcommand(CliTest):

    def test_ls_is_cli_subcommand(self):
        assert hasattr(cli, "commands")
        assert "ls" in cli.commands
        assert cli.commands["ls"] == ls

    @patch(f"{TESTED_MODULE}.pipe")
    def test_ls_gets_context_from_cli(self, mock_pipe, config):
        cli_server = "test.server.com"
        cli_email = "test@example.com"

        result = self.runner.invoke(
            cli, ["--server", cli_server, "--email", cli_email, "ls"], env=config
        )

        assert result.exit_code == 0
        mock_pipe.assert_called_once()

        context_obj = mock_pipe.call_args[0][0]
        assert context_obj["JIRA_SERVER"] == cli_server
        assert context_obj["JIRA_EMAIL"] == cli_email

    @patch(f"{TESTED_MODULE}.create_jira_connection")
    @patch(f"{TESTED_MODULE}.get_config_rop")
    def test_pipeline_calls_correct_mocks_in_order(
        self, mock_get_config, mock_create_connection, config
    ):
        mock_jira_config = "mock_jira_config"
        mock_jira_client = "mock_jira_client"
        mock_get_config.return_value = success(mock_jira_config)
        mock_create_connection.return_value = success(mock_jira_client)

        result = self.runner.invoke(cli, ["ls"], env=config)

        assert result.exit_code == 0

        mock_get_config.assert_called_once()
        mock_create_connection.assert_called_once()

        # Verify get_config_rop was called with context object
        config_call_args = mock_get_config.call_args[0][0]
        # The context should contain all the config values from env
        for key in config:
            assert config_call_args[key] == config[key]

        # Verify create_jira_connection was called with result from get_config_rop
        connection_call_args = mock_create_connection.call_args[0][0]
        assert connection_call_args == mock_jira_config
