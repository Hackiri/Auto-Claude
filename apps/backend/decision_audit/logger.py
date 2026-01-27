"""
Decision Audit Logger
=====================

Logger for recording key decisions made by AI agents during builds.
Records reasoning, alternatives considered, and context that influenced decisions.

Features:
- JSON-structured decision logs
- Streaming markers for real-time UI updates
- Filtering by decision type, phase, subtask
- Decision annotation support for pattern learning
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    ConfidenceLevel,
    DecisionContext,
    DecisionEntry,
    DecisionType,
)
from .storage import DecisionStorage

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Streaming markers
# =============================================================================


def emit_decision_marker(marker_type: str, data: dict, enabled: bool = True) -> None:
    """
    Emit a streaming marker to stdout for UI consumption.

    Args:
        marker_type: Type of marker (e.g., "DECISION_LOGGED", "DECISION_ANNOTATED")
        data: Data to include in the marker
        enabled: Whether marker emission is enabled
    """
    if not enabled:
        return
    try:
        marker = f"__DECISION_LOG_{marker_type.upper()}__:{json.dumps(data)}"
        print(marker, flush=True)
    except Exception:
        pass  # Don't let marker emission break logging


# =============================================================================
# Decision Audit Logger
# =============================================================================


class DecisionAuditLogger:
    """
    Logger for recording agent decisions during builds.

    Records key decisions with reasoning, alternatives considered,
    and context that influenced the decision. Supports real-time
    streaming to UI and decision annotation for pattern learning.

    Usage:
        logger = DecisionAuditLogger(spec_dir)
        logger.log_approach_chosen(
            description="Using React hooks for state management",
            reasoning="Follows existing patterns in the codebase",
            alternatives=["Redux", "MobX", "Context API"],
            subtask_id="subtask-1-1",
            phase="coding",
        )

        # Later, user can annotate decisions
        logger.annotate_decision(decision_id, "good_pattern", "This worked well")
    """

    _instance: DecisionAuditLogger | None = None

    def __init__(
        self,
        spec_dir: Path,
        emit_markers: bool = True,
        enabled: bool = True,
    ):
        """
        Initialize the decision audit logger.

        Args:
            spec_dir: Path to the spec directory
            emit_markers: Whether to emit streaming markers to stdout
            enabled: Whether decision logging is enabled
        """
        self.spec_dir = Path(spec_dir)
        self.emit_markers = emit_markers
        self.enabled = enabled
        self.current_phase: str | None = None
        self.current_subtask: str | None = None
        self.current_session: int | None = None

        if enabled:
            self.storage = DecisionStorage(spec_dir)
        else:
            self.storage = None

    @classmethod
    def get_instance(
        cls,
        spec_dir: Path | None = None,
        **kwargs,
    ) -> DecisionAuditLogger:
        """Get or create singleton instance."""
        if cls._instance is None:
            if spec_dir is None:
                raise ValueError("spec_dir required for first initialization")
            cls._instance = cls(spec_dir=spec_dir, **kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def _timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _generate_id(self) -> str:
        """Generate a unique decision ID."""
        return f"dec-{uuid.uuid4().hex[:12]}"

    def _emit(self, marker_type: str, data: dict) -> None:
        """Emit a streaming marker."""
        emit_decision_marker(marker_type, data, self.emit_markers)

    def set_phase(self, phase: str) -> None:
        """Set the current phase."""
        self.current_phase = phase

    def set_subtask(self, subtask_id: str | None) -> None:
        """Set the current subtask being processed."""
        self.current_subtask = subtask_id

    def set_session(self, session: int) -> None:
        """Set the current session number."""
        self.current_session = session

    def _build_context_list(
        self, context: DecisionContext | dict | list | None
    ) -> list[DecisionContext]:
        """
        Build a list of DecisionContext objects from various input formats.

        Args:
            context: Context in various formats (single context, dict, or list)

        Returns:
            List of DecisionContext objects
        """
        if context is None:
            return []

        if isinstance(context, list):
            result = []
            for ctx in context:
                if isinstance(ctx, DecisionContext):
                    result.append(ctx)
                elif isinstance(ctx, dict):
                    result.append(DecisionContext.from_dict(ctx))
            return result

        if isinstance(context, DecisionContext):
            return [context]

        if isinstance(context, dict):
            # Handle dict format - convert to DecisionContext
            # Support both old format (source/content) and new format (metadata fields)
            if "source" in context and "content" in context:
                return [DecisionContext.from_dict(context)]
            else:
                # Convert arbitrary dict to a single context entry
                ctx = DecisionContext(
                    source="metadata",
                    content=json.dumps(context),
                    metadata=context,
                )
                return [ctx]

        return []

    def log_decision(
        self,
        decision_type: DecisionType | str,
        description: str,
        reasoning: str,
        alternatives: list[str] | None = None,
        context: DecisionContext | dict | list | None = None,
        confidence: ConfidenceLevel | str = ConfidenceLevel.MEDIUM,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """
        Log a decision.

        Args:
            decision_type: Type of decision
            description: What was decided
            reasoning: Why this decision was made
            alternatives: What alternatives were considered
            context: Context that influenced the decision
            confidence: Confidence level of the decision
            subtask_id: Override current subtask
            phase: Override current phase

        Returns:
            The created DecisionEntry
        """
        type_value = (
            decision_type.value
            if isinstance(decision_type, DecisionType)
            else decision_type
        )
        confidence_value = (
            confidence.value if isinstance(confidence, ConfidenceLevel) else confidence
        )
        context_list = self._build_context_list(context)

        entry = DecisionEntry(
            id=self._generate_id(),
            timestamp=self._timestamp(),
            decision_type=type_value,
            description=description,
            reasoning=reasoning,
            alternatives_considered=alternatives or [],
            context_used=context_list,
            subtask_id=subtask_id or self.current_subtask,
            phase=phase or self.current_phase,
            confidence_level=confidence_value,
        )

        if self.enabled and self.storage:
            self.storage.add_entry(entry)

        # Emit streaming marker for real-time UI
        self._emit(
            "DECISION_LOGGED",
            {
                "id": entry.id,
                "type": entry.decision_type,
                "description": entry.description,
                "phase": entry.phase,
                "subtask_id": entry.subtask_id,
                "timestamp": entry.timestamp,
            },
        )

        logger.debug(f"Decision logged: {entry.decision_type} - {entry.description}")
        return entry

    def log_approach_chosen(
        self,
        description: str,
        reasoning: str,
        alternatives: list[str] | None = None,
        context: DecisionContext | dict | list | None = None,
        confidence: ConfidenceLevel | str = ConfidenceLevel.MEDIUM,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log an approach that was chosen."""
        return self.log_decision(
            decision_type=DecisionType.APPROACH_CHOSEN,
            description=description,
            reasoning=reasoning,
            alternatives=alternatives,
            context=context,
            confidence=confidence,
            subtask_id=subtask_id,
            phase=phase,
        )

    def log_alternative_rejected(
        self,
        description: str,
        reasoning: str,
        alternatives: list[str] | None = None,
        context: DecisionContext | dict | list | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log why an alternative was rejected."""
        return self.log_decision(
            decision_type=DecisionType.ALTERNATIVE_REJECTED,
            description=description,
            reasoning=reasoning,
            alternatives=alternatives,
            context=context,
            subtask_id=subtask_id,
            phase=phase,
        )

    def log_context_used(
        self,
        description: str,
        reasoning: str,
        context: DecisionContext | dict | list | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log context that influenced a decision."""
        return self.log_decision(
            decision_type=DecisionType.CONTEXT_USED,
            description=description,
            reasoning=reasoning,
            context=context,
            subtask_id=subtask_id,
            phase=phase,
        )

    def log_pattern_followed(
        self,
        description: str,
        reasoning: str,
        pattern_source: str | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log that a codebase pattern was followed."""
        context = None
        if pattern_source:
            context = DecisionContext(
                source="pattern_file",
                content=pattern_source,
                metadata={"pattern_file": pattern_source},
            )
        return self.log_decision(
            decision_type=DecisionType.PATTERN_FOLLOWED,
            description=description,
            reasoning=reasoning,
            context=context,
            subtask_id=subtask_id,
            phase=phase,
        )

    def log_file_selected(
        self,
        description: str,
        reasoning: str,
        file_path: str,
        alternatives: list[str] | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log why a specific file was selected for modification."""
        context = DecisionContext(
            source="file_read",
            content=file_path,
            metadata={"file_path": file_path},
        )
        return self.log_decision(
            decision_type=DecisionType.FILE_SELECTED,
            description=description,
            reasoning=reasoning,
            alternatives=alternatives,
            context=context,
            subtask_id=subtask_id,
            phase=phase,
        )

    def log_tool_selected(
        self,
        description: str,
        reasoning: str,
        tool_name: str,
        alternatives: list[str] | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log why a specific tool was selected."""
        context = DecisionContext(
            source="tool_selection",
            content=tool_name,
            metadata={"tool": tool_name},
        )
        return self.log_decision(
            decision_type=DecisionType.TOOL_SELECTED,
            description=description,
            reasoning=reasoning,
            alternatives=alternatives,
            context=context,
            subtask_id=subtask_id,
            phase=phase,
        )

    def log_error_recovery(
        self,
        description: str,
        reasoning: str,
        error: str,
        recovery_action: str,
        subtask_id: str | None = None,
        phase: str | None = None,
    ) -> DecisionEntry:
        """Log a decision made during error recovery."""
        context = DecisionContext(
            source="error_recovery",
            content=f"Error: {error}",
            metadata={"error": error, "recovery_action": recovery_action},
        )
        return self.log_decision(
            decision_type=DecisionType.ERROR_RECOVERY,
            description=description,
            reasoning=reasoning,
            context=context,
            confidence=ConfidenceLevel.MEDIUM,
            subtask_id=subtask_id,
            phase=phase,
        )

    def annotate_decision(
        self,
        decision_id: str,
        annotation: str,
        note: str | None = None,
    ) -> bool:
        """
        Annotate a decision as good/bad pattern for learning.

        Args:
            decision_id: The decision ID to annotate
            annotation: "good_pattern", "bad_pattern", or "neutral"
            note: Optional note about the annotation

        Returns:
            True if decision was found and annotated
        """
        if not self.enabled or not self.storage:
            return False

        result = self.storage.annotate(decision_id, annotation, note)

        if result:
            self._emit(
                "DECISION_ANNOTATED",
                {
                    "id": decision_id,
                    "annotation": annotation,
                    "note": note,
                    "timestamp": self._timestamp(),
                },
            )

        return result

    def get_decisions(
        self,
        decision_type: DecisionType | str | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
        annotation: str | None = None,
        limit: int | None = None,
    ) -> list[DecisionEntry]:
        """
        Get decisions with optional filtering.

        Args:
            decision_type: Filter by decision type
            subtask_id: Filter by subtask ID
            phase: Filter by phase
            annotation: Filter by annotation
            limit: Maximum results

        Returns:
            List of DecisionEntry objects
        """
        if not self.enabled or not self.storage:
            return []

        type_value = (
            decision_type.value
            if isinstance(decision_type, DecisionType)
            else decision_type
        )

        return self.storage.query(
            decision_type=type_value,
            subtask_id=subtask_id,
            phase=phase,
            annotation=annotation,
            limit=limit,
        )

    def get_decision_summary(self) -> dict[str, Any]:
        """
        Get a summary of all decisions.

        Returns:
            Dictionary with counts by type, phase, and annotation
        """
        if not self.enabled or not self.storage:
            return {
                "total_decisions": 0,
                "by_type": {},
                "by_phase": {},
                "by_annotation": {},
            }

        return self.storage.get_summary()


# =============================================================================
# Convenience functions
# =============================================================================


def get_decision_logger(spec_dir: Path | None = None) -> DecisionAuditLogger:
    """
    Get the decision logger instance.

    Args:
        spec_dir: Path to spec directory (required for first call)

    Returns:
        DecisionAuditLogger instance
    """
    return DecisionAuditLogger.get_instance(spec_dir=spec_dir)
