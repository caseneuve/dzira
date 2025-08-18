import os

import pytest

from dzira.cli.config_rop import (
    convert_to_jira_config,
    discover_config_file,
    get_config_file_path,
    get_config_rop,
    get_environment_paths,
    load_config,
)
from dzira.betterdict import D
from dzira.core.models_rop import JiraConfig
from dzira.core.result import success, failure


# Patching fixtures for common mocks
@pytest.fixture
def mock_get_environment_paths(mocker):
    return mocker.patch("dzira.cli.config_rop.get_environment_paths")


@pytest.fixture
def mock_isfile(mocker):
    return mocker.patch("os.path.isfile")


@pytest.fixture
def mock_discover_config_file(mocker):
    return mocker.patch("dzira.cli.config_rop.discover_config_file")


@pytest.fixture
def mock_get_config_file_path(mocker):
    return mocker.patch("dzira.cli.config_rop.get_config_file_path")


@pytest.fixture
def mock_dotenv_values(mocker):
    return mocker.patch("dzira.cli.config_rop.dotenv_values")


@pytest.fixture
def mock_pipeline_functions(mocker):
    return {
        "load_config": mocker.patch("dzira.cli.config_rop.load_config"),
        "convert_to_jira_config": mocker.patch("dzira.cli.config_rop.convert_to_jira_config"),
    }


class TestGetEnvironmentPaths:
    @pytest.mark.parametrize(
        "env_vars,expected_paths",
        [
            (
                {"XDG_CONFIG_HOME": "/test/xdg", "HOME": "/test/home"},
                [
                    "/test/xdg/dzira/env",
                    "/test/xdg/.dzira",
                    "/test/home/.config/dzira/env",
                    "/test/home/.config/.dzira",
                ],
            ),
            (
                {"HOME": "/test/home"},
                [
                    "/test/home/dzira/env",
                    "/test/home/.dzira",
                    "/test/home/.config/dzira/env",
                    "/test/home/.config/.dzira",
                ],
            ),
            (
                {},
                [
                    "dzira/env",
                    ".dzira",
                    ".config/dzira/env",
                    ".config/.dzira",
                ],
            ),
        ],
    )
    def test_returns_correct_paths_based_on_env_vars(self, mocker, env_vars, expected_paths):
        mocker.patch.dict(os.environ, env_vars, clear=True)

        result = get_environment_paths()

        assert result == expected_paths


class TestDiscoverConfigFile:
    def test_returns_first_existing_file(self, mock_get_environment_paths, mock_isfile):
        mock_paths = ["/path1", "/path2", "/path3"]
        mock_get_environment_paths.return_value = mock_paths
        mock_isfile.side_effect = lambda path: path == "/path2"

        result = discover_config_file()

        assert result == "/path2"
        mock_get_environment_paths.assert_called_once()
        assert mock_isfile.call_count == 2  # Stops at first match

    def test_returns_none_when_no_files_exist(self, mock_get_environment_paths, mock_isfile):
        mock_get_environment_paths.return_value = ["/path1", "/path2"]
        mock_isfile.return_value = False

        result = discover_config_file()

        assert result is None
        mock_get_environment_paths.assert_called_once()
        assert mock_isfile.call_count == 2


class TestGetConfigFilePath:
    def test_returns_provided_file_path(self, mock_discover_config_file):
        mock_discover_config_file.return_value = "/fallback/path"

        result = get_config_file_path(D({"file": "/custom/path"}))

        assert result.is_success
        assert result.value == "/custom/path"
        mock_discover_config_file.assert_called_once()

    def test_discovers_file_when_not_provided(self, mock_discover_config_file):
        mock_discover_config_file.return_value = "/discovered/path"

        result = get_config_file_path(D({}))

        assert result.is_success
        assert result.value == "/discovered/path"
        mock_discover_config_file.assert_called_once()

    def test_handles_none_from_discovery(self, mock_discover_config_file):
        mock_discover_config_file.return_value = None

        result = get_config_file_path(D({}))

        assert result.is_success
        assert result.value is None
        mock_discover_config_file.assert_called_once()


