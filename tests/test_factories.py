import pytest
from datetime import datetime, timedelta

from tests.factories import (
    # Domain model factories
    UserFactory,
    BoardFactory,
    SprintFactory,
    IssueFactory,
    WorklogFactory,
    WorklogEntryFactory,
    # JIRA object factories
    JiraIssueFactory,
    JiraSprintFactory,
    JiraBoardFactory,
    JiraWorklogFactory,
    # Field-specific JIRA factories
    JiraIssueMinimalFieldsFactory,
    JiraIssueWorklogFieldsFactory,
    JiraIssueSprintOnlyFactory,
    JiraIssueParametricFactory,
    # Specialized factories
    ActiveSprintFactory,
    InProgressIssueFactory,
    CompletedWorklogFactory,
    ActiveJiraSprintFactory,
    InProgressJiraIssueFactory,
    JiraWorklogWithTimeFactory,
    # Helper functions
    create_jira_issue_with_fields,
    create_jira_issues_for_api_scenario,
    DEFAULT_ISSUE_FIELDS,
    WORKLOG_REPORT_FIELDS,
    SPRINT_QUERY_FIELDS,
    JiraConfigFactory,
)

from dzira.core.models import User, Board, Sprint, Issue, Worklog, WorklogEntry
from jira.resources import (
    Issue as JiraIssue,
    Sprint as JiraSprint,
    Board as JiraBoard,
    Worklog as JiraWorklog,
)


class TestDomainModelFactories:

    def test_user_factory_creates_user_instance(self):
        user = UserFactory()

        assert isinstance(user, User)
        assert user.id.startswith("user")
        assert "@example.com" in user.email_address
        assert user.display_name
        assert user.email_address == f"{user.display_name.lower().replace(' ', '.')}@example.com"

    def test_user_factory_with_custom_attributes(self):
        user = UserFactory(display_name="John Doe", email_address="john@test.com")

        assert user.display_name == "John Doe"
        assert user.email_address == "john@test.com"

    def test_board_factory_creates_board_instance(self):
        board = BoardFactory()

        assert isinstance(board, Board)
        assert board.id > 0
        assert board.name.startswith("Test Board")
        assert board.project_key.startswith("PROJ")

    def test_board_factory_with_custom_attributes(self):
        board = BoardFactory(name="Custom Board", project_key="CUST")

        assert board.name == "Custom Board"
        assert board.project_key == "CUST"

    def test_sprint_factory_creates_sprint_instance(self):
        sprint = SprintFactory()

        assert isinstance(sprint, Sprint)
        assert sprint.id > 0
        assert sprint.name.startswith("Sprint")
        assert sprint.state in ["active", "closed", "future"]
        assert isinstance(sprint.start_date, datetime)
        assert isinstance(sprint.end_date, datetime)
        assert sprint.end_date > sprint.start_date

    def test_issue_factory_creates_issue_instance(self):
        issue = IssueFactory()

        assert isinstance(issue, Issue)
        assert issue.key.startswith("TEST-")
        assert issue.summary
        assert issue.status in ["To Do", "In Progress", "Done"]
        assert isinstance(issue.time_spent_seconds, int)
        assert issue.time_spent_seconds >= 0
        assert isinstance(issue.time_estimate_seconds, int)
        assert issue.time_estimate_seconds > 0

    def test_issue_factory_time_display_formatting(self):
        issue = IssueFactory(time_spent_seconds=7200)  # 2 hours

        assert issue.time_spent_display == "2h 0m"

    def test_issue_factory_time_display_with_minutes(self):
        issue = IssueFactory(time_spent_seconds=5400)  # 1.5 hours

        assert issue.time_spent_display == "1h 30m"

    def test_issue_factory_zero_time_spent(self):
        issue = IssueFactory(time_spent_seconds=0)

        assert issue.time_spent_display is None

    def test_worklog_factory_creates_worklog_instance(self):
        worklog = WorklogFactory()

        assert isinstance(worklog, Worklog)
        assert worklog.id
        assert worklog.issue_key.startswith("TEST-")
        assert isinstance(worklog.time_spent_seconds, int)
        assert worklog.time_spent_seconds >= 300  # At least 5 minutes
        assert worklog.comment
        assert isinstance(worklog.started, datetime)
        assert "@" in worklog.author_email

    def test_worklog_entry_factory_creates_worklog_entry_instance(self):
        entry = WorklogEntryFactory()

        assert isinstance(entry, WorklogEntry)
        assert entry.issue_key.startswith("TEST-")
        assert isinstance(entry.time_spent_seconds, int)
        assert entry.time_spent_seconds >= 300
        assert entry.comment
        assert isinstance(entry.started, datetime)

    def test_factory_batch_creation(self):
        users = UserFactory.create_batch(3)

        assert len(users) == 3
        assert all(isinstance(user, User) for user in users)
        assert len(set(user.id for user in users)) == 3  # All unique IDs


