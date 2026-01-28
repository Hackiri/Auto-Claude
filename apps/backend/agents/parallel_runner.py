"""
Parallel Runner
===============

Entry point for running parallel sub-agent execution within the coder workflow.
This module bridges the main coder agent loop with the parallel execution module.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from ui import Icons, bold, box, highlight, icon, print_key_value, print_status

from .parallel import (
    DependencyAnalyzer,
    ParallelConfig,
    ParallelExecutor,
    ParallelResults,
    can_run_in_parallel,
)

if TYPE_CHECKING:
    from recovery import RecoveryManager

logger = logging.getLogger(__name__)


def is_parallel_execution_enabled() -> bool:
    """Check if parallel execution is enabled via environment variable."""
    return os.environ.get("PARALLEL_EXECUTION_ENABLED", "true").lower() == "true"


def get_parallel_config() -> ParallelConfig:
    """Get parallel execution configuration from environment."""
    max_concurrent = int(os.environ.get("MAX_CONCURRENT_SUBAGENTS", "4"))
    fail_fast = os.environ.get("PARALLEL_FAIL_FAST", "false").lower() == "true"
    fetch_mcp = os.environ.get("PARALLEL_FETCH_MCP", "true").lower() == "true"

    return ParallelConfig(
        max_concurrent=max_concurrent,
        enabled=is_parallel_execution_enabled(),
        fetch_mcp_context=fetch_mcp,
        fail_fast=fail_fast,
    )


async def check_parallel_opportunities(
    spec_dir: Path,
    plan: dict,
) -> tuple[bool, list[list[str]]]:
    """
    Check if there are parallelization opportunities in the current plan.

    Args:
        spec_dir: Spec directory
        plan: Implementation plan dictionary

    Returns:
        Tuple of (can_parallelize, parallel_groups)
    """
    if not is_parallel_execution_enabled():
        return False, []

    # Get all pending subtasks
    pending_subtasks = []
    phases = plan.get("phases", [])

    for phase in phases:
        # Skip phases that aren't parallel_safe
        if not phase.get("parallel_safe", False):
            continue

        for subtask in phase.get("subtasks", phase.get("chunks", [])):
            if subtask.get("status", "pending") == "pending":
                pending_subtasks.append(subtask.get("id", ""))

    if len(pending_subtasks) < 2:
        return False, []

    return can_run_in_parallel(plan, pending_subtasks)


async def run_parallel_phase(
    project_dir: Path,
    spec_dir: Path,
    plan: dict,
    phase: dict,
    model: str,
    session_num: int,
    recovery_manager: "RecoveryManager",
) -> ParallelResults | None:
    """
    Run a parallel-safe phase using sub-agents.

    Args:
        project_dir: Project root directory
        spec_dir: Spec directory
        plan: Full implementation plan
        phase: The phase to execute
        model: Claude model to use
        session_num: Current session number
        recovery_manager: Recovery manager for tracking

    Returns:
        ParallelResults if successful, None if parallel execution not applicable
    """
    if not phase.get("parallel_safe", False):
        logger.debug(f"Phase {phase.get('name')} is not parallel_safe, skipping")
        return None

    # Get pending subtasks from this phase
    pending_subtasks = [
        s
        for s in phase.get("subtasks", phase.get("chunks", []))
        if s.get("status", "pending") == "pending"
    ]

    if len(pending_subtasks) < 2:
        logger.debug(
            f"Phase has {len(pending_subtasks)} pending subtasks, skipping parallel"
        )
        return None

    # Print parallel execution header
    content = [
        bold(f"{icon(Icons.GEAR)} PARALLEL EXECUTION"),
        "",
        f"Phase: {highlight(phase.get('name', 'Unknown'))}",
        f"Subtasks: {len(pending_subtasks)} pending",
    ]
    print()
    print(box(content, width=70, style="double"))
    print()

    # Configure and run parallel executor
    config = get_parallel_config()
    executor = ParallelExecutor(
        project_dir=project_dir,
        spec_dir=spec_dir,
        config=config,
        model=model,
        recovery_manager=recovery_manager,
    )

    # Execute in parallel
    results = await executor.execute_parallel(
        subtasks=pending_subtasks,
        plan=plan,
        phase=phase,
        session_num=session_num,
    )

    # Print summary
    print()
    print_key_value("Completed", f"{results.completed_count}/{results.total_subtasks}")
    print_key_value("Failed", str(results.failed_count))
    print_key_value("Duration", f"{results.total_duration_seconds:.1f}s")
    print_key_value("Commits", str(results.commits_made_total))

    if results.has_conflicts:
        print_status(
            f"File conflicts detected: {', '.join(results.conflict_files[:3])}",
            "warning",
        )

    return results


async def get_parallelizable_subtasks(
    spec_dir: Path,
    plan: dict,
) -> list[dict]:
    """
    Get all subtasks that can be run in parallel right now.

    This considers:
    1. Phase dependencies (phase must have all deps satisfied)
    2. Phase parallel_safe flag
    3. Subtask status (only pending)
    4. File overlap between subtasks

    Args:
        spec_dir: Spec directory
        plan: Implementation plan dictionary

    Returns:
        List of subtask dictionaries that can run in parallel
    """
    if not is_parallel_execution_enabled():
        return []

    analyzer = DependencyAnalyzer(plan)
    parallelizable = []

    phases = plan.get("phases", [])

    # Find completed phases
    completed_phases = set()
    for phase in phases:
        subtasks = phase.get("subtasks", phase.get("chunks", []))
        if all(s.get("status") == "completed" for s in subtasks):
            completed_phases.add(phase.get("phase", 0))

    for phase in phases:
        phase_id = phase.get("phase", 0)
        depends_on = phase.get("depends_on", [])

        # Check if all dependencies are satisfied
        if not all(dep in completed_phases for dep in depends_on):
            continue

        # Only consider parallel_safe phases
        if not phase.get("parallel_safe", False):
            continue

        # Get pending subtasks
        for subtask in phase.get("subtasks", phase.get("chunks", [])):
            if subtask.get("status", "pending") == "pending":
                subtask_copy = subtask.copy()
                subtask_copy["phase_name"] = phase.get("name")
                subtask_copy["phase_number"] = phase_id
                parallelizable.append(subtask_copy)

    # Now filter to only subtasks that don't conflict
    if len(parallelizable) < 2:
        return parallelizable

    subtask_ids = [s.get("id", "") for s in parallelizable]
    _, groups = can_run_in_parallel(plan, subtask_ids)

    # Return the first group that can run together
    if groups and len(groups[0]) > 1:
        group_ids = set(groups[0])
        return [s for s in parallelizable if s.get("id", "") in group_ids]

    return []


def should_use_parallel_execution(
    spec_dir: Path,
    plan: dict,
) -> bool:
    """
    Quick check to determine if parallel execution should be attempted.

    Args:
        spec_dir: Spec directory
        plan: Implementation plan dictionary

    Returns:
        True if parallel execution should be attempted
    """
    if not is_parallel_execution_enabled():
        return False

    # Check if any phase is parallel_safe
    for phase in plan.get("phases", []):
        if phase.get("parallel_safe", False):
            subtasks = phase.get("subtasks", phase.get("chunks", []))
            pending = [s for s in subtasks if s.get("status", "pending") == "pending"]
            if len(pending) >= 2:
                return True

    return False
