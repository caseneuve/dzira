import os
from unittest.mock import call, patch, sentinel

import pytest

from src.dzira.betterdict import D
from src.dzira.cli.config import (
    CONFIG_DIR_NAME,
    DOTFILE,
    get_config,
    get_config_from_file,
)


@pytest.fixture
def config(mocker):
    mock_dotenv_values = mocker.patch("src.dzira.cli.config.dotenv_values")
    mock_dotenv_values.return_value = {
        "JIRA_SERVER": "foo.bar.com",
        "JIRA_EMAIL": "name@example.com",
        "JIRA_TOKEN": "asdf1234",
        "JIRA_PROJECT_KEY": "XYZ",
    }
    return mock_dotenv_values


class TestGetConfigFromFile:
    def test_looks_for_config_file_in_default_locations_when_path_not_provided(
            self, mocker, config
    ):
        mocker.patch.dict(os.environ, {"HOME": "/home/foo"}, clear=True)
        mock_env_get = mocker.patch("src.dzira.cli.config.os.environ.get")
        mock_os_path = mocker.patch("src.dzira.cli.config.os.path")
        mock_dotenv_values = config

        get_config_from_file()

        mock_env_get.assert_called_once_with("XDG_CONFIG_HOME", "/home/foo")
        assert mock_os_path.join.call_args_list == [
            call(mock_env_get.return_value, CONFIG_DIR_NAME, "env"),
            call(mock_env_get.return_value, DOTFILE),
            call(os.environ["HOME"], ".config", CONFIG_DIR_NAME, "env"),
            call(os.environ["HOME"], ".config", DOTFILE)
        ]
        mock_dotenv_values.assert_called_once()

    def test_picks_up_first_matching_path_when_no_file_provided(self, mocker, config):
        mocker.patch.dict(os.environ, {"HOME": "/home/foo"}, clear=True)
        mock_os_path_isfile = mocker.patch("src.dzira.cli.config.os.path.isfile")
        mock_os_path_isfile.side_effect = [False, True]
        mock_dotenv_values = config

        get_config_from_file()

        mock_dotenv_values.assert_called_once_with(f"/home/foo/{DOTFILE}")

    def test_looks_for_config_file_in_provided_location(self, config):
        mock_dotenv_values = config

        get_config_from_file(sentinel.path)

        mock_dotenv_values.assert_called_once_with(sentinel.path)

    def test_returns_empty_dict_when_no_file_found(self, mocker):
        mocker.patch("src.dzira.cli.config.os.path.isfile", lambda _: False)

        result = get_config_from_file()

        assert result == {}


@patch("src.dzira.cli.config.REQUIRED_KEYS", ("FOO", "BAR", "BAZ"))
@patch("src.dzira.cli.config.get_config_from_file")
class TestGetConfig:
    def test_uses_user_provided_values_entirely(self, mock_config_from_file):
        override_conf = D({"FOO": "123", "BAR": "abc", "BAZ": "zab"})

        result = get_config(override_conf)

        assert result == override_conf
        mock_config_from_file.assert_not_called()

    def test_uses_config_files_as_fallback(self, mock_config_from_file):
        mock_config_from_file.return_value = {"BAR": "abc", "BAZ": "999", "FOO": "321"}

        result = get_config({"BAR": "from override"})

        assert result == D({"FOO": "321", "BAR": "from override", "BAZ": "999"})

    def test_uses_provided_file_instead_of_default_ones(self, mock_config_from_file):
        mock_config_from_file.return_value = {"FOO": "123", "BAR": "abc", "BAZ": "zab"}

        result = get_config({"file": "/path/to/file"})

        assert result == D(
            {
                "FOO": "123",
                "BAR": "abc",
                "BAZ": "zab",
                "file": "/path/to/file",
            }
        )
        mock_config_from_file.assert_called_once_with("/path/to/file")

    def test_raises_when_required_values_not_found_in_compiled_config(
        self, mock_config_from_file
    ):
        mock_config_from_file.return_value = {"BAR": "abc"}
        with pytest.raises(Exception) as exc_info:
            get_config({})

        assert str(exc_info.value) == "could not find required config values: BAZ, FOO"
