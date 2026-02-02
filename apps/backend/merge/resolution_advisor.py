"""
Resolution Advisor
==================

Analyzes predicted conflicts and suggests resolution strategies.

This module is purely rule-based (no AI calls). For each conflict,
it produces a ConflictAdvice with:
- strategy: recommended MergeStrategy
- rationale: why this strategy was chosen
- complexity_score: 0.0-1.0 estimate of resolution difficulty
- recommended_action: human-readable next step

Decision logic:
- Additive-only conflicts → auto-merge with appropriate strategy
- Same-location modifications → severity-based escalation
- Critical conflicts → human review
- Everything else → rebase or defer based on complexity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .types import (
    ChangeType,
    ConflictRegion,
    ConflictSeverity,
    MergeStrategy,
)

try:
    from debug import debug, debug_success
except ImportError:

    def debug(*args, **kwargs):
        pass

    def debug_success(*args, **kwargs):
        pass


logger = logging.getLogger(__name__)
MODULE = "merge.resolution_advisor"


@dataclass
class ConflictAdvice:
    """
    Resolution advice for a single conflict.

    Attributes:
        conflict: The original conflict region
        strategy: Recommended merge strategy
        rationale: Why this strategy was chosen
        complexity_score: 0.0 (trivial) to 1.0 (very complex)
        recommended_action: Human-readable next step
    """

    conflict: ConflictRegion
    strategy: MergeStrategy
    rationale: str
    complexity_score: float
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "conflict": self.conflict.to_dict(),
            "strategy": self.strategy.value,
            "rationale": self.rationale,
            "complexity_score": self.complexity_score,
            "recommended_action": self.recommended_action,
        }


# Severity to base complexity mapping
_SEVERITY_COMPLEXITY: dict[ConflictSeverity, float] = {
    ConflictSeverity.NONE: 0.0,
    ConflictSeverity.LOW: 0.2,
    ConflictSeverity.MEDIUM: 0.5,
    ConflictSeverity.HIGH: 0.7,
    ConflictSeverity.CRITICAL: 0.9,
}

# Change types considered additive (safe to combine)
_ADDITIVE_TYPES: set[ChangeType] = {
    ChangeType.ADD_IMPORT,
    ChangeType.ADD_FUNCTION,
    ChangeType.ADD_HOOK_CALL,
    ChangeType.ADD_VARIABLE,
    ChangeType.ADD_CONSTANT,
    ChangeType.ADD_CLASS,
    ChangeType.ADD_METHOD,
    ChangeType.ADD_PROPERTY,
    ChangeType.ADD_TYPE,
    ChangeType.ADD_INTERFACE,
    ChangeType.ADD_DECORATOR,
    ChangeType.ADD_JSX_ELEMENT,
    ChangeType.ADD_COMMENT,
}

# Strategies for additive change types
_ADDITIVE_STRATEGY: dict[ChangeType, MergeStrategy] = {
    ChangeType.ADD_IMPORT: MergeStrategy.COMBINE_IMPORTS,
    ChangeType.ADD_FUNCTION: MergeStrategy.APPEND_FUNCTIONS,
    ChangeType.ADD_METHOD: MergeStrategy.APPEND_METHODS,
    ChangeType.ADD_HOOK_CALL: MergeStrategy.HOOKS_FIRST,
    ChangeType.ADD_JSX_ELEMENT: MergeStrategy.COMBINE_PROPS,
}


class ResolutionAdvisor:
    """
    Analyzes predicted conflicts and suggests resolution strategies.

    Uses rule-based logic to determine the best approach for each
    conflict, considering severity, change types, and task count.

    Example:
        advisor = ResolutionAdvisor()
        advices = advisor.advise(conflicts)
        for advice in advices:
            print(f"{advice.strategy.value}: {advice.recommended_action}")
    """

    def __init__(self):
        """Initialize the resolution advisor."""
        debug(MODULE, "Initializing ResolutionAdvisor")
        debug_success(MODULE, "ResolutionAdvisor initialized")

    def advise(self, conflicts: list[ConflictRegion]) -> list[ConflictAdvice]:
        """
        Produce resolution advice for a list of conflicts.

        Args:
            conflicts: List of detected conflict regions

        Returns:
            List of ConflictAdvice, one per conflict
        """
        advices = [self._advise_single(conflict) for conflict in conflicts]

        auto_count = sum(
            1 for a in advices if a.strategy not in {
                MergeStrategy.AI_REQUIRED,
                MergeStrategy.HUMAN_REQUIRED,
            }
        )
        debug_success(
            MODULE,
            "Resolution advice complete",
            total=len(advices),
            auto_resolvable=auto_count,
        )

        return advices

    def _advise_single(self, conflict: ConflictRegion) -> ConflictAdvice:
        """
        Produce advice for a single conflict.

        Decision order:
        1. If conflict already has an auto-merge strategy, use it
        2. If all change types are additive, pick an additive strategy
        3. If severity is CRITICAL, recommend human review
        4. If severity is HIGH, recommend AI resolution
        5. Otherwise, recommend rebase or order-by-time
        """
        # 1. Conflict already resolved by detector
        if conflict.can_auto_merge and conflict.merge_strategy:
            return ConflictAdvice(
                conflict=conflict,
                strategy=conflict.merge_strategy,
                rationale="Conflict detector determined auto-merge is safe.",
                complexity_score=_SEVERITY_COMPLEXITY.get(
                    conflict.severity, 0.2
                ),
                recommended_action=(
                    f"Auto-merge using {conflict.merge_strategy.value} strategy."
                ),
            )

        # 2. All additive changes
        if all(ct in _ADDITIVE_TYPES for ct in conflict.change_types):
            strategy = self._pick_additive_strategy(conflict.change_types)
            return ConflictAdvice(
                conflict=conflict,
                strategy=strategy,
                rationale="All changes are additive and can be safely combined.",
                complexity_score=max(0.1, _SEVERITY_COMPLEXITY.get(
                    conflict.severity, 0.2
                ) - 0.1),
                recommended_action=(
                    f"Combine additive changes using {strategy.value} strategy."
                ),
            )

        # 3. Critical severity
        if conflict.severity == ConflictSeverity.CRITICAL:
            complexity = self._compute_complexity(conflict)
            return ConflictAdvice(
                conflict=conflict,
                strategy=MergeStrategy.HUMAN_REQUIRED,
                rationale=(
                    "Critical conflict with incompatible changes across "
                    f"{len(conflict.tasks_involved)} tasks."
                ),
                complexity_score=min(1.0, complexity),
                recommended_action=(
                    "Manual review required. Inspect conflicting changes "
                    "and decide which version to keep."
                ),
            )

        # 4. High severity
        if conflict.severity == ConflictSeverity.HIGH:
            complexity = self._compute_complexity(conflict)
            return ConflictAdvice(
                conflict=conflict,
                strategy=MergeStrategy.AI_REQUIRED,
                rationale=(
                    "High-severity conflict that may be resolvable with "
                    "AI-assisted merge."
                ),
                complexity_score=min(1.0, complexity),
                recommended_action=(
                    "Use AI-assisted merge to resolve overlapping changes, "
                    "then verify the result."
                ),
            )

        # 5. Medium/Low — try rebase or time-ordered merge
        complexity = self._compute_complexity(conflict)
        if len(conflict.tasks_involved) == 2:
            strategy = MergeStrategy.ORDER_BY_TIME
            action = (
                "Apply changes in chronological order. "
                "Rebase the later task onto the earlier one."
            )
        else:
            strategy = MergeStrategy.ORDER_BY_DEPENDENCY
            action = (
                "Analyze dependencies between tasks and apply in "
                "dependency order."
            )

        return ConflictAdvice(
            conflict=conflict,
            strategy=strategy,
            rationale=(
                f"{conflict.severity.value.title()}-severity conflict between "
                f"{len(conflict.tasks_involved)} tasks at {conflict.location}."
            ),
            complexity_score=complexity,
            recommended_action=action,
        )

    def _pick_additive_strategy(
        self, change_types: list[ChangeType]
    ) -> MergeStrategy:
        """Pick the best strategy for a set of additive change types."""
        for ct in change_types:
            if ct in _ADDITIVE_STRATEGY:
                return _ADDITIVE_STRATEGY[ct]
        return MergeStrategy.APPEND_STATEMENTS

    def _compute_complexity(self, conflict: ConflictRegion) -> float:
        """
        Compute a complexity score for a conflict.

        Factors:
        - Base severity score
        - Number of tasks involved (more tasks = harder)
        - Number of distinct change types (more variety = harder)
        """
        base = _SEVERITY_COMPLEXITY.get(conflict.severity, 0.5)

        # Extra complexity for many tasks
        task_factor = min(0.2, (len(conflict.tasks_involved) - 2) * 0.05)

        # Extra complexity for diverse change types
        unique_types = len(set(conflict.change_types))
        type_factor = min(0.15, (unique_types - 1) * 0.05)

        return min(1.0, base + task_factor + type_factor)
