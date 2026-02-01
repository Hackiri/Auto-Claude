"""
Data models for decision audit trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    """Types of decisions that agents make during execution."""

    APPROACH_CHOSEN = "approach_chosen"
    ALTERNATIVE_REJECTED = "alternative_rejected"
    CONTEXT_USED = "context_used"
    PATTERN_FOLLOWED = "pattern_followed"
    FILE_SELECTED = "file_selected"
    TOOL_SELECTED = "tool_selected"
    ERROR_RECOVERY = "error_recovery"


class ConfidenceLevel(str, Enum):
    """Confidence level for decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DecisionContext:
    """Context that influenced a decision."""

    source: str  # e.g., "graphiti_query", "file_read", "user_instruction"
    content: str  # The actual context content
    timestamp: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "source": self.source,
            "content": self.content,
            "metadata": self.metadata,
        }
        if self.timestamp:
            result["timestamp"] = self.timestamp
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionContext:
        """Create from dictionary."""
        return cls(
            source=data.get("source", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DecisionEntry:
    """A single decision entry in the audit trail."""

    id: str  # Unique identifier for the decision
    timestamp: str
    decision_type: str  # DecisionType value
    description: str
    reasoning: str
    alternatives_considered: list[str] = field(default_factory=list)
    context_used: list[DecisionContext] = field(default_factory=list)
    subtask_id: str | None = None
    phase: str | None = None
    confidence_level: str = ConfidenceLevel.MEDIUM.value
    # User annotation fields
    annotation: str | None = None  # "good_pattern" | "bad_pattern" | None
    annotation_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "decision_type": self.decision_type,
            "description": self.description,
            "reasoning": self.reasoning,
            "alternatives_considered": self.alternatives_considered,
            "context_used": [ctx.to_dict() for ctx in self.context_used],
            "subtask_id": self.subtask_id,
            "phase": self.phase,
            "confidence_level": self.confidence_level,
            "annotation": self.annotation,
            "annotation_note": self.annotation_note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionEntry:
        """Create from dictionary."""
        context_used = [
            DecisionContext.from_dict(ctx)
            for ctx in data.get("context_used", [])
        ]
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            decision_type=data.get("decision_type", DecisionType.APPROACH_CHOSEN.value),
            description=data.get("description", ""),
            reasoning=data.get("reasoning", ""),
            alternatives_considered=data.get("alternatives_considered", []),
            context_used=context_used,
            subtask_id=data.get("subtask_id"),
            phase=data.get("phase"),
            confidence_level=data.get("confidence_level", ConfidenceLevel.MEDIUM.value),
            annotation=data.get("annotation"),
            annotation_note=data.get("annotation_note"),
        )


@dataclass
class DecisionFilter:
    """Filter criteria for querying decisions."""

    decision_type: str | None = None
    subtask_id: str | None = None
    phase: str | None = None
    annotation: str | None = None
    since: datetime | None = None
    until: datetime | None = None
