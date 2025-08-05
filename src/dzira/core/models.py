from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class User:
    id: str
    display_name: str
    email_address: Optional[str] = None


@dataclass(frozen=True)
class Board:
    id: int
    name: str
    project_key: str


@dataclass(frozen=True)
class Sprint:
    id: int
    name: str
    state: str  # 'active', 'closed', 'future'
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass(frozen=True)
class Issue:
    key: str
    summary: str
    status: str
    sprint_info: Optional[Dict[str, Any]] = None
    time_spent_seconds: Optional[int] = None
    time_spent_display: Optional[str] = None  # Human-readable format like "2d 1h 50m"
    time_estimate_seconds: Optional[int] = None
    time_remaining_estimate: Optional[str] = None  # Human-readable remaining like "0m"
    time_original_estimate: Optional[str] = None   # Human-readable original like "3h"


@dataclass(frozen=True)
class Worklog:
    id: str
    issue_key: str
    time_spent_seconds: int
    comment: Optional[str]
    started: datetime
    author_email: str


@dataclass(frozen=True)
class WorklogEntry:
    issue_key: str
    time_spent_seconds: int
    comment: Optional[str] = None
    started: Optional[datetime] = None
