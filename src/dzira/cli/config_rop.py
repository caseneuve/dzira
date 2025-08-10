from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import dotenv_values

from ..betterdict import D
from ..core.result import Result, pipe, partial, safe


CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"
REQUIRED_KEYS = set(("JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT_KEY"))


def get_environment_paths() -> List[str]:
    config_file_dir = os.environ.get("XDG_CONFIG_HOME", os.environ.get("HOME", ""))
    home_dir = os.environ.get("HOME", "")

    return [
        os.path.join(config_file_dir, CONFIG_DIR_NAME, "env"),
        os.path.join(config_file_dir, DOTFILE),
        os.path.join(home_dir, ".config", CONFIG_DIR_NAME, "env"),
        os.path.join(home_dir, ".config", DOTFILE),
    ]


def discover_config_file() -> Optional[str]:
    return next(
        (path for path in get_environment_paths() if os.path.isfile(path)),
        None
    )


@safe
def get_config_file_path(data: D) -> str:
    return data.get("file", discover_config_file())


@safe
def check_required_keys(config: D) -> Dict[str, Any]:
    if missing_keys := REQUIRED_KEYS.difference(set(config.keys())):
        raise Exception(
            f"could not find required config values: "
            f"{', '.join(sorted(missing_keys))}"
        )
    return config


def load_config(data: D) -> Result[Dict[str, Any], Exception]:
    return (
        get_config_file_path(data)
        .map(dotenv_values)
    )


@safe
def merge_configs(data: D, config: D) -> Dict[str, Any]:
    return {**config, **data}


def get_config_rop(data: D) -> Result[D, Exception]:
    return pipe(
        data,
        load_config,
        partial(merge_configs, data),
        check_required_keys
    )
