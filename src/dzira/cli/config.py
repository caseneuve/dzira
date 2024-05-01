from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from tabulate import tabulate_formats

from dzira.betterdict import D


CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"
REQUIRED_KEYS = "JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT_KEY"
VALID_OUTPUT_FORMATS = sorted(tabulate_formats + ["json", "csv"])
DEFAULT_OUTPUT_FORMAT = "simple_grid"


def get_config_from_file(config_file: str | Path | None = None) -> dict:
    if config_file is None:
        config_file_dir = os.environ.get("XDG_CONFIG_HOME", os.environ["HOME"])
        for path in (
                os.path.join(config_file_dir, CONFIG_DIR_NAME, "env"),
                os.path.join(config_file_dir, DOTFILE),
                os.path.join(os.environ["HOME"], ".config", CONFIG_DIR_NAME, "env"),
                os.path.join(os.environ["HOME"], ".config", DOTFILE),
        ):
            if os.path.isfile(path):
                config_file = path
                break

    return dotenv_values(config_file)


def get_config(config: dict = {}) -> D:
    for cfg_fn in (
        lambda: get_config_from_file(config.get("file")),
        lambda: (_ for _ in ()).throw(
            Exception(
                "could not find required config values: "
                f"{', '.join(sorted(set(REQUIRED_KEYS).difference(set(config))))}"
            )
        ),
    ):
        if set(REQUIRED_KEYS).issubset(config.keys()):
            break
        config = {**cfg_fn(), **config}

    return D(config)
