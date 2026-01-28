"""
Ralph Loop Package
==================

Implements the "Ralph Wiggum" iterative AI development technique for
autonomous overnight builds. This module provides:

- Configuration for iterative loop behavior
- Completion promise definitions and evaluation
- Retry strategies with approach variation
- Overnight run summary reporting

Usage:
    from ralph_loop import RalphLoopConfig, load_ralph_config

    # Load configuration
    config = load_ralph_config(spec_dir, cli_args)

    # Run with Ralph loop mode enabled
    result = run_autonomous_agent(
        project_dir=project_dir,
        spec_dir=spec_dir,
        ralph_config=config
    )

Module structure:
    - config.py: RalphLoopConfig and configuration loading
    - promises.py: CompletionPromise definitions and evaluation
    - strategy.py: RetryStrategy with approach variation
    - reporter.py: Overnight run summary generation
"""

# Configuration
from .config import (
    DEFAULT_RALPH_CONFIG,
    VALID_RETRY_STRATEGIES,
    RalphLoopConfig,
    get_default_config,
    get_max_iterations,
    is_ralph_loop_enabled,
    load_ralph_config,
    load_ralph_config_from_metadata,
)

# Completion promises
from .promises import (
    CompletionPromise,
    PromiseResult,
    PromiseType,
    evaluate_all_promises,
    evaluate_promise,
    get_default_promises,
    load_promises_from_plan,
)

# Reporter
from .reporter import (
    IterationRecord,
    RalphLoopReporter,
    RalphLoopSummary,
    clear_ralph_history,
    generate_ralph_report,
    get_ralph_run_status,
)

# Retry strategies
from .strategy import (
    ApproachCategory,
    ApproachSuggestion,
    RetryDecision,
    RetryStrategy,
    RetryStrategyType,
    create_retry_strategy,
    get_retry_hints,
    get_varied_approach,
)

# Public API
__all__ = [
    # Configuration
    "RalphLoopConfig",
    "DEFAULT_RALPH_CONFIG",
    "VALID_RETRY_STRATEGIES",
    "get_default_config",
    "load_ralph_config_from_metadata",
    "load_ralph_config",
    "is_ralph_loop_enabled",
    "get_max_iterations",
    # Completion promises
    "PromiseType",
    "CompletionPromise",
    "PromiseResult",
    "evaluate_promise",
    "evaluate_all_promises",
    "load_promises_from_plan",
    "get_default_promises",
    # Retry strategies
    "RetryStrategyType",
    "ApproachCategory",
    "ApproachSuggestion",
    "RetryDecision",
    "RetryStrategy",
    "get_varied_approach",
    "get_retry_hints",
    "create_retry_strategy",
    # Reporter
    "IterationRecord",
    "RalphLoopSummary",
    "RalphLoopReporter",
    "generate_ralph_report",
    "get_ralph_run_status",
    "clear_ralph_history",
]
