"""Unified core module - all JIRA functionality in one place."""

from .models import User, Board, Sprint, Issue, Worklog, WorklogEntry
from .result import Result, safe, pipe, success, failure, compose, partial
from .operations import (
    # Connection functions
    create_jira_connection,
    
    # Issue operations
    get_current_sprint_issues,
    get_future_sprint_issues,
    get_closed_sprint_issues,
    get_sprint_issues,
    get_issues_by_sprint_state,
    search_issues_with_sprint_info,
    get_issues_by_work_logged_on_date,
    
    # Board operations
    get_board_by_key,
    
    # Sprint operations
    get_sprints_by_board,
    get_sprint_by_id,
    
    # User operations
    get_current_user,
    
    # Worklog operations
    log_work,
    get_worklog,
    get_issue_worklogs_by_user_and_date,
)

__all__ = [
    # Domain models
    "User",
    "Board", 
    "Sprint",
    "Issue",
    "Worklog",
    "WorklogEntry",
    # ROP utilities
    "Result",
    "safe", 
    "pipe",
    "success",
    "failure", 
    "compose",
    "partial",
    # JIRA operations
    "create_jira_connection",
    "get_current_sprint_issues",
    "get_future_sprint_issues", 
    "get_closed_sprint_issues",
    "get_sprint_issues",
    "get_issues_by_sprint_state",
    "search_issues_with_sprint_info",
    "get_issues_by_work_logged_on_date",
    "get_board_by_key",
    "get_sprints_by_board",
    "get_sprint_by_id",
    "get_current_user",
    "log_work",
    "get_worklog",
    "get_issue_worklogs_by_user_and_date",
]