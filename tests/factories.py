from datetime import datetime, timedelta
from unittest.mock import Mock

from factory import (
    Factory,
    Sequence,
    Iterator,
    Faker,
    LazyFunction,
    LazyAttribute,
    lazy_attribute,
)
from faker import Faker as FakerLib
from jira.resources import (
    Board as JiraBoard,
    Sprint as JiraSprint,
    Issue as JiraIssue,
    Worklog as JiraWorklog,
)

from dzira.core.models import User, Board, Sprint, Issue, Worklog, WorklogEntry


# ====================================================================
# DOMAIN MODEL FACTORIES
# ====================================================================


class UserFactory(Factory):
    class Meta:
        model = User

    id = Sequence(lambda n: f"user{n}")
    display_name = Faker("name")
    email_address = LazyAttribute(
        lambda obj: f"{obj.display_name.lower().replace(' ', '.')}@example.com"
    )


class BoardFactory(Factory):
    class Meta:
        model = Board

    id = Sequence(lambda n: n + 1)
    name = Sequence(lambda n: f"Test Board {n}")
    project_key = Sequence(lambda n: f"PROJ{n}")


class SprintFactory(Factory):
    class Meta:
        model = Sprint

    id = Sequence(lambda n: n + 1)
    name = Sequence(lambda n: f"Sprint {n}")
    state = Iterator(["active", "closed", "future"])
    start_date = LazyFunction(lambda: datetime.now() - timedelta(days=7))
    end_date = LazyFunction(lambda: datetime.now() + timedelta(days=7))


class IssueFactory(Factory):
    class Meta:
        model = Issue

    key = Sequence(lambda n: f"TEST-{n}")
    summary = Faker("sentence", nb_words=6)
    status = Iterator(["To Do", "In Progress", "Done"])
    time_spent_seconds = Faker("random_int", min=0, max=28800)
    time_spent_display = LazyAttribute(
        lambda obj: (
            f"{obj.time_spent_seconds//3600}h {(obj.time_spent_seconds%3600)//60}m"
            if obj.time_spent_seconds
            else None
        )
    )
    time_estimate_seconds = Faker("random_int", min=3600, max=86400)
    time_remaining_estimate = LazyAttribute(
        lambda obj: (
            f"{obj.time_estimate_seconds//3600}h" if obj.time_estimate_seconds else None
        )
    )
    time_original_estimate = LazyAttribute(
        lambda obj: f"{(obj.time_estimate_seconds or 0)//3600 + 2}h"
    )


class WorklogFactory(Factory):
    class Meta:
        model = Worklog

    id = Sequence(lambda n: str(n))
    issue_key = Sequence(lambda n: f"TEST-{n}")
    time_spent_seconds = Faker("random_int", min=300, max=28800)
    comment = Faker("text", max_nb_chars=100)
    started = LazyFunction(lambda: datetime.now() - timedelta(hours=8))
    author_email = Faker("email")


class WorklogEntryFactory(Factory):
    class Meta:
        model = WorklogEntry

    issue_key = Sequence(lambda n: f"TEST-{n}")
    time_spent_seconds = Faker("random_int", min=300, max=28800)
    comment = Faker("text", max_nb_chars=100)
    started = LazyFunction(lambda: datetime.now() - timedelta(hours=1))


# ====================================================================
# JIRA OBJECT FACTORIES
# These create real jira.resources objects
# ====================================================================


class JiraResourceFactory(Factory):
    class Meta:
        abstract = True

    options = LazyAttribute(lambda _: {"server": "https://test.atlassian.net"})
    session = LazyAttribute(lambda _: Mock())


class JiraIssueFactory(JiraResourceFactory):
    class Meta:
        model = JiraIssue

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        issue_key = f"TEST-{fake.random_int(min=1, max=9999)}"
        issue_id = str(fake.random_int(min=10000, max=99999))

        return {
            "key": issue_key,
            "id": issue_id,
            "fields": {
                "summary": fake.sentence(nb_words=6),
                "status": {
                    "name": fake.random_element(["To Do", "In Progress", "Done"])
                },
                "timespent": fake.random_int(min=0, max=28800),
                "timetracking": {
                    "remainingEstimate": fake.random_element(
                        ["1d", "2d", "3d", "4h", "2h"]
                    ),
                    "originalEstimate": fake.random_element(
                        ["2d", "3d", "4d", "8h", "6h"]
                    ),
                    "timeSpent": fake.random_element(["1h", "2h", "4h", "30m"]),
                },
                "Sprint": [
                    {
                        "id": fake.random_int(min=1, max=1000),
                        "name": f"Sprint {fake.random_int(min=1, max=20)}",
                        "state": "active",
                    }
                ],
            },
        }


