"""
Result Aggregator
=================

Aggregates results from parallel sub-agent executions into a unified result.
Handles conflict detection, memory merging, and status reconciliation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .subagent import SubagentResult, SubagentStatus

logger = logging.getLogger(__name__)


@dataclass
class ParallelResults:
    """
    Aggregated results from parallel sub-agent execution.

    Combines outcomes from multiple sub-agents into a single result
    with conflict detection and metrics aggregation.
    """

    # Execution tracking
    batch_id: str
    started_at: datetime
    completed_at: datetime | None = None

    # Individual results
    results: list[SubagentResult] = field(default_factory=list)

    # Aggregated metrics
    total_subtasks: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0

    # Combined outcomes
    all_successful: bool = False
    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)

    # Git tracking
    commits_made_total: int = 0
    files_changed_all: set[str] = field(default_factory=set)

    # Memory aggregation
    total_discoveries: int = 0
    total_insights: int = 0

    # Resource usage
    total_tool_calls: int = 0
    total_tokens: int = 0
    total_duration_seconds: float = 0.0

    def add_result(self, result: SubagentResult):
        """Add a sub-agent result to the aggregation."""
        self.results.append(result)
        self.total_subtasks += 1

        # Update status counts
        if result.status == SubagentStatus.COMPLETED and result.success:
            self.completed_count += 1
        elif result.status == SubagentStatus.FAILED:
            self.failed_count += 1
        elif result.status == SubagentStatus.CANCELLED:
            self.cancelled_count += 1

        # Aggregate git changes
        self.commits_made_total += result.commits_made
        if result.files_changed:
            # Check for conflicts
            overlap = self.files_changed_all & set(result.files_changed)
            if overlap:
                self.has_conflicts = True
                self.conflict_files.extend(list(overlap))
            self.files_changed_all.update(result.files_changed)

        # Aggregate memory
        if result.discoveries:
            self.total_discoveries += len(result.discoveries.get("patterns", []))
            self.total_discoveries += len(result.discoveries.get("gotchas", []))
        self.total_insights += result.insights_extracted

        # Aggregate resources
        self.total_tool_calls += result.tool_calls_count
        self.total_tokens += result.tokens_used
        if result.duration_seconds():
            self.total_duration_seconds += result.duration_seconds()

    def finalize(self):
        """Finalize the aggregation after all results are added."""
        self.completed_at = datetime.now()
        self.all_successful = (
            self.failed_count == 0
            and self.cancelled_count == 0
            and self.completed_count == self.total_subtasks
        )

    def get_failed_subtasks(self) -> list[str]:
        """Get IDs of failed subtasks."""
        return [
            r.subtask_id
            for r in self.results
            if r.status == SubagentStatus.FAILED
        ]

    def get_successful_subtasks(self) -> list[str]:
        """Get IDs of successfully completed subtasks."""
        return [
            r.subtask_id
            for r in self.results
            if r.status == SubagentStatus.COMPLETED and r.success
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "batch_id": self.batch_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_subtasks": self.total_subtasks,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "all_successful": self.all_successful,
            "has_conflicts": self.has_conflicts,
            "conflict_files": self.conflict_files,
            "commits_made_total": self.commits_made_total,
            "files_changed_all": list(self.files_changed_all),
            "total_discoveries": self.total_discoveries,
            "total_insights": self.total_insights,
            "total_tool_calls": self.total_tool_calls,
            "total_tokens": self.total_tokens,
            "total_duration_seconds": self.total_duration_seconds,
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            f"Parallel Batch: {self.batch_id}",
            f"Status: {'SUCCESS' if self.all_successful else 'PARTIAL/FAILED'}",
            f"Subtasks: {self.completed_count}/{self.total_subtasks} completed",
        ]
        if self.failed_count > 0:
            lines.append(f"Failed: {self.failed_count}")
            failed_ids = self.get_failed_subtasks()
            lines.append(f"  - {', '.join(failed_ids[:5])}")
        if self.has_conflicts:
            lines.append(f"Conflicts detected in: {', '.join(self.conflict_files[:5])}")
        lines.append(f"Duration: {self.total_duration_seconds:.1f}s (parallel)")
        lines.append(f"Commits: {self.commits_made_total}")
        return "\n".join(lines)


def aggregate_results(
    batch_id: str,
    results: list[SubagentResult],
    started_at: datetime,
) -> ParallelResults:
    """
    Aggregate multiple sub-agent results.

    Args:
        batch_id: Unique identifier for this parallel batch
        results: List of SubagentResult instances
        started_at: When the batch started

    Returns:
        ParallelResults with all aggregations computed
    """
    aggregated = ParallelResults(
        batch_id=batch_id,
        started_at=started_at,
    )

    for result in results:
        aggregated.add_result(result)

    aggregated.finalize()
    return aggregated


def detect_file_conflicts(
    results: list[SubagentResult],
) -> tuple[bool, dict[str, list[str]]]:
    """
    Detect file modification conflicts across multiple results.

    Args:
        results: List of SubagentResult instances

    Returns:
        Tuple of (has_conflicts, conflict_map)
        conflict_map maps file paths to list of subtask IDs that modified them
    """
    file_to_subtasks: dict[str, list[str]] = {}

    for result in results:
        for file_path in result.files_changed:
            if file_path not in file_to_subtasks:
                file_to_subtasks[file_path] = []
            file_to_subtasks[file_path].append(result.subtask_id)

    # Find conflicts (files modified by multiple subtasks)
    conflict_map = {
        path: subtasks
        for path, subtasks in file_to_subtasks.items()
        if len(subtasks) > 1
    }

    return len(conflict_map) > 0, conflict_map