class TestJiraObjectFactories:

    def test_jira_issue_factory_creates_jira_issue_instance(self):
        issue = JiraIssueFactory()

        assert isinstance(issue, JiraIssue)
        assert isinstance(issue.raw, dict)
        assert "key" in issue.raw
        assert "fields" in issue.raw
        # Test that JIRA object has expected attributes from raw data
        assert hasattr(issue, "key")
        assert hasattr(issue, "id")

    def test_jira_issue_factory_fields_structure(self):
        issue = JiraIssueFactory()

        fields = issue.raw["fields"]
        assert "summary" in fields
        assert "status" in fields
        assert "timespent" in fields
        assert "timetracking" in fields
        assert "Sprint" in fields

    def test_jira_issue_factory_key_format(self):
        issue = JiraIssueFactory()

        assert issue.raw["key"].startswith("TEST-")
        assert isinstance(issue.raw["id"], str)

    def test_jira_sprint_factory_creates_jira_sprint_instance(self):
        sprint = JiraSprintFactory()

        assert isinstance(sprint, JiraSprint)
        assert isinstance(sprint.raw, dict)
        # Test that JIRA object has expected attributes from raw data
        assert hasattr(sprint, "id")
        assert hasattr(sprint, "name")

    def test_jira_sprint_factory_raw_structure(self):
        sprint = JiraSprintFactory()

        raw = sprint.raw
        assert "id" in raw
        assert "name" in raw
        assert "state" in raw
        assert "startDate" in raw
        assert "endDate" in raw
        assert raw["state"] in ["active", "closed", "future"]

    def test_jira_sprint_factory_date_formatting(self):
        sprint = JiraSprintFactory()

        # Check ISO format with Z suffix
        assert sprint.raw["startDate"].endswith("Z")
        assert sprint.raw["endDate"].endswith("Z")
        assert "T" in sprint.raw["startDate"]
        assert "T" in sprint.raw["endDate"]

    def test_jira_board_factory_creates_jira_board_instance(self):
        board = JiraBoardFactory()

        assert isinstance(board, JiraBoard)
        assert isinstance(board.raw, dict)
        assert "location" in board.raw
        assert "displayName" in board.raw["location"]
        # Test that JIRA object has expected attributes from raw data
        assert hasattr(board, "id")
        assert hasattr(board, "name")

    def test_jira_worklog_factory_creates_jira_worklog_instance(self):
        worklog = JiraWorklogFactory()

        assert isinstance(worklog, JiraWorklog)
        assert isinstance(worklog.raw, dict)
        # Test that JIRA object has expected attributes from raw data
        assert hasattr(worklog, "id")

    def test_jira_worklog_factory_raw_structure(self):
        worklog = JiraWorklogFactory()

        raw = worklog.raw
        assert "id" in raw
        assert "issueId" in raw
        assert "timeSpent" in raw
        assert "timeSpentSeconds" in raw
        assert "comment" in raw
        assert "started" in raw
        assert "author" in raw
        assert "emailAddress" in raw["author"]
        assert "displayName" in raw["author"]

    def test_jira_worklog_factory_time_formatting(self):
        worklog = JiraWorklogFactory()

        time_spent = worklog.raw["timeSpent"]
        # Should be formatted as "Xh" or "Xm"
        assert time_spent.endswith("h") or time_spent.endswith("m")