class JiraSprintFactory(JiraResourceFactory):
    class Meta:
        model = JiraSprint

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        sprint_id = fake.random_int(min=1, max=9999)
        sprint_name = f"Sprint {fake.random_int(min=1, max=50)}"
        state = fake.random_element(["active", "closed", "future"])
        start_date = (datetime.now() - timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        end_date = (datetime.now() + timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        return {
            "id": sprint_id,
            "name": sprint_name,
            "state": state,
            "startDate": start_date,
            "endDate": end_date,
        }


class JiraBoardFactory(JiraResourceFactory):
    class Meta:
        model = JiraBoard

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        board_id = fake.random_int(min=1, max=9999)
        board_name = f"Test Board {fake.random_int(min=1, max=100)}"

        return {
            "id": board_id,
            "name": board_name,
            "location": {"displayName": fake.company()},
        }


class JiraWorklogFactory(JiraResourceFactory):
    class Meta:
        model = JiraWorklog

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        time_spent_seconds = fake.random_int(min=300, max=28800)
        time_hours = time_spent_seconds // 3600
        time_display = (
            f"{time_hours}h" if time_hours > 0 else f"{time_spent_seconds//60}m"
        )

        worklog_id = fake.random_int(min=1, max=999999)
        issue_id = fake.random_int(min=1000, max=999999)

        return {
            "id": str(worklog_id),
            "issueId": str(issue_id),
            "timeSpent": time_display,
            "timeSpentSeconds": time_spent_seconds,
            "comment": fake.text(max_nb_chars=100),
            "started": (datetime.now() - timedelta(hours=8)).strftime(
                "%Y-%m-%dT%H:%M:%S.%f%z"
            ),
            "author": {
                "emailAddress": fake.email(),
                "displayName": fake.name(),
            },
        }


# ====================================================================
# FIELD-SPECIFIC JIRA FACTORIES
# These simulate different field responses from JIRA API
# ====================================================================


class JiraIssueMinimalFieldsFactory(JiraResourceFactory):
    class Meta:
        model = JiraIssue

    @lazy_attribute
    def raw(self):
        fake = FakerLib()
        issue_key = f"TEST-{fake.random_int(min=1, max=9999)}"
        issue_id = str(fake.random_int(min=10000, max=99999))

        return {
            "key": issue_key,
            "id": issue_id,
            "fields": {
                "summary": fake.sentence(nb_words=6),
                "status": {
                    "name": fake.random_element(["To Do", "In Progress", "Done"])
                },
                # Note: No timespent, timetracking, or Sprint fields
            },
        }


class JiraIssueWorklogFieldsFactory(JiraResourceFactory):
    class Meta:
        model = JiraIssue

    @lazy_attribute
    def raw(self):
        fake = FakerLib()
        issue_key = f"TEST-{fake.random_int(min=1, max=9999)}"
        issue_id = str(fake.random_int(min=10000, max=99999))

        return {
            "key": issue_key,
            "id": issue_id,
            "fields": {
                "summary": fake.sentence(nb_words=6),
                "worklog": {
                    "total": fake.random_int(min=0, max=5),
                    "worklogs": [
                        {
                            "id": str(fake.random_int(min=1, max=999)),
                            "timeSpent": "2h",
                            "timeSpentSeconds": 7200,
                            "comment": fake.text(max_nb_chars=50),
                            "started": (datetime.now() - timedelta(hours=2)).strftime(
                                "%Y-%m-%dT%H:%M:%S.%f%z"
                            ),
                            "author": {
                                "emailAddress": fake.email(),
                                "displayName": fake.name(),
                            },
                        }
                    ],
                },
                # Note: No Sprint, timespent, or timetracking fields
            },
        }


class JiraIssueSprintOnlyFactory(JiraResourceFactory):
    class Meta:
        model = JiraIssue

    @lazy_attribute
    def raw(self):
        fake = FakerLib()
        issue_key = f"TEST-{fake.random_int(min=1, max=9999)}"
        issue_id = str(fake.random_int(min=10000, max=99999))

        return {
            "key": issue_key,
            "id": issue_id,
            "fields": {
                "customfield_10121": [
                    {
                        "id": fake.random_int(min=1, max=1000),
                        "name": f"Sprint {fake.random_int(min=1, max=20)}",
                        "state": "active",
                        "startDate": (datetime.now() - timedelta(days=7)).strftime(
                            "%Y-%m-%dT%H:%M:%S.%fZ"
                        ),
                        "endDate": (datetime.now() + timedelta(days=7)).strftime(
                            "%Y-%m-%dT%H:%M:%S.%fZ"
                        ),
                    }
                ],
                # Note: No summary, status, timespent, or timetracking fields
            },
        }


class JiraIssueParametricFactory(JiraResourceFactory):
    class Meta:
        model = JiraIssue
        exclude = ["requested_fields"]  # Don't pass this to the constructor

    # Default to all fields if not specified
    requested_fields = [
        "summary",
        "status",
        "timespent",
        "timetracking",
        "customfield_10121",
    ]

    @lazy_attribute
    def raw(self):
        fake = FakerLib()
        issue_key = f"TEST-{fake.random_int(min=1, max=9999)}"
        issue_id = str(fake.random_int(min=10000, max=99999))

        # Base structure always present
        result = {
            "key": issue_key,
            "id": issue_id,
            "fields": {},
        }

        # Build fields dict based on requested_fields
        fields = result["fields"]

        if "summary" in self.requested_fields:
            fields["summary"] = fake.sentence(nb_words=6)

        if "status" in self.requested_fields:
            fields["status"] = {
                "name": fake.random_element(["To Do", "In Progress", "Done"])
            }

        if "timespent" in self.requested_fields:
            fields["timespent"] = fake.random_int(min=0, max=28800)

        if "timetracking" in self.requested_fields:
            fields["timetracking"] = {
                "remainingEstimate": fake.random_element(
                    ["1d", "2d", "3d", "4h", "2h"]
                ),
                "originalEstimate": fake.random_element(["2d", "3d", "4d", "8h", "6h"]),
                "timeSpent": fake.random_element(["1h", "2h", "4h", "30m"]),
            }

        if "customfield_10121" in self.requested_fields:
            fields["customfield_10121"] = [
                {
                    "id": fake.random_int(min=1, max=1000),
                    "name": f"Sprint {fake.random_int(min=1, max=20)}",
                    "state": "active",
                    "startDate": (datetime.now() - timedelta(days=7)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                    "endDate": (datetime.now() + timedelta(days=7)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                }
            ]

        if "Sprint" in self.requested_fields:  # Legacy Sprint field
            fields["Sprint"] = [
                {
                    "id": fake.random_int(min=1, max=1000),
                    "name": f"Sprint {fake.random_int(min=1, max=20)}",
                    "state": "active",
                }
            ]

        if "worklog" in self.requested_fields:
            fields["worklog"] = {
                "total": fake.random_int(min=0, max=5),
                "worklogs": [
                    {
                        "id": str(fake.random_int(min=1, max=999)),
                        "timeSpent": "2h",
                        "timeSpentSeconds": 7200,
                        "comment": fake.text(max_nb_chars=50),
                        "started": (datetime.now() - timedelta(hours=2)).strftime(
                            "%Y-%m-%dT%H:%M:%S.%f%z"
                        ),
                        "author": {
                            "emailAddress": fake.email(),
                            "displayName": fake.name(),
                        },
                    }
                ],
            }

        return result


# ====================================================================
# SPECIALIZED FACTORIES
# ====================================================================


class ActiveSprintFactory(SprintFactory):
    state = "active"
    start_date = LazyFunction(lambda: datetime.now() - timedelta(days=3))
    end_date = LazyFunction(lambda: datetime.now() + timedelta(days=11))


class InProgressIssueFactory(IssueFactory):
    status = "In Progress"
    time_spent_seconds = Faker("random_int", min=3600, max=14400)


class CompletedWorklogFactory(WorklogFactory):
    started = LazyFunction(lambda: datetime.now() - timedelta(days=1))
    time_spent_seconds = Faker("random_int", min=1800, max=7200)


class ActiveJiraSprintFactory(JiraSprintFactory):

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        sprint_id = fake.random_int(min=1, max=9999)
        sprint_name = f"Sprint {fake.random_int(min=1, max=50)}"
        start_date = (datetime.now() - timedelta(days=3)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        end_date = (datetime.now() + timedelta(days=11)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        return {
            "id": sprint_id,
            "name": sprint_name,
            "state": "active",  # Fixed to active
            "startDate": start_date,
            "endDate": end_date,
        }


class InProgressJiraIssueFactory(JiraIssueFactory):

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        issue_key = f"TEST-{fake.random_int(min=1, max=9999)}"
        issue_id = str(fake.random_int(min=10000, max=99999))

        return {
            "key": issue_key,
            "id": issue_id,
            "fields": {
                "summary": fake.sentence(nb_words=6),
                "status": {"name": "In Progress"},
                "timespent": fake.random_int(min=3600, max=14400),  # 1-4 hours
                "timetracking": {
                    "remainingEstimate": fake.random_element(
                        ["1d", "2d", "3d", "4h", "2h"]
                    ),
                    "originalEstimate": fake.random_element(
                        ["2d", "3d", "4d", "8h", "6h"]
                    ),
                    "timeSpent": fake.random_element(["1h", "2h", "4h", "30m"]),
                },
                "Sprint": [
                    {
                        "id": fake.random_int(min=1, max=1000),
                        "name": f"Sprint {fake.random_int(min=1, max=20)}",
                        "state": "active",
                    }
                ],
            },
        }


class JiraWorklogWithTimeFactory(JiraWorklogFactory):

    @lazy_attribute
    def raw(self):
        fake = FakerLib()

        return {
            "id": str(fake.random_int(min=1, max=999999)),
            "issueId": str(fake.random_int(min=1000, max=999999)),
            "timeSpent": "2h",  # Fixed time
            "timeSpentSeconds": 7200,  # 2 hours
            "comment": fake.text(max_nb_chars=100),
            "started": (datetime.now() - timedelta(hours=8)).strftime(
                "%Y-%m-%dT%H:%M:%S.%f%z"
            ),
            "author": {
                "emailAddress": fake.email(),
                "displayName": fake.name(),
            },
        }


# ====================================================================
# HELPER FUNCTIONS FOR FIELD-SPECIFIC FACTORIES
# ====================================================================


def create_jira_issue_with_fields(fields):
    """
    Convenient helper to create JIRA issues with specific fields.

    Args:
        fields (list): List of field names to include in the response

    Returns:
        JiraIssue: A JIRA Issue object with only the specified fields

    Example:
        # Simulate API call: jira.search_issues(fields="summary,status")
        issue = create_jira_issue_with_fields(["summary", "status"])

        # Simulate API call: jira.search_issues(fields="worklog,summary")
        issue = create_jira_issue_with_fields(["worklog", "summary"])
    """
    return JiraIssueParametricFactory(requested_fields=fields)


def create_jira_issues_for_api_scenario(scenario_name):
    """
    Create JIRA issues for common API usage scenarios.

    Args:
        scenario_name (str): One of the predefined scenarios

    Returns:
        JiraIssue: A JIRA Issue object configured for the specified scenario

    Available scenarios:
        - "search_basic": Basic search with summary and status
        - "search_with_time": Search with time tracking fields
        - "search_with_sprint": Search with sprint information
        - "search_with_worklog": Search with worklog data
        - "search_full": Full search with all fields
    """
    scenarios = {
        "search_basic": ["summary", "status"],
        "search_with_time": ["summary", "status", "timespent", "timetracking"],
        "search_with_sprint": ["summary", "status", "customfield_10121"],
        "search_with_worklog": ["summary", "worklog"],
        "search_full": [
            "summary",
            "status",
            "timespent",
            "timetracking",
            "customfield_10121",
            "worklog",
        ],
    }

    if scenario_name not in scenarios:
        raise ValueError(
            f"Unknown scenario '{scenario_name}'. Available: {list(scenarios.keys())}"
        )

    return create_jira_issue_with_fields(scenarios[scenario_name])


# Common field combinations used in the codebase
DEFAULT_ISSUE_FIELDS = [
    "summary",
    "status",
    "timespent",
    "timetracking",
    "customfield_10121",
]
WORKLOG_REPORT_FIELDS = ["worklog", "summary"]
SPRINT_QUERY_FIELDS = [
    "customfield_10121",
    "status",
    "summary",
    "timespent",
    "timeestimate",
    "timetracking",
]
