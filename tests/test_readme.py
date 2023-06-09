from pathlib import Path

import pytest
from click.testing import CliRunner

from dzira.dzira import cli

runner = CliRunner()


@pytest.fixture
def readme():
    return Path("README.md")

def test_readme_exists(readme):
    assert readme.is_file()

def test_readme_contains_actual_help_message(readme):
    help = runner.invoke(cli, ["--help"])

    text = readme.read_text().replace(" ", "").replace("\n", "")
    for line in help.output.split("\n")[1:]:
        assert line.replace(" ", "")[:50] in text


def test_readme_contains_actual_ls_help(readme):
    help = runner.invoke(cli, ["ls", "--help"])

    text = readme.read_text().replace(" ", "").replace("\n", "")
    for line in help.output.split("\n")[1:]:
        assert line.replace(" ", "")[:50] in text


def test_readme_contains_actual_log_help(readme):
    help = runner.invoke(cli, ["log", "--help"])

    text = readme.read_text().replace(" ", "").replace("\n", "")
    for line in help.output.split("\n")[1:]:
        assert line.replace(" ", "")[:50] in text