class TestLoadConfig:
    def test_success_with_valid_file_path(self, mock_get_config_file_path, mock_dotenv_values):
        file_config = {"KEY1": "value1", "KEY2": "value2"}
        mock_get_config_file_path.return_value = success("/path/to/file")
        mock_dotenv_values.return_value = file_config

        input_data = D({"file": "/test", "KEY1": "input_value"})
        result = load_config(input_data)

        assert result.is_success
        # File config should override input data (c.merge(data) means data wins)
        expected = D({"file": "/test", "KEY1": "input_value", "KEY2": "value2"})
        assert result.value == expected
        mock_get_config_file_path.assert_called_once_with(input_data)
        mock_dotenv_values.assert_called_once_with("/path/to/file")

    def test_merge_precedence_file_vs_input(self, mock_get_config_file_path, mock_dotenv_values):
        # Test that input data takes precedence over file config
        file_config = {"COMMON_KEY": "from_file", "FILE_ONLY": "file_value"}
        mock_get_config_file_path.return_value = success("/path/to/file")
        mock_dotenv_values.return_value = file_config

        input_data = D({"COMMON_KEY": "from_input", "INPUT_ONLY": "input_value"})
        result = load_config(input_data)

        assert result.is_success
        # Input should win for COMMON_KEY, both unique keys should be present
        expected = D(
            {
                "COMMON_KEY": "from_input",  # Input wins
                "FILE_ONLY": "file_value",  # From file
                "INPUT_ONLY": "input_value",  # From input
            }
        )
        assert result.value == expected

    def test_success_with_none_file_path(self, mock_get_config_file_path, mock_dotenv_values):
        mock_get_config_file_path.return_value = success(None)
        mock_dotenv_values.return_value = {}

        result = load_config(D({}))

        assert result.is_success
        assert isinstance(result.value, D)
        assert len(result.value) == 0
        mock_dotenv_values.assert_called_once_with(None)

    def test_failure_when_get_config_file_path_fails(self, mock_get_config_file_path):
        mock_get_config_file_path.return_value = failure(Exception("Path error"))

        result = load_config(D({}))

        assert result.is_failure
        assert "Path error" in str(result.error)

    def test_failure_when_dotenv_values_raises(
        self, mock_get_config_file_path, mock_dotenv_values
    ):
        mock_get_config_file_path.return_value = success("/path/to/file")
        mock_dotenv_values.side_effect = FileNotFoundError("File not found")

        result = load_config(D({}))

        assert result.is_failure
        assert "File not found" in str(result.error)


class TestConvertToJiraConfig:
    def test_returns_success_with_valid_config(self, config):
        # Add some extra data to verify it's preserved
        extended_config = {**config, "EXTRA_KEY": "extra_value"}
        d_config = D(extended_config)
        result = convert_to_jira_config(d_config)

        assert result.is_success
        assert isinstance(result.value, D)

        # Should have jira_config added
        assert "jira_config" in result.value
        assert isinstance(result.value.get("jira_config"), JiraConfig)

        # Should have removed the original JIRA_* keys
        assert "JIRA_SERVER" not in result.value
        assert "JIRA_EMAIL" not in result.value
        assert "JIRA_TOKEN" not in result.value
        assert "JIRA_PROJECT_KEY" not in result.value

        # Should preserve non-JIRA keys
        assert result.value.get("EXTRA_KEY") == "extra_value"

    def test_returns_failure_with_missing_required_fields(self):
        incomplete_config = D(
            {
                "JIRA_SERVER": "https://test.atlassian.net",
                "JIRA_EMAIL": "test@example.com",
                # Missing JIRA_TOKEN and JIRA_PROJECT_KEY
            }
        )

        result = convert_to_jira_config(incomplete_config)

        assert result.is_failure
        assert (
            "JIRA_TOKEN" in str(result.error)
            or "JIRA_PROJECT_KEY" in str(result.error)
            or "missing" in str(result.error).lower()
        )

    def test_returns_success_with_extra_fields_preserved(self, config):
        config_with_extra = D({**config, "EXTRA_FIELD": "preserved"})

        result = convert_to_jira_config(config_with_extra)

        assert result.is_success
        assert isinstance(result.value, D)

        # Extra field should be preserved (not ignored)
        assert result.value.get("EXTRA_FIELD") == "preserved"
        assert "jira_config" in result.value


class TestGetConfigRopPipeline:
    def test_successful_pipeline_execution_order(self, mock_pipeline_functions):
        # load_config merges input with file config
        mock_merged_config = D({"JIRA_SERVER": "server", "JIRA_EMAIL": "email", "input": "data"})
        mock_validated_config = D({"jira_config": "validated", "input": "data"})

        mock_pipeline_functions["load_config"].return_value = success(mock_merged_config)
        mock_pipeline_functions["convert_to_jira_config"].return_value = success(
            mock_validated_config
        )

        input_data = D({"input": "data"})
        result = get_config_rop(input_data)

        assert result.is_success
        assert result.value == mock_validated_config

        # Verify call order and arguments
        mock_pipeline_functions["load_config"].assert_called_once_with(input_data)
        mock_pipeline_functions["convert_to_jira_config"].assert_called_once_with(
            mock_merged_config
        )

    @pytest.mark.parametrize(
        "failing_function,error_message",
        [
            ("load_config", "Load failed"),
            ("convert_to_jira_config", "TypeError"),
        ],
    )
    def test_pipeline_short_circuits_on_failure(
        self, mock_pipeline_functions, failing_function, error_message
    ):
        # Success scenarios
        mock_pipeline_functions["load_config"].return_value = success(D({"config": "data"}))
        mock_pipeline_functions["convert_to_jira_config"].return_value = success(
            D({"merged": "data"})
        )

        # Set up the failure point
        if failing_function == "load_config":
            mock_pipeline_functions["load_config"].return_value = failure(Exception(error_message))
        elif failing_function == "convert_to_jira_config":
            mock_pipeline_functions["convert_to_jira_config"].return_value = failure(
                Exception(error_message)
            )

        result = get_config_rop(D({"test": "data"}))

        assert result.is_failure
        assert error_message in str(result.error)

        # Verify short-circuiting: functions after failure should not be called
        if failing_function == "load_config":
            mock_pipeline_functions["convert_to_jira_config"].assert_not_called()
        elif failing_function == "convert_to_jira_config":
            mock_pipeline_functions["load_config"].assert_called_once()
