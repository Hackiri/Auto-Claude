#!/usr/bin/env python3
"""
Phase Models
============

Defines a group of subtasks with dependencies and progress tracking.
"""

from dataclasses import dataclass, field

from .enums import PhaseType, SubtaskStatus
from .subtask import Subtask


@dataclass
class Phase:
    """A group of subtasks with dependencies."""

    phase: int
    name: str
    type: PhaseType = PhaseType.IMPLEMENTATION
    subtasks: list[Subtask] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    parallel_safe: bool = False  # Can subtasks in this phase run in parallel?

    # Backwards compatibility: chunks is an alias for subtasks
    @property
    def chunks(self) -> list[Subtask]:
        """Alias for subtasks (backwards compatibility)."""
        return self.subtasks

    @chunks.setter
    def chunks(self, value: list[Subtask]):
        """Alias for subtasks (backwards compatibility)."""
        self.subtasks = value

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "phase": self.phase,
            "name": self.name,
            "type": self.type.value,
            "subtasks": [s.to_dict() for s in self.subtasks],
            # Also include 'chunks' for backwards compatibility
            "chunks": [s.to_dict() for s in self.subtasks],
        }
        if self.depends_on:
            result["depends_on"] = self.depends_on
        if self.parallel_safe:
            result["parallel_safe"] = True
        return result

    @classmethod
    def from_dict(cls, data: dict, fallback_phase: int = 1) -> "Phase":
        """Create Phase from dict. Uses fallback_phase if 'phase' field is missing."""
        # Support both 'subtasks' and 'chunks' keys for backwards compatibility
        subtask_data = data.get("subtasks", data.get("chunks", []))
        return cls(
            phase=data.get("phase", fallback_phase),
            name=data.get("name", f"Phase {fallback_phase}"),
            type=PhaseType(data.get("type", "implementation")),
            subtasks=[Subtask.from_dict(s) for s in subtask_data],
            depends_on=data.get("depends_on", []),
            parallel_safe=data.get("parallel_safe", False),
        )

    def is_complete(self) -> bool:
        """Check if all subtasks in this phase are done."""
        return all(s.status == SubtaskStatus.COMPLETED for s in self.subtasks)

    def get_pending_subtasks(self) -> list[Subtask]:
        """Get subtasks that can be worked on."""
        return [s for s in self.subtasks if s.status == SubtaskStatus.PENDING]

    # Backwards compatibility alias
    def get_pending_chunks(self) -> list[Subtask]:
        """Alias for get_pending_subtasks (backwards compatibility)."""
        return self.get_pending_subtasks()

    def get_progress(self) -> tuple[int, int]:
        """Get (completed, total) subtask counts."""
        done = sum(1 for s in self.subtasks if s.status == SubtaskStatus.COMPLETED)
        return done, len(self.subtasks)

    def validate_dependencies(self) -> tuple[bool, list[str]]:
        """
        Validate subtask dependencies within this phase.

        Checks:
        1. All dependency IDs reference existing subtasks in this phase
        2. No circular dependencies exist

        Returns:
            (is_valid, error_messages) tuple
        """
        errors: list[str] = []
        subtask_ids = {st.id for st in self.subtasks}

        # Check all dependency IDs exist within this phase
        for subtask in self.subtasks:
            for dep_id in subtask.blocks:
                if dep_id not in subtask_ids:
                    errors.append(
                        f"Subtask '{subtask.id}' depends on non-existent subtask '{dep_id}'"
                    )
                elif dep_id == subtask.id:
                    errors.append(f"Subtask '{subtask.id}' cannot depend on itself")

        # Check for cycles only if no ID errors
        if not errors:
            is_acyclic, cycle = self._detect_cycles()
            if not is_acyclic:
                errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")

        return len(errors) == 0, errors

    def _detect_cycles(self) -> tuple[bool, list[str]]:
        """
        Detect circular dependencies using DFS-based topological sort.

        Returns:
            (is_acyclic, cycle_path) tuple where cycle_path is empty if no cycle
        """
        # Build adjacency list from blocks field
        # blocks means "must complete before this", so edges go: dependency -> dependent
        graph: dict[str, list[str]] = {st.id: [] for st in self.subtasks}
        for subtask in self.subtasks:
            for dep_id in subtask.blocks:
                if dep_id in graph:  # Only add if valid ID
                    graph[dep_id].append(subtask.id)

        # DFS state: 0 = unvisited, 1 = visiting (in stack), 2 = visited
        state: dict[str, int] = {st_id: 0 for st_id in graph}
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            """Returns cycle path if found, None otherwise."""
            if state[node] == 1:
                # Found cycle - reconstruct path from node back to node
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            if state[node] == 2:
                return None

            state[node] = 1
            path.append(node)

            for neighbor in graph[node]:
                result = dfs(neighbor)
                if result:
                    return result

            path.pop()
            state[node] = 2
            return None

        # Check all nodes (handles disconnected components)
        for start_node in graph:
            if state[start_node] == 0:
                cycle = dfs(start_node)
                if cycle:
                    return False, cycle

        return True, []

    def compute_blocked_by(self) -> None:
        """
        Compute the blocked_by field for all subtasks based on blocks.

        blocked_by is the inverse of blocks:
        If A.blocks = [B], then B.blocked_by should include A
        """
        # Build reverse mapping
        blocked_by_map: dict[str, list[str]] = {st.id: [] for st in self.subtasks}

        for subtask in self.subtasks:
            for dep_id in subtask.blocks:
                if dep_id in blocked_by_map:
                    blocked_by_map[dep_id].append(subtask.id)

        # Apply to subtasks
        for subtask in self.subtasks:
            subtask.blocked_by = blocked_by_map[subtask.id]
