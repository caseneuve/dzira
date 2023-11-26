from pathlib import Path

from click.testing import CliRunner

from src.dzira.dzira import cli


runner = CliRunner()
readme = Path("README.md").read_text()


def assert_help_in_readme(help):
    text = readme.replace(" ", "").replace("\n", "")
    for line in help.output.split("\n")[1:]:
        assert line.replace(" ", "").replace("\b", "")[:50] in text


def test_readme_exists():
    assert Path("README.md").is_file()


def test_readme_contains_actual_help_message():
    help = runner.invoke(cli, ["--help"])
    assert_help_in_readme(help)


def test_readme_contains_actual_ls_help():
    help = runner.invoke(cli, ["ls", "--help"])
    assert_help_in_readme(help)


def test_readme_contains_actual_log_help():
    help = runner.invoke(cli, ["log", "--help"])
    assert_help_in_readme(help)


def test_readme_contains_actual_report_help():
    help = runner.invoke(cli, ["report", "--help"])
    assert_help_in_readme(help)
