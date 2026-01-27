"""
Decision Audit Package
======================

Audit trail for agent decisions during builds.
Records key decisions, reasoning, alternatives considered, and context.

Key features:
- Decision type classification (approach chosen, alternatives rejected, etc.)
- JSON file persistence per spec
- Query capabilities with filtering
- Streaming markers for real-time UI updates
- Automatic decision extraction from agent responses

Usage:
    from decision_audit import DecisionAuditLogger, DecisionType, get_decision_logger

    logger = get_decision_logger(spec_dir)
    logger.log_approach_chosen(
        description="Using existing auth patterns",
        reasoning="Matches current codebase conventions",
        alternatives=["Custom implementation", "Third-party library"],
    )

    # Automatic extraction from agent responses
    from decision_audit import extract_decisions_from_response

    decisions = await extract_decisions_from_response(
        response_text=agent_response,
        subtask_id="subtask-1-1",
        phase="coding",
    )
"""

# Export extractor utilities
from .extractor import (
    extract_decisions_from_response,
    extract_decisions_sync,
    is_decision_extraction_enabled,
)

# Export main logger
from .logger import (
    DecisionAuditLogger,
    emit_decision_marker,
    get_decision_logger,
)

# Export models
from .models import (
    ConfidenceLevel,
    DecisionContext,
    DecisionEntry,
    DecisionFilter,
    DecisionType,
)

# Export storage utilities
from .storage import (
    DecisionStorage,
    get_decision_count,
    load_decisions,
)

__all__ = [
    # Main logger
    "DecisionAuditLogger",
    "get_decision_logger",
    "emit_decision_marker",
    # Models
    "DecisionType",
    "DecisionEntry",
    "DecisionContext",
    "DecisionFilter",
    "ConfidenceLevel",
    # Storage utilities
    "DecisionStorage",
    "load_decisions",
    "get_decision_count",
    # Extractor
    "extract_decisions_from_response",
    "extract_decisions_sync",
    "is_decision_extraction_enabled",
]
