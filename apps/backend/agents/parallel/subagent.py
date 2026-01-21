"""
Subagent Configuration and Results
==================================

Defines the configuration and result structures for parallel sub-agents.
Each sub-agent is a specialized worker that handles a specific subtask.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class SubagentStatus(Enum):
    """Status of a sub-agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentConfig:
    """
    Configuration for a single sub-agent.

    Each sub-agent handles one subtask from the implementation plan.
    The configuration defines the subtask scope, allowed files,
    and MCP servers the sub-agent can use.
    """

    # Identity
    subtask_id: str
    subtask_description: str

    # Scope restrictions
    files_to_modify: list[str] = field(default_factory=list)
    files_to_create: list[str] = field(default_factory=list)
    patterns_from: list[str] = field(default_factory=list)

    # Service scoping
    service: str | None = None
    all_services: bool = False

    # MCP servers this sub-agent needs
    mcp_servers: list[str] = field(default_factory=list)

    # Custom tools enabled for this sub-agent
    custom_tools: list[str] = field(default_factory=list)

    # Extended thinking settings
    max_thinking_tokens: int | None = None

    # Timeout in seconds (default: 10 minutes)
    timeout_seconds: int = 600

    # Phase context
    phase_name: str | None = None
    phase_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "subtask_id": self.subtask_id,
            "subtask_description": self.subtask_description,
            "files_to_modify": self.files_to_modify,
            "files_to_create": self.files_to_create,
            "patterns_from": self.patterns_from,
            "service": self.service,
            "all_services": self.all_services,
            "mcp_servers": self.mcp_servers,
            "custom_tools": self.custom_tools,
            "max_thinking_tokens": self.max_thinking_tokens,
            "timeout_seconds": self.timeout_seconds,
            "phase_name": self.phase_name,
            "phase_number": self.phase_number,
        }

    @classmethod
    def from_subtask(cls, subtask: dict, phase: dict | None = None) -> "SubagentConfig":
        """
        Create SubagentConfig from a subtask dictionary.

        Args:
            subtask: Subtask from implementation plan
            phase: Optional phase containing the subtask

        Returns:
            SubagentConfig instance
        """
        return cls(
            subtask_id=subtask.get("id", "unknown"),
            subtask_description=subtask.get("description", ""),
            files_to_modify=subtask.get("files_to_modify", []),
            files_to_create=subtask.get("files_to_create", []),
            patterns_from=subtask.get("patterns_from", []),
            service=subtask.get("service"),
            all_services=subtask.get("all_services", False),
            phase_name=phase.get("name") if phase else None,
            phase_number=phase.get("phase") if phase else None,
        )


@dataclass
class SubagentResult:
    """
    Result of a sub-agent execution.

    Captures the outcome, timing, and any artifacts produced.
    """

    # Identity
    subtask_id: str
    config: SubagentConfig

    # Execution status
    status: SubagentStatus = SubagentStatus.PENDING

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Outcomes
    success: bool = False
    error_message: str | None = None
    response_text: str | None = None

    # Git tracking
    commit_before: str | None = None
    commit_after: str | None = None
    commits_made: int = 0

    # Files modified
    files_changed: list[str] = field(default_factory=list)

    # Memory artifacts
    discoveries: dict | None = None
    insights_extracted: int = 0

    # Metrics
    tool_calls_count: int = 0
    tokens_used: int = 0

    def duration_seconds(self) -> float | None:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "subtask_id": self.subtask_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "error_message": self.error_message,
            "response_text": self.response_text[:1000] if self.response_text else None,
            "commit_before": self.commit_before,
            "commit_after": self.commit_after,
            "commits_made": self.commits_made,
            "files_changed": self.files_changed,
            "discoveries": self.discoveries,
            "insights_extracted": self.insights_extracted,
            "tool_calls_count": self.tool_calls_count,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds(),
        }

    def mark_running(self):
        """Mark the sub-agent as running."""
        self.status = SubagentStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self, success: bool, response: str | None = None):
        """Mark the sub-agent as completed."""
        self.status = SubagentStatus.COMPLETED if success else SubagentStatus.FAILED
        self.completed_at = datetime.now()
        self.success = success
        self.response_text = response

    def mark_failed(self, error: str):
        """Mark the sub-agent as failed."""
        self.status = SubagentStatus.FAILED
        self.completed_at = datetime.now()
        self.success = False
        self.error_message = error

    def mark_cancelled(self):
        """Mark the sub-agent as cancelled."""
        self.status = SubagentStatus.CANCELLED
        self.completed_at = datetime.now()
        self.success = False