class TestSpecializedFactories:

    def test_active_sprint_factory(self):
        sprint = ActiveSprintFactory()

        assert isinstance(sprint, Sprint)
        assert sprint.state == "active"
        # Should be currently running (started in past, ends in future)
        now = datetime.now()
        assert sprint.start_date < now < sprint.end_date

    def test_in_progress_issue_factory(self):
        issue = InProgressIssueFactory()

        assert isinstance(issue, Issue)
        assert issue.status == "In Progress"
        # Should have reasonable time logged (1-4 hours)
        assert 3600 <= issue.time_spent_seconds <= 14400

    def test_completed_worklog_factory(self):
        worklog = CompletedWorklogFactory()

        assert isinstance(worklog, Worklog)
        # Should be from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        assert worklog.started.date() == yesterday.date()
        # Should have reasonable time (30min-2h)
        assert 1800 <= worklog.time_spent_seconds <= 7200

    def test_active_jira_sprint_factory(self):
        sprint = ActiveJiraSprintFactory()

        assert isinstance(sprint, JiraSprint)
        assert sprint.raw["state"] == "active"
        # Should be currently running
        start_date = datetime.strptime(sprint.raw["startDate"], "%Y-%m-%dT%H:%M:%S.%fZ")
        end_date = datetime.strptime(sprint.raw["endDate"], "%Y-%m-%dT%H:%M:%S.%fZ")
        now = datetime.now()
        assert start_date < now < end_date

    def test_in_progress_jira_issue_factory(self):
        issue = InProgressJiraIssueFactory()

        assert isinstance(issue, JiraIssue)
        assert issue.raw["fields"]["status"]["name"] == "In Progress"
        # Should have reasonable time logged
        assert 3600 <= issue.raw["fields"]["timespent"] <= 14400

    def test_jira_worklog_with_time_factory(self):
        worklog = JiraWorklogWithTimeFactory()

        assert isinstance(worklog, JiraWorklog)
        assert worklog.raw["timeSpent"] == "2h"
        assert worklog.raw["timeSpentSeconds"] == 7200


class TestFactoryCustomization:

    def test_factory_with_build_strategy(self):
        # Test build() vs create() - both should work
        user_built = UserFactory.build()
        user_created = UserFactory.create()

        assert isinstance(user_built, User)
        assert isinstance(user_created, User)
        assert user_built.id != user_created.id

    def test_factory_with_stub_strategy(self):
        user_stub = UserFactory.stub()

        # Stub should have attributes but might not be full instance
        assert hasattr(user_stub, "id")
        assert hasattr(user_stub, "display_name")
        assert hasattr(user_stub, "email_address")

    def test_factory_sequence_uniqueness(self):
        users = [UserFactory() for _ in range(5)]
        issues = [IssueFactory() for _ in range(5)]

        # All IDs should be unique
        user_ids = [user.id for user in users]
        issue_keys = [issue.key for issue in issues]

        assert len(set(user_ids)) == 5
        assert len(set(issue_keys)) == 5

    def test_factory_lazy_attribute_evaluation(self):
        # Test that lazy attributes are properly evaluated
        issue1 = IssueFactory(time_spent_seconds=3600)
        issue2 = IssueFactory(time_spent_seconds=7200)

        assert issue1.time_spent_display == "1h 0m"
        assert issue2.time_spent_display == "2h 0m"

    def test_factory_iterator_cycling(self):
        # Test that iterators cycle through values
        sprints = [SprintFactory() for _ in range(10)]
        states = [sprint.state for sprint in sprints]

        # Should have all three states represented (cycling)
        unique_states = set(states)
        assert len(unique_states) <= 3
        assert unique_states.issubset({"active", "closed", "future"})


