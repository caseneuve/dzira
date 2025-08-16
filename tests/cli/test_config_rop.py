import os
from collections import OrderedDict

import pytest

from dzira.cli.config_rop import (
    convert_to_jira_config,
    discover_config_file,
    get_config_file_path,
    get_config_rop,
    get_environment_paths,
    load_config,
    merge_configs,
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
        "merge_configs": mocker.patch("dzira.cli.config_rop.merge_configs"),
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
        mock_config = OrderedDict([("KEY1", "value1"), ("KEY2", "value2")])
        mock_get_config_file_path.return_value = success("/path/to/file")
        mock_dotenv_values.return_value = mock_config

        result = load_config(D({"file": "/test"}))

        assert result.is_success
        assert result.value == mock_config
        mock_get_config_file_path.assert_called_once_with(D({"file": "/test"}))
        mock_dotenv_values.assert_called_once_with("/path/to/file")

    def test_success_with_none_file_path(self, mock_get_config_file_path, mock_dotenv_values):
        mock_get_config_file_path.return_value = success(None)
        mock_dotenv_values.return_value = OrderedDict()

        result = load_config(D({}))

        assert result.is_success
        assert isinstance(result.value, OrderedDict)
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


class TestMergeConfigs:
    def test_input_data_overrides_file_config(self):
        input_data = D({"KEY1": "input_value", "KEY2": "input_only"})
        file_config = D({"KEY1": "file_value", "KEY3": "file_only"})

        result = merge_configs(input_data, file_config)

        assert result.is_success and result.value
        merged = result.value
        assert merged["KEY1"] == "input_value"  # Input wins
        assert merged["KEY2"] == "input_only"  # From input
        assert merged["KEY3"] == "file_only"  # From file

    def test_handles_empty_configs(self):
        result = merge_configs(D({}), D({}))

        assert result.is_success and result.value is not None
        assert len(result.value) == 0

    def test_none_values_override(self):
        input_data = D({"KEY1": None})
        file_config = D({"KEY1": "file_value"})

        result = merge_configs(input_data, file_config)

        assert result.is_success and result.value
        assert result.value["KEY1"] is None


class TestConvertToJiraConfig:
    def test_returns_success_with_valid_config(self, config):
        result = convert_to_jira_config(config)

        assert result.is_success
        assert isinstance(result.value, JiraConfig)

    def test_returns_failure_with_missing_required_fields(self):
        incomplete_config = {
            "JIRA_SERVER": "https://test.atlassian.net",
            "JIRA_EMAIL": "test@example.com",
            # Missing JIRA_TOKEN and JIRA_PROJECT_KEY
        }

        result = convert_to_jira_config(incomplete_config)

        assert result.is_failure
        assert (
            "JIRA_TOKEN" in str(result.error)
            or "JIRA_PROJECT_KEY" in str(result.error)
            or "missing" in str(result.error).lower()
        )

    def test_returns_success_with_extra_fields_ignored(self, config):
        config_with_extra = {**config, "EXTRA_FIELD": "ignored"}

        result = convert_to_jira_config(config_with_extra)

        assert result.is_success
        assert isinstance(result.value, JiraConfig)


class TestGetConfigRopPipeline:
    def test_successful_pipeline_execution_order(self, mock_pipeline_functions):
        mock_file_config = {"JIRA_SERVER": "server", "JIRA_EMAIL": "email"}
        mock_merged_config = {
            **mock_file_config,
            "input": "data",
        }
        mock_validated_config = mock_merged_config

        mock_pipeline_functions["load_config"].return_value = success(mock_file_config)
        mock_pipeline_functions["merge_configs"].return_value = success(mock_merged_config)
        mock_pipeline_functions["convert_to_jira_config"].return_value = success(
            mock_validated_config
        )

        input_data = D({"input": "data"})
        result = get_config_rop(input_data)

        assert result.is_success
        assert result.value == mock_validated_config

        # Verify call order and arguments
        mock_pipeline_functions["load_config"].assert_called_once_with(input_data)
        mock_pipeline_functions["merge_configs"].assert_called_once_with(
            input_data, mock_file_config
        )
        mock_pipeline_functions["convert_to_jira_config"].assert_called_once_with(
            mock_merged_config
        )

    @pytest.mark.parametrize(
        "failing_function,error_message",
        [
            ("load_config", "Load failed"),
            ("merge_configs", "Merge failed"),
            ("convert_to_jira_config", "TypeError"),
        ],
    )
    def test_pipeline_short_circuits_on_failure(
        self, mock_pipeline_functions, failing_function, error_message
    ):
        # Success scenarios
        mock_pipeline_functions["load_config"].return_value = success({"config": "data"})
        mock_pipeline_functions["merge_configs"].return_value = success({"merged": "data"})
        mock_pipeline_functions["convert_to_jira_config"].return_value = success(
            {"merged": "data"}
        )

        # Set up the failure point
        if failing_function == "load_config":
            mock_pipeline_functions["load_config"].return_value = failure(Exception(error_message))
        elif failing_function == "merge_configs":
            mock_pipeline_functions["merge_configs"].return_value = failure(
                Exception(error_message)
            )
        elif failing_function == "convert_to_jira_config":
            mock_pipeline_functions["convert_to_jira_config"].return_value = failure(
                Exception(error_message)
            )

        result = get_config_rop(D({"test": "data"}))

        assert result.is_failure
        assert error_message in str(result.error)

        # Verify short-circuiting: functions after failure should not be called
        if failing_function == "load_config":
            mock_pipeline_functions["merge_configs"].assert_not_called()
            mock_pipeline_functions["convert_to_jira_config"].assert_not_called()
        elif failing_function == "merge_configs":
            mock_pipeline_functions["load_config"].assert_called_once()
            mock_pipeline_functions["convert_to_jira_config"].assert_not_called()
        elif failing_function == "convert_to_jira_config":
            mock_pipeline_functions["load_config"].assert_called_once()
            mock_pipeline_functions["merge_configs"].assert_called_once()
