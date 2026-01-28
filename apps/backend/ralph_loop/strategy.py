"""
Retry Strategy Module
=====================

Implements intelligent retry strategies for the Ralph Wiggum iterative loop.
Strategies determine how to vary approach after failures, with different
levels of aggressiveness and adaptation.

Key Features:
- Three strategy types: conservative, aggressive, adaptive
- Approach variation based on failure history
- Integration with RecoveryManager for attempt tracking
- Smart hints for different approaches
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RetryStrategyType(Enum):
    """Types of retry strategies available."""

    CONSERVATIVE = "conservative"  # Fewer retries, longer delays, careful approach
    AGGRESSIVE = "aggressive"  # More retries, shorter delays, try many approaches
    ADAPTIVE = "adaptive"  # Adjust based on failure patterns


class ApproachCategory(Enum):
    """Categories of alternative approaches to try."""

    SIMPLIFY = "simplify"  # Try a simpler implementation
    ALTERNATIVE = "alternative"  # Use different library/pattern
    DECOMPOSE = "decompose"  # Break into smaller pieces
    REFACTOR = "refactor"  # Restructure existing code
    WORKAROUND = "workaround"  # Find a different path to the goal
    DEBUG = "debug"  # Focus on understanding the issue first


@dataclass
class ApproachSuggestion:
    """A suggested alternative approach for retry.

    Attributes:
        category: Category of the approach
        description: What to do differently
        hints: Specific hints for this approach
        priority: Priority level (1=highest)
    """

    category: ApproachCategory
    description: str
    hints: list[str] = field(default_factory=list)
    priority: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "description": self.description,
            "hints": self.hints,
            "priority": self.priority,
        }


@dataclass
class RetryDecision:
    """Decision about whether and how to retry.

    Attributes:
        should_retry: Whether to retry the operation
        delay_seconds: How long to wait before retrying
        approach: Suggested approach for the retry
        reason: Human-readable reason for the decision
        attempt_number: Which attempt this would be
    """

    should_retry: bool
    delay_seconds: float
    approach: ApproachSuggestion | None
    reason: str
    attempt_number: int


class RetryStrategy:
    """
    Manages retry logic and approach variation for Ralph loop.

    The strategy determines:
    - Whether to retry after a failure
    - How long to wait before retrying
    - What different approach to try

    Different strategy types have different behaviors:
    - CONSERVATIVE: Max 3 retries, exponential backoff, careful changes
    - AGGRESSIVE: Max 5 retries, minimal delays, many approach variations
    - ADAPTIVE: Adjusts based on failure patterns and progress
    """

    # Default limits per strategy type
    STRATEGY_LIMITS = {
        RetryStrategyType.CONSERVATIVE: {
            "max_retries": 3,
            "base_delay": 5.0,
            "max_delay": 60.0,
            "backoff_factor": 2.0,
        },
        RetryStrategyType.AGGRESSIVE: {
            "max_retries": 5,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "backoff_factor": 1.5,
        },
        RetryStrategyType.ADAPTIVE: {
            "max_retries": 4,
            "base_delay": 2.0,
            "max_delay": 45.0,
            "backoff_factor": 1.75,
        },
    }

    def __init__(
        self,
        strategy_type: RetryStrategyType | str = RetryStrategyType.ADAPTIVE,
        max_retries: int | None = None,
        base_delay: float | None = None,
    ):
        """
        Initialize the retry strategy.

        Args:
            strategy_type: Type of strategy (conservative, aggressive, adaptive)
            max_retries: Override default max retries (optional)
            base_delay: Override default base delay in seconds (optional)
        """
        # Normalize string to enum
        if isinstance(strategy_type, str):
            try:
                self.strategy_type = RetryStrategyType(strategy_type.lower())
            except ValueError:
                logging.warning(
                    f"Unknown strategy type '{strategy_type}', using adaptive"
                )
                self.strategy_type = RetryStrategyType.ADAPTIVE
        else:
            self.strategy_type = strategy_type

        # Get defaults for this strategy type
        defaults = self.STRATEGY_LIMITS[self.strategy_type]

        # Apply overrides
        self.max_retries = (
            max_retries if max_retries is not None else defaults["max_retries"]
        )
        self.base_delay = (
            base_delay if base_delay is not None else defaults["base_delay"]
        )
        self.max_delay = defaults["max_delay"]
        self.backoff_factor = defaults["backoff_factor"]

        # Track approach usage to avoid repetition
        self._used_approaches: list[ApproachCategory] = []

    def should_retry(
        self,
        attempt_count: int,
        error: str | None = None,
        consecutive_failures: int = 0,
    ) -> RetryDecision:
        """
        Decide whether to retry and how.

        Args:
            attempt_count: Number of attempts so far
            error: The error message from the last attempt
            consecutive_failures: Number of consecutive failures

        Returns:
            RetryDecision with retry information
        """
        # Check if we've exceeded max retries
        if attempt_count >= self.max_retries:
            return RetryDecision(
                should_retry=False,
                delay_seconds=0,
                approach=None,
                reason=f"Max retries ({self.max_retries}) exceeded",
                attempt_number=attempt_count + 1,
            )

        # Calculate delay with exponential backoff
        delay = min(
            self.base_delay * (self.backoff_factor**attempt_count),
            self.max_delay,
        )

        # Adaptive strategy adjustments
        if self.strategy_type == RetryStrategyType.ADAPTIVE:
            delay = self._adaptive_delay(delay, consecutive_failures, error)

        # Get suggested approach
        approach = self._get_suggested_approach(attempt_count, error)

        return RetryDecision(
            should_retry=True,
            delay_seconds=delay,
            approach=approach,
            reason=f"Retry attempt {attempt_count + 1}/{self.max_retries}",
            attempt_number=attempt_count + 1,
        )

    def _adaptive_delay(
        self,
        base_delay: float,
        consecutive_failures: int,
        error: str | None,
    ) -> float:
        """Adjust delay based on failure patterns (adaptive strategy)."""
        delay = base_delay

        # Increase delay for many consecutive failures
        if consecutive_failures >= 3:
            delay *= 1.5
            logging.info(
                f"Adaptive: Increased delay due to {consecutive_failures} consecutive failures"
            )

        # Check for rate limit errors - add extra delay
        if error and any(
            term in error.lower()
            for term in ["rate limit", "429", "too many requests", "throttl"]
        ):
            delay = max(delay, 30.0)  # At least 30 seconds for rate limits
            logging.info("Adaptive: Extended delay due to rate limit error")

        return min(delay, self.max_delay)

    def _get_suggested_approach(
        self,
        attempt_count: int,
        error: str | None,
    ) -> ApproachSuggestion:
        """Get a suggested alternative approach based on attempt history."""
        # Analyze error to determine best approach category
        category = self._categorize_approach_from_error(error, attempt_count)

        # Track that we're using this approach
        self._used_approaches.append(category)

        # Get specific suggestions for this category
        return self._build_approach_suggestion(category, error, attempt_count)

    def _categorize_approach_from_error(
        self,
        error: str | None,
        attempt_count: int,
    ) -> ApproachCategory:
        """Determine which approach category to suggest based on error."""
        error_lower = (error or "").lower()

        # First attempt after initial failure - try debugging
        if attempt_count == 1:
            return ApproachCategory.DEBUG

        # Complexity-related errors suggest simplification
        complexity_indicators = [
            "complex",
            "too large",
            "memory",
            "timeout",
            "context",
            "token limit",
        ]
        if any(ind in error_lower for ind in complexity_indicators):
            return ApproachCategory.SIMPLIFY

        # Import/module errors suggest alternative libraries
        module_indicators = [
            "import",
            "module",
            "package",
            "dependency",
            "not found",
            "cannot find",
        ]
        if any(ind in error_lower for ind in module_indicators):
            return ApproachCategory.ALTERNATIVE

        # Type/syntax errors suggest refactoring
        code_indicators = [
            "syntax",
            "type",
            "attribute",
            "undefined",
            "not defined",
            "indentation",
        ]
        if any(ind in error_lower for ind in code_indicators):
            return ApproachCategory.REFACTOR

        # Circular fix pattern - decompose or workaround
        if attempt_count >= 3:
            # Avoid categories we've already tried
            unused = [
                c for c in ApproachCategory if c not in self._used_approaches[-3:]
            ]
            if unused:
                return random.choice(unused)
            return ApproachCategory.WORKAROUND

        # Default progression: debug -> simplify -> alternative -> decompose
        progression = [
            ApproachCategory.DEBUG,
            ApproachCategory.SIMPLIFY,
            ApproachCategory.ALTERNATIVE,
            ApproachCategory.DECOMPOSE,
            ApproachCategory.WORKAROUND,
        ]
        index = min(attempt_count, len(progression) - 1)
        return progression[index]

    def _build_approach_suggestion(
        self,
        category: ApproachCategory,
        error: str | None,
        attempt_count: int,
    ) -> ApproachSuggestion:
        """Build detailed approach suggestion for a category."""
        suggestions = {
            ApproachCategory.DEBUG: ApproachSuggestion(
                category=ApproachCategory.DEBUG,
                description="Focus on understanding the root cause before fixing",
                hints=[
                    "Add logging/print statements to trace execution",
                    "Check if the error is in the implementation or the approach",
                    "Verify assumptions about inputs/outputs",
                    "Read the error message carefully for clues",
                ],
                priority=1,
            ),
            ApproachCategory.SIMPLIFY: ApproachSuggestion(
                category=ApproachCategory.SIMPLIFY,
                description="Try a simpler implementation",
                hints=[
                    "Remove non-essential features temporarily",
                    "Use a more straightforward algorithm",
                    "Reduce number of edge cases handled",
                    "Start with a minimal working version",
                ],
                priority=2,
            ),
            ApproachCategory.ALTERNATIVE: ApproachSuggestion(
                category=ApproachCategory.ALTERNATIVE,
                description="Use a different library, pattern, or tool",
                hints=[
                    "Try a different library for the same functionality",
                    "Use a built-in solution instead of custom code",
                    "Consider a different design pattern",
                    "Look for established solutions to this problem",
                ],
                priority=3,
            ),
            ApproachCategory.DECOMPOSE: ApproachSuggestion(
                category=ApproachCategory.DECOMPOSE,
                description="Break the task into smaller, independent pieces",
                hints=[
                    "Identify the smallest testable unit",
                    "Implement and verify one piece at a time",
                    "Create helper functions for complex logic",
                    "Separate concerns into distinct modules",
                ],
                priority=3,
            ),
            ApproachCategory.REFACTOR: ApproachSuggestion(
                category=ApproachCategory.REFACTOR,
                description="Restructure existing code to fix the issue",
                hints=[
                    "Fix type annotations and ensure consistency",
                    "Clean up imports and dependencies",
                    "Reorganize code structure for clarity",
                    "Address any code smell that might cause the error",
                ],
                priority=4,
            ),
            ApproachCategory.WORKAROUND: ApproachSuggestion(
                category=ApproachCategory.WORKAROUND,
                description="Find a different path to achieve the goal",
                hints=[
                    "Consider if the requirement can be met differently",
                    "Skip the problematic part and continue",
                    "Use a completely different approach to the problem",
                    "Accept a partial solution if full solution is blocked",
                ],
                priority=5,
            ),
        }

        suggestion = suggestions.get(
            category,
            ApproachSuggestion(
                category=category,
                description="Try a different approach",
                hints=["Review what was tried and do something different"],
                priority=5,
            ),
        )

        # Add attempt-specific context
        if attempt_count >= 2:
            suggestion.hints.insert(
                0,
                f"This is attempt {attempt_count + 1} - previous approaches failed",
            )

        return suggestion

    def reset(self) -> None:
        """Reset the strategy state (clear used approaches)."""
        self._used_approaches.clear()

    def get_strategy_info(self) -> dict[str, Any]:
        """Get information about this strategy configuration."""
        return {
            "type": self.strategy_type.value,
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
        }


def get_varied_approach(
    attempt_count: int,
    previous_approaches: list[str] | None = None,
    error: str | None = None,
    strategy: str = "adaptive",
) -> ApproachSuggestion:
    """
    Get a varied approach suggestion for retrying a failed task.

    This is a convenience function that creates a RetryStrategy and
    generates an approach suggestion.

    Args:
        attempt_count: Number of attempts so far
        previous_approaches: List of approach descriptions from previous attempts
        error: The error message from the last attempt
        strategy: Strategy type ("conservative", "aggressive", "adaptive")

    Returns:
        ApproachSuggestion with category, description, and hints
    """
    retry_strategy = RetryStrategy(strategy_type=strategy)

    # Mark previous approach categories as used
    if previous_approaches:
        for approach_desc in previous_approaches:
            category = _infer_category_from_description(approach_desc)
            if category:
                retry_strategy._used_approaches.append(category)

    return retry_strategy._get_suggested_approach(attempt_count, error)


def _infer_category_from_description(description: str) -> ApproachCategory | None:
    """Infer approach category from a description string."""
    desc_lower = description.lower()

    category_keywords = {
        ApproachCategory.SIMPLIFY: ["simpl", "basic", "minimal", "strip"],
        ApproachCategory.ALTERNATIVE: ["alternat", "different", "another", "instead"],
        ApproachCategory.DECOMPOSE: ["break", "split", "decompos", "smaller"],
        ApproachCategory.REFACTOR: ["refactor", "restructur", "reorganiz", "clean"],
        ApproachCategory.WORKAROUND: ["workaround", "bypass", "skip", "avoid"],
        ApproachCategory.DEBUG: ["debug", "trace", "log", "understand"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return category

    return None


def get_retry_hints(
    attempt_count: int,
    error: str | None = None,
    strategy: str = "adaptive",
) -> list[str]:
    """
    Get retry hints for the given attempt context.

    This is a convenience function that returns just the hints
    from an approach suggestion.

    Args:
        attempt_count: Number of attempts so far
        error: The error message from the last attempt
        strategy: Strategy type

    Returns:
        List of hint strings
    """
    approach = get_varied_approach(
        attempt_count=attempt_count,
        error=error,
        strategy=strategy,
    )

    hints = [f"Suggested approach: {approach.description}"]
    hints.extend(approach.hints)

    return hints


def create_retry_strategy(
    strategy_type: str = "adaptive",
    max_retries: int | None = None,
    base_delay: float | None = None,
) -> RetryStrategy:
    """
    Create a RetryStrategy with the given configuration.

    This is a factory function for creating strategies with
    custom parameters.

    Args:
        strategy_type: Type of strategy ("conservative", "aggressive", "adaptive")
        max_retries: Maximum number of retries (optional, uses strategy default)
        base_delay: Base delay between retries in seconds (optional)

    Returns:
        Configured RetryStrategy instance
    """
    return RetryStrategy(
        strategy_type=strategy_type,
        max_retries=max_retries,
        base_delay=base_delay,
    )