class TestFieldSpecificFactories:

    def test_minimal_fields_factory_has_only_basic_fields(self):
        issue = JiraIssueMinimalFieldsFactory()

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have basic fields
        assert "summary" in fields
        assert "status" in fields

        # Should NOT have time or sprint fields
        assert "timespent" not in fields
        assert "timetracking" not in fields
        assert "Sprint" not in fields
        assert "customfield_10121" not in fields
        assert "worklog" not in fields

    def test_worklog_fields_factory_has_worklog_data(self):
        issue = JiraIssueWorklogFieldsFactory()

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have basic fields
        assert "summary" in fields
        assert "worklog" in fields

        # Worklog should have proper structure
        worklog = fields["worklog"]
        assert "total" in worklog
        assert "worklogs" in worklog
        assert isinstance(worklog["worklogs"], list)

        # Should NOT have time tracking or sprint fields
        assert "timespent" not in fields
        assert "timetracking" not in fields
        assert "Sprint" not in fields
        assert "customfield_10121" not in fields

    def test_sprint_only_factory_has_only_sprint_field(self):
        issue = JiraIssueSprintOnlyFactory()

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have sprint field
        assert "customfield_10121" in fields
        sprint_data = fields["customfield_10121"][0]
        assert "id" in sprint_data
        assert "name" in sprint_data
        assert "state" in sprint_data
        assert "startDate" in sprint_data
        assert "endDate" in sprint_data

        # Should NOT have other fields
        assert "summary" not in fields
        assert "status" not in fields
        assert "timespent" not in fields
        assert "timetracking" not in fields
        assert "worklog" not in fields

    def test_parametric_factory_with_custom_fields(self):
        # Test with only summary and status
        issue = JiraIssueParametricFactory(requested_fields=["summary", "status"])

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have requested fields
        assert "summary" in fields
        assert "status" in fields

        # Should NOT have unrequested fields
        assert "timespent" not in fields
        assert "timetracking" not in fields
        assert "customfield_10121" not in fields

    def test_parametric_factory_with_sprint_fields(self):
        # Test with sprint and worklog fields
        issue = JiraIssueParametricFactory(requested_fields=["customfield_10121", "worklog"])

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have requested fields
        assert "customfield_10121" in fields
        assert "worklog" in fields

        # Should NOT have unrequested fields
        assert "summary" not in fields
        assert "status" not in fields
        assert "timespent" not in fields

    def test_parametric_factory_default_has_all_fields(self):
        # Test default behavior (all fields)
        issue = JiraIssueParametricFactory()

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have all default fields
        assert "summary" in fields
        assert "status" in fields
        assert "timespent" in fields
        assert "timetracking" in fields
        assert "customfield_10121" in fields


class TestFactoryIntegration:

    def test_related_factories_work_together(self):
        # Create related objects that would work in a real scenario
        user = UserFactory()
        board = BoardFactory()
        sprint = ActiveSprintFactory()
        issue = InProgressIssueFactory()
        worklog = CompletedWorklogFactory(issue_key=issue.key)

        # Verify they have compatible data
        assert user.email_address.endswith("@example.com")
        assert board.project_key.startswith("PROJ")
        assert sprint.state == "active"
        assert issue.status == "In Progress"
        assert worklog.issue_key == issue.key

    def test_jira_and_domain_factories_compatibility(self):
        # Test that JIRA factories and domain factories create compatible data
        domain_issue = IssueFactory()
        jira_issue = JiraIssueFactory()

        # Both should have compatible key formats
        assert domain_issue.key.startswith("TEST-")
        assert jira_issue.raw["key"].startswith("TEST-")

        # Both should have reasonable time values
        assert isinstance(domain_issue.time_spent_seconds, int)
        assert isinstance(jira_issue.raw["fields"]["timespent"], int)

    def test_field_specific_factories_simulate_different_api_responses(self):
        # Simulate different API calls with different field requests
        minimal_issue = JiraIssueMinimalFieldsFactory()
        worklog_issue = JiraIssueWorklogFieldsFactory()
        sprint_issue = JiraIssueSprintOnlyFactory()

        # Each should have different field structures
        minimal_fields = set(minimal_issue.raw["fields"].keys())
        worklog_fields = set(worklog_issue.raw["fields"].keys())
        sprint_fields = set(sprint_issue.raw["fields"].keys())

        # Should have minimal intersection (simulating different API responses)
        assert minimal_fields != worklog_fields
        assert worklog_fields != sprint_fields
        assert minimal_fields != sprint_fields


