"""Tests for domain models."""

from datetime import datetime

from dzira.core.models import User, Board, Sprint, Issue, Worklog, WorklogEntry


class TestUser:
    def test_should_create_user_with_required_fields(self):
        user = User(id="user123", display_name="John Doe")
        
        assert user.id == "user123"
        assert user.display_name == "John Doe"
        assert user.email_address is None
    
    def test_should_create_user_with_optional_email(self):
        user = User(id="user123", display_name="John Doe", email_address="john@example.com")
        
        assert user.email_address == "john@example.com"
    
    def test_should_be_immutable(self):
        user = User(id="user123", display_name="John Doe")
        
        # Should not be able to modify frozen dataclass
        try:
            user.id = "new_id"
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected


class TestBoard:
    def test_should_create_board_with_required_fields(self):
        board = Board(id=42, name="Test Board", project_key="TEST")
        
        assert board.id == 42
        assert board.name == "Test Board"
        assert board.project_key == "TEST"
    
    def test_should_be_immutable(self):
        board = Board(id=42, name="Test Board", project_key="TEST")
        
        try:
            board.name = "New Name"
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected


class TestSprint:
    def test_should_create_sprint_with_required_fields(self):
        sprint = Sprint(id=123, name="Sprint 1", state="active")
        
        assert sprint.id == 123
        assert sprint.name == "Sprint 1"
        assert sprint.state == "active"
    
    def test_should_be_immutable(self):
        sprint = Sprint(id=123, name="Sprint 1", state="active")
        
        try:
            sprint.state = "closed"
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected


class TestIssue:
    def test_should_create_issue_with_required_fields(self):
        issue = Issue(key="TEST-123", summary="Test issue", status="To Do")
        
        assert issue.key == "TEST-123"
        assert issue.summary == "Test issue"
        assert issue.status == "To Do"
        assert issue.sprint_id is None
        assert issue.time_spent_seconds is None
        assert issue.time_estimate_seconds is None
    
    def test_should_create_issue_with_optional_fields(self):
        issue = Issue(
            key="TEST-123",
            summary="Test issue",
            status="In Progress",
            sprint_id=42,
            time_spent_seconds=3600,
            time_estimate_seconds=7200
        )
        
        assert issue.sprint_id == 42
        assert issue.time_spent_seconds == 3600
        assert issue.time_estimate_seconds == 7200
    
    def test_should_be_immutable(self):
        issue = Issue(key="TEST-123", summary="Test issue", status="To Do")
        
        try:
            issue.status = "Done"
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected


class TestWorklog:
    def test_should_create_worklog_with_required_fields(self):
        started = datetime(2024, 1, 15, 10, 30)
        worklog = Worklog(
            id="12345",
            issue_key="TEST-123",
            time_spent_seconds=3600,
            comment="Work done",
            started=started,
            author_email="user@example.com"
        )
        
        assert worklog.id == "12345"
        assert worklog.issue_key == "TEST-123"
        assert worklog.time_spent_seconds == 3600
        assert worklog.comment == "Work done"
        assert worklog.started == started
        assert worklog.author_email == "user@example.com"
    
    def test_should_allow_none_comment(self):
        started = datetime(2024, 1, 15, 10, 30)
        worklog = Worklog(
            id="12345",
            issue_key="TEST-123",
            time_spent_seconds=3600,
            comment=None,
            started=started,
            author_email="user@example.com"
        )
        
        assert worklog.comment is None
    
    def test_should_be_immutable(self):
        started = datetime(2024, 1, 15, 10, 30)
        worklog = Worklog(
            id="12345",
            issue_key="TEST-123",
            time_spent_seconds=3600,
            comment="Work done",
            started=started,
            author_email="user@example.com"
        )
        
        try:
            worklog.comment = "New comment"
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected


class TestWorklogEntry:
    def test_should_create_worklog_entry_with_required_fields(self):
        entry = WorklogEntry(issue_key="TEST-123", time_spent_seconds=3600)
        
        assert entry.issue_key == "TEST-123"
        assert entry.time_spent_seconds == 3600
        assert entry.comment is None
        assert entry.started is None
    
    def test_should_create_worklog_entry_with_optional_fields(self):
        started = datetime(2024, 1, 15, 10, 30)
        entry = WorklogEntry(
            issue_key="TEST-123",
            time_spent_seconds=3600,
            comment="Work description",
            started=started
        )
        
        assert entry.comment == "Work description"
        assert entry.started == started
    
    def test_should_be_immutable(self):
        entry = WorklogEntry(issue_key="TEST-123", time_spent_seconds=3600)
        
        try:
            entry.time_spent_seconds = 7200
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass  # Expected