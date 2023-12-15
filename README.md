`dzira` /dʑira/ is just `jira` /dʒɪrə/ pronounced in a slightly different way.

# Overview

```
Usage: dzira [OPTIONS] COMMAND [ARGS]...

  Configure JIRA connection by using default config files, environment
  variables, or options below. The discovery of default config files uses
  paths in the following order:

  - $XDG_CONFIG_HOME or $HOME/dzira/env
  - $XDG_CONFIG_HOME or $HOME/.dzira
  - $HOME/.config/dzira/env
  - $HOME/.config/.dzira

  Configuration requires setting values for:

  - JIRA_SERVER (the servers where your Jira instance is hosted on),
  - JIRA_EMAIL (the email you use to log into Jira),
  - JIRA_TOKEN (your Jira token),
  - JIRA_PROJECT_KEY (your team's project key)

Options:
  -f, --file PATH     Config file path
  -k, --key TEXT      JIRA_PROJECT_KEY value
  -t, --token TEXT    JIRA_TOKEN value
  -m, --email TEXT    JIRA_EMAIL value
  -s, --server TEXT   JIRA_SERVER value
  --spin / --no-spin  Control the spinner
  -h, --help          Show this message and exit.

Commands:
  log     Log time spent on ISSUE number or ISSUE with description...
  ls      List issues from the current sprint.
  report  Show work logged for today or for DATE.
```


## Persistent configuration

Create file `$XDG_CONFIG_HOME/dzira/env` (usually `~/.config/dzira/env`) 
or `$HOME/.dzira` (`~/.dzira`) with contents:

```text
JIRA_EMAIL=<your email used for Jira API>
JIRA_TOKEN=<your Jira API token>
JIRA_SERVER=<your Jira instance server name>
JIRA_PROJECT_KEY=<your Jira project key>
```


## Overriding settings

If you don't want to store your credentials in a file or want to override existing
ones, use relevant options or environment variables, for example:

This:

`python dzira.py --board XYZ ...`

is equivalent to:

`JIRA_BOARD=XYZ python dzira.py ...`


## Creating an API jira token

Once you're logged into your Jira instance, click on the profile icon (the upper
right corner), choose `Manage account`, then `Security` from the top menu and
`Create and manage API tokens` from the **API tokens** section, and lastly use
`Create API token` button.


# Commands

## `ls` commmand

```
Usage: dzira ls [OPTIONS]

  List issues from the current sprint.

  'Current sprint' is understood as the first 'active' sprint found. To avoid
  ambiguity, use --sprint-id option.

Options:
  -s, --state [active|closed]  Sprint state used for filtering  [default:
                               active]
  -i, --sprint-id INTEGER      Sprint id to get unambiguous result, helpful
                               when multiple active sprints; has precedence
                               over --state
  -h, --help                   Show this message and exit.
```


## `log` command

```
Usage: dzira log [OPTIONS] ISSUE

  Log time spent on ISSUE number or ISSUE with description containing matching
  string.

  TIME spent should be in format '[[Nh][ ]][Nm]'; or it can be calculated when
  START time is be provided;

  END time is optional, both should match 'H:M' format.

  Optionally a COMMENT text can be added.

  When WORKLOG id is present, it will update an existing log, rather then
  create a new one.  ISSUE is still required.

  To log work done in the past (but no older as 2 weeks), use --date option.
  It accepts the following patterns:

    "YYYY-mm-dd", "YYYY-mm-ddTHH:MM", "YYYY-mm-dd HH:MM".

  Time is assumed from the START option, if present and date is not
  specifying it.  The script will try to figure out local timezone and adjust
  the log started time accordingly.

Options:
  -t, --time TEXT        Time to spend in JIRA accepted format, e.g. '2h 10m'
  -s, --start TEXT       Time when the work started, e.g. '10:30', '12.45'
  -e, --end TEXT         Time when the work ended, e.g. '14:50', '16.10'
  -d, --date TEXT        Date when the work was done in ISO format, e.g.
                         2023-11-24, 2023-11-24 8:19, defaults to now; when
                         date matches %Y-%m-%d, time will be added from the
                         --start option, if present, or current time will be used
  -c, --comment TEXT     Comment added to logged time
  -w, --worklog INTEGER  Id of the worklog to be updated
  --spin / --no-spin
  -h, --help             Show this message and exit.
```


## `report` command

```
Usage: dzira report [OPTIONS]

  Show work logged for today or for DATE.

Options:
  -d, --date [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]
                                  Date to show report for
  -h, --help                      Show this message and exit.
```
