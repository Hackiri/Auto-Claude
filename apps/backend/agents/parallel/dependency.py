"""
Dependency Analyzer
===================

Analyzes subtask dependencies to determine which subtasks can safely run in parallel.
Uses file overlap detection, service scoping, and explicit dependency tracking.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Information about a subtask's dependencies."""

    subtask_id: str
    depends_on: list[str]  # Subtask IDs this depends on
    depended_by: list[str]  # Subtask IDs that depend on this
    files_touched: set[str]  # Files this subtask modifies or creates
    service: str | None  # Service this subtask affects
    can_parallelize: bool  # Whether this can run with other subtasks


class DependencyAnalyzer:
    """
    Analyzes dependencies between subtasks to determine parallel execution safety.

    Two subtasks can run in parallel if:
    1. Neither depends on the other (explicit dependency)
    2. They don't modify overlapping files
    3. They operate on different services (or both are service-agnostic)
    4. The phase they're in is marked as parallel_safe
    """

    def __init__(self, implementation_plan: dict):
        """
        Initialize with an implementation plan.

        Args:
            implementation_plan: The implementation_plan.json as a dictionary
        """
        self.plan = implementation_plan
        self._dependency_graph: dict[str, DependencyInfo] = {}
        self._build_dependency_graph()

    def _build_dependency_graph(self):
        """Build the dependency graph from the implementation plan."""
        phases = self.plan.get("phases", [])

        # First pass: collect all subtask info
        for phase in phases:
            phase_id = phase.get("phase", 0)
            phase_depends_on = phase.get("depends_on", [])
            subtasks = phase.get("subtasks", phase.get("chunks", []))

            for subtask in subtasks:
                subtask_id = subtask.get("id", "")
                if not subtask_id:
                    continue

                files_touched = set(
                    subtask.get("files_to_modify", [])
                    + subtask.get("files_to_create", [])
                )

                self._dependency_graph[subtask_id] = DependencyInfo(
                    subtask_id=subtask_id,
                    depends_on=[],  # Will be filled in second pass
                    depended_by=[],
                    files_touched=files_touched,
                    service=subtask.get("service"),
                    can_parallelize=phase.get("parallel_safe", False),
                )

        # Second pass: build dependencies based on phase ordering
        # Subtasks in phase N depend on all subtasks in phases that phase N depends on
        for phase in phases:
            phase_id = phase.get("phase", 0)
            phase_depends_on = phase.get("depends_on", [])
            subtasks = phase.get("subtasks", phase.get("chunks", []))

            # Get subtask IDs from dependency phases
            dependency_subtasks = []
            for dep_phase_id in phase_depends_on:
                for other_phase in phases:
                    if other_phase.get("phase") == dep_phase_id:
                        for other_subtask in other_phase.get(
                            "subtasks", other_phase.get("chunks", [])
                        ):
                            if other_subtask.get("id"):
                                dependency_subtasks.append(other_subtask["id"])

            # Set dependencies for all subtasks in this phase
            for subtask in subtasks:
                subtask_id = subtask.get("id", "")
                if subtask_id and subtask_id in self._dependency_graph:
                    self._dependency_graph[subtask_id].depends_on = dependency_subtasks
                    # Update depended_by for dependency subtasks
                    for dep_id in dependency_subtasks:
                        if dep_id in self._dependency_graph:
                            self._dependency_graph[dep_id].depended_by.append(
                                subtask_id
                            )

    def get_subtask_dependencies(self, subtask_id: str) -> DependencyInfo | None:
        """Get dependency info for a specific subtask."""
        return self._dependency_graph.get(subtask_id)

    def can_run_parallel(self, subtask_a: str, subtask_b: str) -> tuple[bool, str]:
        """
        Check if two subtasks can safely run in parallel.

        Args:
            subtask_a: First subtask ID
            subtask_b: Second subtask ID

        Returns:
            Tuple of (can_run_parallel, reason)
        """
        info_a = self._dependency_graph.get(subtask_a)
        info_b = self._dependency_graph.get(subtask_b)

        if not info_a or not info_b:
            return False, "One or both subtasks not found in plan"

        # Check explicit dependencies
        if subtask_b in info_a.depends_on:
            return False, f"{subtask_a} depends on {subtask_b}"
        if subtask_a in info_b.depends_on:
            return False, f"{subtask_b} depends on {subtask_a}"

        # Check for file overlap
        file_overlap = info_a.files_touched & info_b.files_touched
        if file_overlap:
            return False, f"File overlap: {', '.join(list(file_overlap)[:3])}"

        # Check service conflicts (if both specify services, they must be different)
        if info_a.service and info_b.service and info_a.service == info_b.service:
            # Same service is OK if both are parallel_safe
            if not (info_a.can_parallelize and info_b.can_parallelize):
                return False, f"Same service ({info_a.service}) without parallel_safe"

        return True, "No conflicts detected"

    def get_parallel_groups(self, subtask_ids: list[str]) -> list[list[str]]:
        """
        Group subtasks into batches that can run in parallel.

        Args:
            subtask_ids: List of subtask IDs to analyze

        Returns:
            List of groups, where each group can run in parallel
        """
        if not subtask_ids:
            return []

        groups: list[list[str]] = []
        remaining = set(subtask_ids)

        while remaining:
            # Start a new group
            current_group: list[str] = []

            for subtask_id in list(remaining):
                # Check if this subtask can run with all others in the current group
                can_add = True
                for existing_id in current_group:
                    can_parallel, reason = self.can_run_parallel(
                        subtask_id, existing_id
                    )
                    if not can_parallel:
                        logger.debug(
                            f"Cannot run {subtask_id} with {existing_id}: {reason}"
                        )
                        can_add = False
                        break

                if can_add:
                    current_group.append(subtask_id)
                    remaining.remove(subtask_id)

            if current_group:
                groups.append(current_group)
            else:
                # Safety: if no progress was made, add one subtask to avoid infinite loop
                one_id = remaining.pop()
                groups.append([one_id])
                logger.warning(
                    f"Forced single-task group for {one_id} due to complex dependencies"
                )

        return groups

    def get_ready_subtasks(
        self, pending_ids: list[str], completed_ids: set[str]
    ) -> list[str]:
        """
        Get subtasks that are ready to run (all dependencies satisfied).

        Args:
            pending_ids: Subtask IDs that haven't started
            completed_ids: Subtask IDs that have completed

        Returns:
            List of subtask IDs ready to run
        """
        ready = []
        for subtask_id in pending_ids:
            info = self._dependency_graph.get(subtask_id)
            if not info:
                # Unknown subtask, assume ready
                ready.append(subtask_id)
                continue

            # Check if all dependencies are satisfied
            unsatisfied = [
                dep_id for dep_id in info.depends_on if dep_id not in completed_ids
            ]
            if not unsatisfied:
                ready.append(subtask_id)
            else:
                logger.debug(
                    f"Subtask {subtask_id} waiting on: {', '.join(unsatisfied)}"
                )

        return ready


def can_run_in_parallel(
    plan: dict, subtask_ids: list[str]
) -> tuple[bool, list[list[str]]]:
    """
    Convenience function to check if subtasks can run in parallel.

    Args:
        plan: Implementation plan dictionary
        subtask_ids: List of subtask IDs to check

    Returns:
        Tuple of (any_can_parallel, parallel_groups)
    """
    analyzer = DependencyAnalyzer(plan)
    groups = analyzer.get_parallel_groups(subtask_ids)

    # If any group has more than one subtask, we have parallelism
    any_parallel = any(len(group) > 1 for group in groups)

    return any_parallel, groups
