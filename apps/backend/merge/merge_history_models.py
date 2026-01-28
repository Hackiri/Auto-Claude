"""
Merge History Data Models
==========================

Data classes for tracking merge completion history.

These models capture:
- Complete merge records with timestamp, files changed, and source worktree
- Conflict resolution details for audit purposes
- Rollback information for reverting merges
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MergeConflictRecord:
    """
    Record of a single conflict that was resolved during merge.

    This provides the audit trail showing what conflicts occurred
    and how they were resolved (auto vs AI).
    """

    file_path: str
    conflict_type: str  # e.g., "content", "semantic", "structural"
    resolution_method: str  # "auto" or "ai"

    # Content details
    base_content: str = ""
    task_content: str = ""
    main_content: str = ""
    resolved_content: str = ""

    # AI resolution details (if applicable)
    ai_reasoning: str | None = None
    ai_tokens_used: int = 0

    # Metadata
    resolved_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "conflict_type": self.conflict_type,
            "resolution_method": self.resolution_method,
            "base_content": self.base_content,
            "task_content": self.task_content,
            "main_content": self.main_content,
            "resolved_content": self.resolved_content,
            "ai_reasoning": self.ai_reasoning,
            "ai_tokens_used": self.ai_tokens_used,
            "resolved_at": self.resolved_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeConflictRecord:
        """Create from dictionary."""
        return cls(
            file_path=data["file_path"],
            conflict_type=data["conflict_type"],
            resolution_method=data["resolution_method"],
            base_content=data.get("base_content", ""),
            task_content=data.get("task_content", ""),
            main_content=data.get("main_content", ""),
            resolved_content=data.get("resolved_content", ""),
            ai_reasoning=data.get("ai_reasoning"),
            ai_tokens_used=data.get("ai_tokens_used", 0),
            resolved_at=datetime.fromisoformat(data["resolved_at"]),
        )


@dataclass
class MergeHistoryEntry:
    """
    Complete record of a single merge operation.

    This is the primary audit trail showing what was merged, when,
    from which worktree, and how conflicts were resolved.
    """

    # Identification
    merge_id: str  # Unique ID for this merge (e.g., timestamp-based)
    task_id: str
    spec_name: str

    # Timing
    started_at: datetime
    completed_at: datetime | None = None

    # Source information
    source_worktree: str = ""
    source_branch: str = ""
    target_branch: str = "main"

    # Files affected
    files_changed: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)

    # Conflict tracking
    conflicts_resolved: list[MergeConflictRecord] = field(default_factory=list)
    total_conflicts: int = 0
    auto_resolved_count: int = 0
    ai_resolved_count: int = 0

    # Git information for rollback
    pre_merge_commit: str = ""  # Commit hash before merge
    merge_commit: str = ""  # Commit hash after merge

    # Outcome
    success: bool = True
    error_message: str | None = None

    # Metadata
    ai_tokens_used: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "merge_id": self.merge_id,
            "task_id": self.task_id,
            "spec_name": self.spec_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "source_worktree": self.source_worktree,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "files_changed": self.files_changed,
            "files_added": self.files_added,
            "files_deleted": self.files_deleted,
            "conflicts_resolved": [c.to_dict() for c in self.conflicts_resolved],
            "total_conflicts": self.total_conflicts,
            "auto_resolved_count": self.auto_resolved_count,
            "ai_resolved_count": self.ai_resolved_count,
            "pre_merge_commit": self.pre_merge_commit,
            "merge_commit": self.merge_commit,
            "success": self.success,
            "error_message": self.error_message,
            "ai_tokens_used": self.ai_tokens_used,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeHistoryEntry:
        """Create from dictionary."""
        return cls(
            merge_id=data["merge_id"],
            task_id=data["task_id"],
            spec_name=data["spec_name"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            source_worktree=data.get("source_worktree", ""),
            source_branch=data.get("source_branch", ""),
            target_branch=data.get("target_branch", "main"),
            files_changed=data.get("files_changed", []),
            files_added=data.get("files_added", []),
            files_deleted=data.get("files_deleted", []),
            conflicts_resolved=[
                MergeConflictRecord.from_dict(c)
                for c in data.get("conflicts_resolved", [])
            ],
            total_conflicts=data.get("total_conflicts", 0),
            auto_resolved_count=data.get("auto_resolved_count", 0),
            ai_resolved_count=data.get("ai_resolved_count", 0),
            pre_merge_commit=data.get("pre_merge_commit", ""),
            merge_commit=data.get("merge_commit", ""),
            success=data.get("success", True),
            error_message=data.get("error_message"),
            ai_tokens_used=data.get("ai_tokens_used", 0),
            duration_seconds=data.get("duration_seconds", 0.0),
        )
