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

Usage:
    from decision_audit import DecisionAuditLogger, DecisionType, get_decision_logger

    logger = get_decision_logger(spec_dir)
    logger.log_approach_chosen(
        description="Using existing auth patterns",
        reasoning="Matches current codebase conventions",
        alternatives=["Custom implementation", "Third-party library"],
    )
"""

from .logger import (
    DecisionAuditLogger,
    emit_decision_marker,
    get_decision_logger,
)
from .models import (
    ConfidenceLevel,
    DecisionContext,
    DecisionEntry,
    DecisionFilter,
    DecisionType,
)
from .storage import (
    DecisionStorage,
    get_decision_count,
    load_decisions,
)

__all__ = [
    # Logger
    "DecisionAuditLogger",
    "get_decision_logger",
    "emit_decision_marker",
    # Models
    "DecisionType",
    "DecisionEntry",
    "DecisionContext",
    "DecisionFilter",
    "ConfidenceLevel",
    # Storage
    "DecisionStorage",
    "load_decisions",
    "get_decision_count",
]
