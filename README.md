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
  --spin / --no-spin    Control the spinner  [default: spin]
  --color / --no-color  Control colors  [default: color]
  -h, --help          Show this message and exit
  --version           Show the version and exit

Commands:
  log     Log time spent on ISSUE number or ISSUE with description...
  ls      List issues from the current sprint.
  report  Show work logged for today or for DATE using given FORMAT.
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

`dzira --board XYZ ...`

is equivalent to:

`JIRA_BOARD=XYZ dzira ...`


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

  Format can be one of supported TABULATE formats or CSV, JSON.

  Examples of parsable formats:

  CSV format:
    sprint_id,key,summary,state,spent,estimated
    42,XY-250,New feature,To Do,,4h
    42,XY-214,Upgrade foo to 9.99,In Progress,0:30:00,2d 7h 30m (3d)

  JSON format:
    {
      "sprint": {
        "name": "Iteration 42",
        "id": 42,
        "start": "2024-01-01T08:00:00.000Z",
        "end": "2024-01-14T16:00:00.000Z"
      },
      "issues": [
        {
          "key": "XY-250",
          "summary": "New feature",
          "state": "To Do",
          "spent": null,
          "estimated": 4h
        }
      ]
    }

Options:
  -s, --state [active|closed]  Sprint state used for filtering  [default:
                               active]
  -i, --sprint-id INTEGER      Sprint id to get unambiguous result, helpful
                               when multiple active sprints; has precedence
                               over --state
  -f, --format TEXT            Output format: supports TABULATE formats + CSV
                               and JSON  [default: simple_grid]
  -h, --help                   Show this message and exit.
```


## `log` command

```
Usage: dzira log [OPTIONS] ISSUE

  Log time spent on ISSUE number or ISSUE with description containing matching
  string.

  TIME spent should be in format '[[Nh][ ]][Nm]'; or it can be calculated when
  START time is be provided; it's assumed that time spent for a single task
  cannot be greater than 1 day (8 hours).

  END time is optional, both should match 'H:M' format.

  Optionally a COMMENT text can be added.

  When WORKLOG id is present, it will update an existing log, rather then
  create a new one.  ISSUE is still required.

  To log work done in the past (but no older as 2 weeks), use --date option.
  It accepts the following patterns:

    "YYYY-mm-dd", "YYYY-mm-ddTHH:MM", "YYYY-mm-dd HH:MM".

  Time is calculated from the START option, if present, and date is
  not specifying it.  The script will try to figure out local
  timezone and adjust the log started time accordingly.

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

  Show work logged for today or for DATE using given FORMAT.

  TABLE format (default) will print a table with summary showing worklogs for
  every issue having work logged on given DATE.

  CSV and JSON formats are indended to be parsable.

  CSV format:
    issue, summary, worklog, started, spent, spent_seconds, comment
    XY-1,Foo bar,1234,12:45:00,1h 15m,4500,implementing foo in bar

  JSON format:
    {
      "issues": [
        {
          "key": "XY-1",
          "summary": "Foo bar",
          "issue_total_time": "1h 15m",
          "issue_total_spent_seconds": 4500,
          "worklogs": [
            {
              "id": "1",
              "started": "12:45:00",
              "spent": "1h 15m",
              "spent_seconds": 4500,
              "comment": "implementing foo in bar"
            }
          ]
        },
      ],
      "total_time": "1h 15m",
      "total_seconds": 4500
    }

Options:
  -d, --date [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]
                                  Date to show report for
  -f, --format [table|csv|json]   How to display the report  [default: table]
  -h, --help                      Show this message and exit
```
