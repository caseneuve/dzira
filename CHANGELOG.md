# Changelog: `dzira`

## [0.3.1](https://github.com/caseneuve/dzira/releases/tag/v0.3.1)

### Fixed

* Getting issue's worklog should not crash when no worklogs found ([#36](https://github.com/caseneuve/dzira/issues/36))
* API should look only for issues of the authenticated team ([#35](https://github.com/caseneuve/dzira/issues/35))


## [0.3.0](https://github.com/caseneuve/dzira/releases/tag/v0.3.0)

### Changed

First steps toward modularity ([#5](https://github.com/caseneuve/dzira/issues/5)):

```
src/dzira
├── api.py
├── betterdict.py
└── cli
    ├── commands.py
    ├── config.py
    └── output.py
```

### TODO

- Need to extract data processing to `data.py`, so the "showing"
  commands (`ls`, `report`) can do only showing.
- Make an interface for `jira`, so eventually we can get rid of the
  `jira` package dependency and use our own Jira API wrapper.


## [0.2.1](https://github.com/caseneuve/dzira/releases/tag/v0.2) (pre)

### Fixed

* Updating worklog uses seconds as expected ([#22](https://github.com/caseneuve/dzira/issues/22))
* Properly catches error when a worklog is not found ([#22](https://github.com/caseneuve/dzira/issues/22))


## [0.2.0](https://github.com/caseneuve/dzira/releases/tag/v0.2) (2024-02-05)

### Added

* `--no-color` to disable coloring ([#1](https://github.com/caseneuve/dzira/issues/1)) 
* `--format` option in `ls` and `report` supporting `tabulate` formats (only
  `ls`), `csv` and `json` ([#2](https://github.com/caseneuve/dzira/issues/2),
  [#11](https://github.com/caseneuve/dzira/issues/11),
  [#13](https://github.com/caseneuve/dzira/issues/13))
* CHANGELOG (#20)

### Changed 

* `--log` command allows more than 60 minutes to log, when no hour provided, but
  will not let to log more than a day (8h)
  ([#9](https://github.com/caseneuve/dzira/issues/9))

### Fixed

* special characters (e.g. for colors) should be printed only in interactive
  shell ([#4](https://github.com/caseneuve/dzira/issues/4))
* `--no-spin` supresses all printing from the spinner
  ([#8](https://github.com/caseneuve/dzira/issues/8))


## [0.1.2](https://github.com/caseneuve/dzira/releases/tag/v0.1.2) (2023-12-15)

### Added

- `--version` option


## [0.1.1](https://github.com/caseneuve/dzira/releases/tag/v0.1.1) (2023-12-15)

### Added

- Pinned `click` version as the ones lower than `8.1.0` had breaking API for decorators

### Fixed

- `report` command decorator for consistency


## [0.1.0](https://github.com/caseneuve/dzira/releases/tag/v0.1) (2023-12-15)
