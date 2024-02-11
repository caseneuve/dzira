from tabulate import tabulate_formats


CONFIG_DIR_NAME = "dzira"
DOTFILE = f".{CONFIG_DIR_NAME}"
REQUIRED_KEYS = "JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT_KEY"
VALID_OUTPUT_FORMATS = sorted(tabulate_formats + ["json", "csv"])
DEFAULT_OUTPUT_FORMAT = "simple_grid"
