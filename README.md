`dzira` /dʑira/ is just `jira` /dʒɪrə/ pronounced in a slightly different way.

# Overview

```
Usage: dzira.py [OPTIONS] COMMAND [ARGS]...

  Configure JIRA connection by using config files (XDG_CONFIG_HOME/dzira/env
  or ~/.dzira), environment variables, or options below:

Options:
  -f, --file FILENAME  Config file path
  -o, --board TEXT     JIRA_BOARD value
  -k, --token TEXT     JIRA_TOKEN value
  -m, --email TEXT     JIRA_EMAIL value
  -d, --server TEXT    JIRA_SERVER value
  --help               Show this message and exit.

Commands:
  log  Log time spent on ISSUE number or ISSUE with description...
  ls   List issues from the current sprint
```


## Persistent configuration

Create file `$XDG_CONFIG_HOME/dzira/env` (usually `~/.config/dzira/env`) 
or `$HOME/.dzira` (`~/.dzira`) with contents:

```sh
JIRA_EMAIL=<your email used for Jira API>
JIRA_TOKEN=<your Jira API token>
JIRA_SERVER=<your Jira instance server name>
JIRA_BOARD=<your Jira Board name>
```


## Overriding settings

If you don't want to store your credentials in a file or want to override existing
ones, use relevant options or environment variables, for example:

This:

`python dzira.py --board XYZ ...`

is equivalent to:

`JIRA_BOARD=XYZ python dzira.py ...`


# Commands

## `ls` commmand

```
Usage: dzira.py ls [OPTIONS]

  List issues from the current sprint

Options:
  --help  Show this message and exit.
```


## `log` command

```
Usage: dzira.py log [OPTIONS] ISSUE

  Log time spent on ISSUE number or ISSUE with description containing matching
  string.

  TIME spent should be in format '[Nh] [Nm]'; or it can be calculated when
  START time is be provided;

  END time is optional, both should match 'H:M' format.

  Optionally a COMMENT text can be added.

  When WORKLOG id is present, it will update an existing log, rather then
  create a new one.

Options:
  -t, --time TEXT        Time to spend in JIRA accepted format, e.g. '2h 10m'
  -s, --start TEXT       Time when the work started, e.g. '10:30', '12.45'
  -e, --end TEXT         Time when the work ended, e.g. '14:50', '16.10'
  -c, --comment TEXT     Comment added to logged time
  -w, --worklog INTEGER  Id of the worklog to be updated
  --help                 Show this message and exit.
```
