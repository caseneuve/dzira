from __future__ import annotations

import os
from typing import Any

from dotenv import dotenv_values

from ..core.models_rop import JiraConfig
from ..core.result import Result, pipe, partial, safe


CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"


def get_environment_paths() -> list[str]:
    config_file_dir = os.environ.get("XDG_CONFIG_HOME", os.environ.get("HOME", ""))
    home_dir = os.environ.get("HOME", "")

    return [
        os.path.join(config_file_dir, CONFIG_DIR_NAME, "env"),
        os.path.join(config_file_dir, DOTFILE),
        os.path.join(home_dir, ".config", CONFIG_DIR_NAME, "env"),
        os.path.join(home_dir, ".config", DOTFILE),
    ]


def discover_config_file() -> str | None:
    return next((path for path in get_environment_paths() if os.path.isfile(path)), None)


@safe
def get_config_file_path(data: dict[str, Any]) -> str:
    return data.get("file", discover_config_file())


def load_config(data: dict[str, Any]) -> Result[dict[str, Any], Exception]:
    return get_config_file_path(data).map(dotenv_values)


@safe
def merge_configs(data: dict[str, Any], config: dict[str, Any]) -> dict[str, str]:
    return {**config, **data}


@safe
def convert_to_jira_config(config: dict[str, str]) -> JiraConfig:
    return JiraConfig.from_dict(config)


def get_config_rop(data: dict[str, Any]) -> Result[JiraConfig, Exception]:
    return pipe(
        data,
        load_config,
        partial(merge_configs, data),
        convert_to_jira_config,
    )
