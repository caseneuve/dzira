"""Domain models independent of external API implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class User:
    """Represents a user in the system."""
    id: str
    display_name: str
    email_address: Optional[str] = None


@dataclass(frozen=True)
class Board:
    """Represents a project board."""
    id: int
    name: str
    project_key: str


@dataclass(frozen=True)
class Sprint:
    """Represents a sprint."""
    id: int
    name: str
    state: str  # 'active', 'closed', 'future'
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass(frozen=True)
class Issue:
    """Represents an issue/ticket."""
    key: str
    summary: str
    status: str
    sprint_id: Optional[int] = None
    time_spent_seconds: Optional[int] = None
    time_spent_display: Optional[str] = None  # Human-readable format like "2d 1h 50m"
    time_estimate_seconds: Optional[int] = None
    time_remaining_estimate: Optional[str] = None  # Human-readable remaining like "0m"
    time_original_estimate: Optional[str] = None   # Human-readable original like "3h"


@dataclass(frozen=True)
class Worklog:
    """Represents a work log entry."""
    id: str
    issue_key: str
    time_spent_seconds: int
    comment: Optional[str]
    started: datetime
    author_email: str


@dataclass(frozen=True)
class WorklogEntry:
    """Represents a worklog creation/update request."""
    issue_key: str
    time_spent_seconds: int
    comment: Optional[str] = None
    started: Optional[datetime] = None