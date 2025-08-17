from __future__ import annotations

import os
from typing import Any

from dotenv import dotenv_values

from ..betterdict import D
from ..core.models_rop import JiraConfig
from ..core.result import Result, pipe, safe


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
def get_config_file_path(data: D[str, str]) -> str | None:
    return data.get("file", discover_config_file())


def load_config(data: D[str, str | None]) -> Result[D[str, str | None], Exception]:
    return (
        get_config_file_path(data)
        .map(dotenv_values)
        .map(D)
        .map(lambda config: config.merge(data))
    )


@safe
def convert_to_jira_config(config: D[str, Any]) -> D[str, str]:
    jira_config = JiraConfig.from_dict(config)
    return (
        config
        .assoc("jira_config", jira_config)
        .dissoc(*jira_config.keys())
    )


def get_config_rop(data: D[str, str]) -> Result[D[str, str], Exception]:
    return pipe(
        data,
        load_config,
        convert_to_jira_config,
    )