class TestHelperFunctions:

    def test_create_jira_issue_with_fields_basic(self):
        issue = create_jira_issue_with_fields(["summary", "status"])

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have requested fields
        assert "summary" in fields
        assert "status" in fields

        # Should NOT have other fields
        assert "timespent" not in fields
        assert "timetracking" not in fields
        assert "customfield_10121" not in fields

    def test_create_jira_issue_with_fields_complex(self):
        issue = create_jira_issue_with_fields(["customfield_10121", "worklog", "timetracking"])

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have requested fields
        assert "customfield_10121" in fields
        assert "worklog" in fields
        assert "timetracking" in fields

        # Should NOT have unrequested fields
        assert "summary" not in fields
        assert "status" not in fields

    def test_create_jira_issues_for_api_scenario_search_basic(self):
        issue = create_jira_issues_for_api_scenario("search_basic")

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should match search_basic scenario
        assert "summary" in fields
        assert "status" in fields
        assert len(fields) == 2  # Only these two fields

    def test_create_jira_issues_for_api_scenario_search_with_worklog(self):
        issue = create_jira_issues_for_api_scenario("search_with_worklog")

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should match search_with_worklog scenario
        assert "summary" in fields
        assert "worklog" in fields
        assert len(fields) == 2  # Only these two fields

    def test_create_jira_issues_for_api_scenario_search_full(self):
        issue = create_jira_issues_for_api_scenario("search_full")

        assert isinstance(issue, JiraIssue)
        fields = issue.raw["fields"]

        # Should have all fields
        expected_fields = {
            "summary",
            "status",
            "timespent",
            "timetracking",
            "customfield_10121",
            "worklog",
        }
        assert set(fields.keys()) == expected_fields

    def test_create_jira_issues_for_api_scenario_invalid_scenario(self):
        with pytest.raises(ValueError) as exc_info:
            create_jira_issues_for_api_scenario("invalid_scenario")

        assert "Unknown scenario 'invalid_scenario'" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_field_constants_are_defined(self):
        # Test that our field constants are available and reasonable
        assert isinstance(DEFAULT_ISSUE_FIELDS, list)
        assert isinstance(WORKLOG_REPORT_FIELDS, list)
        assert isinstance(SPRINT_QUERY_FIELDS, list)

        # Should contain expected fields
        assert "summary" in DEFAULT_ISSUE_FIELDS
        assert "worklog" in WORKLOG_REPORT_FIELDS
        assert "customfield_10121" in SPRINT_QUERY_FIELDS

    def test_field_constants_can_be_used_with_helper(self):
        # Test that our constants work with the helper function
        issue1 = create_jira_issue_with_fields(DEFAULT_ISSUE_FIELDS)
        issue2 = create_jira_issue_with_fields(WORKLOG_REPORT_FIELDS)
        issue3 = create_jira_issue_with_fields(SPRINT_QUERY_FIELDS)

        # All should be valid JIRA issues
        assert isinstance(issue1, JiraIssue)
        assert isinstance(issue2, JiraIssue)
        assert isinstance(issue3, JiraIssue)

        # Should have different field sets
        fields1 = set(issue1.raw["fields"].keys())
        fields2 = set(issue2.raw["fields"].keys())
        fields3 = set(issue3.raw["fields"].keys())

        assert fields1 != fields2
        assert fields2 != fields3


class TestJiraConfigFactory:

    def test_field_constants(self):
        config = JiraConfigFactory()

        assert "JIRA_PROJECT_KEY" in config
        assert "JIRA_EMAIL" in config
        assert "@" in config["JIRA_EMAIL"]
        assert "JIRA_TOKEN" in config
        assert "JIRA_SERVER" in config
