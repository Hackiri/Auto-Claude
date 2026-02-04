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

        # First pass: collect all subtask info and explicit subtask-level dependencies
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

                # Read explicit subtask-level dependencies (blocks field)
                explicit_deps = subtask.get("blocks", [])

                self._dependency_graph[subtask_id] = DependencyInfo(
                    subtask_id=subtask_id,
                    depends_on=list(explicit_deps),  # Start with explicit deps
                    depended_by=[],
                    files_touched=files_touched,
                    service=subtask.get("service"),
                    can_parallelize=phase.get("parallel_safe", False),
                )

        # Second pass: add phase-level dependencies
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

            # Add phase-level dependencies to all subtasks in this phase
            for subtask in subtasks:
                subtask_id = subtask.get("id", "")
                if subtask_id and subtask_id in self._dependency_graph:
                    # Merge phase-level deps with existing subtask-level deps
                    existing_deps = set(self._dependency_graph[subtask_id].depends_on)
                    existing_deps.update(dependency_subtasks)
                    self._dependency_graph[subtask_id].depends_on = list(existing_deps)

        # Third pass: build depended_by (reverse of depends_on)
        for subtask_id, info in self._dependency_graph.items():
            for dep_id in info.depends_on:
                if dep_id in self._dependency_graph:
                    if subtask_id not in self._dependency_graph[dep_id].depended_by:
                        self._dependency_graph[dep_id].depended_by.append(subtask_id)

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

    def get_wave_groups(self, subtask_ids: list[str] | None = None) -> list[list[str]]:
        """
        Group subtasks into dependency waves for wave-based execution.

        Wave 0: Subtasks with no dependencies
        Wave N: Subtasks that depend only on subtasks in waves < N

        This is useful for understanding the minimum number of sequential steps
        required to complete all subtasks when maximizing parallelism.

        Args:
            subtask_ids: Optional list of subtask IDs to analyze.
                        If None, uses all subtasks in the graph.

        Returns:
            List of waves, where each wave is a list of subtask IDs that can
            run in parallel once all previous waves are complete.

        Raises:
            ValueError: If circular dependencies are detected
        """
        if subtask_ids is None:
            subtask_ids = list(self._dependency_graph.keys())

        # Filter to only requested subtasks
        remaining = {
            st_id: set(self._dependency_graph[st_id].depends_on) & set(subtask_ids)
            for st_id in subtask_ids
            if st_id in self._dependency_graph
        }
        completed: set[str] = set()
        waves: list[list[str]] = []

        while remaining:
            # Find subtasks whose dependencies are all completed
            current_wave = [
                st_id
                for st_id, deps in remaining.items()
                if deps.issubset(completed)
            ]

            if not current_wave:
                # No progress possible - circular dependency detected
                cycle_nodes = list(remaining.keys())
                raise ValueError(
                    f"Circular dependency detected among subtasks: {cycle_nodes}"
                )

            waves.append(current_wave)

            # Move current wave to completed
            for st_id in current_wave:
                completed.add(st_id)
                del remaining[st_id]

        return waves

    def get_subtask_wave(self, subtask_id: str) -> int:
        """
        Get the wave number for a specific subtask.

        Wave 0 means no dependencies, higher wave means more dependencies.

        Args:
            subtask_id: The subtask ID to check

        Returns:
            Wave number (0-based), or -1 if subtask not found
        """
        if subtask_id not in self._dependency_graph:
            return -1

        try:
            waves = self.get_wave_groups()
            for wave_num, wave in enumerate(waves):
                if subtask_id in wave:
                    return wave_num
            return -1
        except ValueError:
            # Circular dependency - can't compute wave
            return -1

    def get_phase_subtask_dependencies(self, phase_num: int) -> dict[str, DependencyInfo]:
        """
        Get dependency info for all subtasks in a specific phase.

        This is useful for analyzing dependencies within a single phase,
        ignoring cross-phase dependencies.

        Args:
            phase_num: The phase number to analyze

        Returns:
            Dictionary mapping subtask IDs to their DependencyInfo
        """
        phases = self.plan.get("phases", [])
        result: dict[str, DependencyInfo] = {}

        # Find the phase
        for phase in phases:
            if phase.get("phase") == phase_num:
                subtasks = phase.get("subtasks", phase.get("chunks", []))
                phase_subtask_ids = {s.get("id") for s in subtasks if s.get("id")}

                for subtask in subtasks:
                    subtask_id = subtask.get("id", "")
                    if subtask_id and subtask_id in self._dependency_graph:
                        info = self._dependency_graph[subtask_id]
                        # Filter dependencies to only those within this phase
                        within_phase_deps = [
                            dep for dep in info.depends_on
                            if dep in phase_subtask_ids
                        ]
                        within_phase_depended_by = [
                            dep for dep in info.depended_by
                            if dep in phase_subtask_ids
                        ]
                        result[subtask_id] = DependencyInfo(
                            subtask_id=subtask_id,
                            depends_on=within_phase_deps,
                            depended_by=within_phase_depended_by,
                            files_touched=info.files_touched,
                            service=info.service,
                            can_parallelize=info.can_parallelize,
                        )
                break

        return result


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
