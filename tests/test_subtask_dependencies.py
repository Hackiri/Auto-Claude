#!/usr/bin/env python3
"""
Tests for Subtask-Level Dependency Tracking
============================================

Tests the subtask-level dependency system including:
- Dependency fields (blocks, blocked_by)
- Cycle detection
- Wave-based grouping
- Ready subtask selection
- Backward compatibility with plans lacking dependency fields
"""

import pytest

from implementation_plan import (
    ImplementationPlan,
    Phase,
    Subtask,
    SubtaskStatus,
    PhaseType,
    WorkflowType,
)
from agents.parallel.dependency import DependencyAnalyzer


class TestSubtaskDependencyFields:
    """Tests for blocks and blocked_by fields on Subtask."""

    def test_subtask_default_empty_blocks(self):
        """Subtask defaults to empty blocks list."""
        subtask = Subtask(id="test", description="Test task")

        assert subtask.blocks == []
        assert subtask.blocked_by == []

    def test_subtask_with_blocks(self):
        """Subtask can be created with blocks."""
        subtask = Subtask(
            id="task-2",
            description="Depends on task-1",
            blocks=["task-1"],
        )

        assert subtask.blocks == ["task-1"]
        assert subtask.blocked_by == []

    def test_subtask_to_dict_includes_blocks(self):
        """Subtask serialization includes blocks when present."""
        subtask = Subtask(
            id="task-2",
            description="Test",
            blocks=["task-1"],
        )

        data = subtask.to_dict()

        assert "blocks" in data
        assert data["blocks"] == ["task-1"]

    def test_subtask_to_dict_omits_empty_blocks(self):
        """Subtask serialization omits empty blocks arrays."""
        subtask = Subtask(id="task-1", description="Test")

        data = subtask.to_dict()

        # Empty lists should not be serialized (to keep JSON clean)
        assert "blocks" not in data or data.get("blocks") == []

    def test_subtask_from_dict_with_blocks(self):
        """Subtask deserialization handles blocks field."""
        data = {
            "id": "task-2",
            "description": "Test",
            "blocks": ["task-1"],
            "blocked_by": ["task-3"],
        }

        subtask = Subtask.from_dict(data)

        assert subtask.blocks == ["task-1"]
        assert subtask.blocked_by == ["task-3"]

    def test_subtask_from_dict_missing_blocks(self):
        """Subtask deserialization defaults to empty blocks."""
        data = {
            "id": "task-1",
            "description": "Test",
        }

        subtask = Subtask.from_dict(data)

        assert subtask.blocks == []
        assert subtask.blocked_by == []

    def test_subtask_roundtrip_preserves_blocks(self):
        """Subtask survives to_dict/from_dict roundtrip."""
        original = Subtask(
            id="task-3",
            description="Depends on both 1 and 2",
            blocks=["task-1", "task-2"],
            blocked_by=["task-4"],
        )

        data = original.to_dict()
        restored = Subtask.from_dict(data)

        assert restored.blocks == ["task-1", "task-2"]
        assert restored.blocked_by == ["task-4"]


class TestPhaseDependencyValidation:
    """Tests for dependency validation in Phase class."""

    def test_validate_no_dependencies(self):
        """Phase with no dependencies is valid."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-1", description="Task 1"),
                Subtask(id="task-2", description="Task 2"),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is True
        assert errors == []

    def test_validate_valid_dependencies(self):
        """Phase with valid dependencies passes validation."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-1", description="No deps"),
                Subtask(id="task-2", description="Depends on task-1", blocks=["task-1"]),
                Subtask(id="task-3", description="Depends on task-2", blocks=["task-2"]),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is True
        assert errors == []

    def test_validate_invalid_dependency_id(self):
        """Phase with invalid dependency ID fails validation."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-1", description="No deps"),
                Subtask(
                    id="task-2",
                    description="Bad dependency",
                    blocks=["non-existent-task"],
                ),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is False
        assert len(errors) == 1
        assert "non-existent-task" in errors[0]

    def test_validate_self_dependency(self):
        """Phase with self-dependency fails validation."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-1", description="Self-dep", blocks=["task-1"]),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is False
        assert len(errors) == 1
        assert "cannot depend on itself" in errors[0]

    def test_validate_circular_dependency_simple(self):
        """Phase with simple A -> B -> A cycle fails validation."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-a", description="A", blocks=["task-b"]),
                Subtask(id="task-b", description="B", blocks=["task-a"]),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is False
        assert len(errors) == 1
        assert "Circular dependency" in errors[0]

    def test_validate_circular_dependency_three_nodes(self):
        """Phase with A -> B -> C -> A cycle fails validation."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-a", description="A", blocks=["task-c"]),
                Subtask(id="task-b", description="B", blocks=["task-a"]),
                Subtask(id="task-c", description="C", blocks=["task-b"]),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is False
        assert "Circular dependency" in errors[0]

    def test_validate_multiple_dependencies_no_cycle(self):
        """Phase with diamond dependency (no cycle) passes."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-1", description="Root"),
                Subtask(id="task-2", description="Branch A", blocks=["task-1"]),
                Subtask(id="task-3", description="Branch B", blocks=["task-1"]),
                Subtask(id="task-4", description="Merge", blocks=["task-2", "task-3"]),
            ],
        )

        is_valid, errors = phase.validate_dependencies()

        assert is_valid is True
        assert errors == []


class TestPhaseComputeBlockedBy:
    """Tests for compute_blocked_by method."""

    def test_compute_blocked_by_simple(self):
        """Computes blocked_by correctly for simple chain."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="task-1", description="First"),
                Subtask(id="task-2", description="Second", blocks=["task-1"]),
                Subtask(id="task-3", description="Third", blocks=["task-2"]),
            ],
        )

        phase.compute_blocked_by()

        assert phase.subtasks[0].blocked_by == ["task-2"]  # task-1 blocks task-2
        assert phase.subtasks[1].blocked_by == ["task-3"]  # task-2 blocks task-3
        assert phase.subtasks[2].blocked_by == []  # task-3 blocks nothing

    def test_compute_blocked_by_diamond(self):
        """Computes blocked_by correctly for diamond pattern."""
        phase = Phase(
            phase=1,
            name="Test Phase",
            subtasks=[
                Subtask(id="root", description="Root"),
                Subtask(id="left", description="Left", blocks=["root"]),
                Subtask(id="right", description="Right", blocks=["root"]),
                Subtask(id="merge", description="Merge", blocks=["left", "right"]),
            ],
        )

        phase.compute_blocked_by()

        root = phase.subtasks[0]
        left = phase.subtasks[1]
        right = phase.subtasks[2]
        merge = phase.subtasks[3]

        # Root blocks both left and right
        assert set(root.blocked_by) == {"left", "right"}
        # Left and right block merge
        assert left.blocked_by == ["merge"]
        assert right.blocked_by == ["merge"]
        # Merge blocks nothing
        assert merge.blocked_by == []


class TestDependencyAnalyzerWithExplicitDeps:
    """Tests for DependencyAnalyzer with explicit subtask dependencies."""

    def test_analyzer_reads_explicit_blocks(self):
        """DependencyAnalyzer reads blocks field from subtasks."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test Phase",
                    "subtasks": [
                        {"id": "task-1", "description": "First", "blocks": []},
                        {
                            "id": "task-2",
                            "description": "Second",
                            "blocks": ["task-1"],
                        },
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)
        info = analyzer.get_subtask_dependencies("task-2")

        assert info is not None
        assert "task-1" in info.depends_on

    def test_analyzer_get_ready_subtasks_respects_deps(self):
        """get_ready_subtasks filters based on dependencies."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test Phase",
                    "subtasks": [
                        {"id": "task-1", "description": "No deps", "blocks": []},
                        {
                            "id": "task-2",
                            "description": "Depends on 1",
                            "blocks": ["task-1"],
                        },
                        {
                            "id": "task-3",
                            "description": "Depends on 2",
                            "blocks": ["task-2"],
                        },
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)

        # Nothing completed - only task-1 is ready
        ready = analyzer.get_ready_subtasks(
            ["task-1", "task-2", "task-3"], completed_ids=set()
        )
        assert ready == ["task-1"]

        # task-1 completed - task-2 is ready
        ready = analyzer.get_ready_subtasks(
            ["task-2", "task-3"], completed_ids={"task-1"}
        )
        assert ready == ["task-2"]

        # task-1 and task-2 completed - task-3 is ready
        ready = analyzer.get_ready_subtasks(
            ["task-3"], completed_ids={"task-1", "task-2"}
        )
        assert ready == ["task-3"]


class TestDependencyAnalyzerWaveGroups:
    """Tests for wave-based execution grouping."""

    def test_wave_groups_simple_chain(self):
        """Wave groups for simple chain: 1 -> 2 -> 3."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test",
                    "subtasks": [
                        {"id": "task-1", "blocks": []},
                        {"id": "task-2", "blocks": ["task-1"]},
                        {"id": "task-3", "blocks": ["task-2"]},
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)
        waves = analyzer.get_wave_groups(["task-1", "task-2", "task-3"])

        assert len(waves) == 3
        assert waves[0] == ["task-1"]
        assert waves[1] == ["task-2"]
        assert waves[2] == ["task-3"]

    def test_wave_groups_parallel_tasks(self):
        """Wave groups for parallel tasks: 1, 2 (no deps), then 3 depends on both."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test",
                    "subtasks": [
                        {"id": "task-1", "blocks": []},
                        {"id": "task-2", "blocks": []},
                        {"id": "task-3", "blocks": ["task-1", "task-2"]},
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)
        waves = analyzer.get_wave_groups(["task-1", "task-2", "task-3"])

        assert len(waves) == 2
        # Wave 0 contains both independent tasks (order may vary)
        assert set(waves[0]) == {"task-1", "task-2"}
        assert waves[1] == ["task-3"]

    def test_wave_groups_diamond_pattern(self):
        """Wave groups for diamond: root -> (left, right) -> merge."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test",
                    "subtasks": [
                        {"id": "root", "blocks": []},
                        {"id": "left", "blocks": ["root"]},
                        {"id": "right", "blocks": ["root"]},
                        {"id": "merge", "blocks": ["left", "right"]},
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)
        waves = analyzer.get_wave_groups(["root", "left", "right", "merge"])

        assert len(waves) == 3
        assert waves[0] == ["root"]
        assert set(waves[1]) == {"left", "right"}
        assert waves[2] == ["merge"]

    def test_wave_groups_circular_raises_error(self):
        """Wave groups raises error for circular dependencies."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test",
                    "subtasks": [
                        {"id": "task-a", "blocks": ["task-b"]},
                        {"id": "task-b", "blocks": ["task-a"]},
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)

        with pytest.raises(ValueError, match="Circular"):
            analyzer.get_wave_groups(["task-a", "task-b"])

    def test_get_subtask_wave_number(self):
        """get_subtask_wave returns correct wave number."""
        plan_data = {
            "phases": [
                {
                    "phase": 1,
                    "name": "Test",
                    "subtasks": [
                        {"id": "task-1", "blocks": []},
                        {"id": "task-2", "blocks": ["task-1"]},
                        {"id": "task-3", "blocks": ["task-2"]},
                    ],
                }
            ]
        }

        analyzer = DependencyAnalyzer(plan_data)

        assert analyzer.get_subtask_wave("task-1") == 0
        assert analyzer.get_subtask_wave("task-2") == 1
        assert analyzer.get_subtask_wave("task-3") == 2
        assert analyzer.get_subtask_wave("nonexistent") == -1


class TestImplementationPlanDependencyIntegration:
    """Tests for dependency handling in ImplementationPlan class."""

    def test_plan_loads_and_computes_blocked_by(self):
        """Plan loading computes blocked_by from blocks."""
        plan_data = {
            "feature": "Test Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Test Phase",
                    "subtasks": [
                        {"id": "task-1", "description": "First", "blocks": []},
                        {
                            "id": "task-2",
                            "description": "Second",
                            "blocks": ["task-1"],
                        },
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)

        # blocked_by should be computed
        assert plan.phases[0].subtasks[0].blocked_by == ["task-2"]
        assert plan.phases[0].subtasks[1].blocked_by == []

    def test_plan_get_next_subtask_respects_deps(self):
        """get_next_subtask respects subtask-level dependencies."""
        plan_data = {
            "feature": "Test Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Test Phase",
                    "subtasks": [
                        {
                            "id": "task-1",
                            "description": "First",
                            "status": "pending",
                            "blocks": [],
                        },
                        {
                            "id": "task-2",
                            "description": "Second",
                            "status": "pending",
                            "blocks": ["task-1"],
                        },
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)

        # First call should return task-1 (no deps)
        result = plan.get_next_subtask()
        assert result is not None
        phase, subtask = result
        assert subtask.id == "task-1"

        # Mark task-1 as completed
        plan.phases[0].subtasks[0].status = SubtaskStatus.COMPLETED

        # Now task-2 should be next
        result = plan.get_next_subtask()
        assert result is not None
        phase, subtask = result
        assert subtask.id == "task-2"

    def test_plan_get_next_subtask_skips_blocked(self):
        """get_next_subtask skips subtasks with unmet dependencies."""
        plan_data = {
            "feature": "Test Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Test Phase",
                    "subtasks": [
                        {
                            "id": "task-1",
                            "description": "First",
                            "status": "pending",
                            "blocks": [],
                        },
                        {
                            "id": "task-2",
                            "description": "Depends on 3",
                            "status": "pending",
                            "blocks": ["task-3"],
                        },
                        {
                            "id": "task-3",
                            "description": "Depends on 1",
                            "status": "pending",
                            "blocks": ["task-1"],
                        },
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)

        # Only task-1 should be ready
        result = plan.get_next_subtask()
        assert result is not None
        _, subtask = result
        assert subtask.id == "task-1"

    def test_plan_validate_all_dependencies(self):
        """Plan can validate dependencies across all phases."""
        plan_data = {
            "feature": "Test Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "subtasks": [
                        {"id": "task-1", "description": "Valid", "blocks": []},
                        {
                            "id": "task-2",
                            "description": "Valid dep",
                            "blocks": ["task-1"],
                        },
                    ],
                },
                {
                    "phase": 2,
                    "name": "Phase 2",
                    "depends_on": [1],
                    "subtasks": [
                        {"id": "task-3", "description": "Valid", "blocks": []},
                        {"id": "task-4", "description": "Invalid", "blocks": ["missing"]},
                    ],
                },
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)
        is_valid, errors = plan.validate_all_dependencies()

        assert is_valid is False
        assert len(errors) == 1
        assert "Phase 2" in errors[0]
        assert "missing" in errors[0]


class TestBackwardCompatibility:
    """Tests for backward compatibility with plans lacking dependency fields."""

    def test_legacy_plan_without_blocks_loads(self):
        """Legacy plan without blocks field loads successfully."""
        plan_data = {
            "feature": "Legacy Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "subtasks": [
                        {"id": "task-1", "description": "Legacy task 1"},
                        {"id": "task-2", "description": "Legacy task 2"},
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)

        assert len(plan.phases[0].subtasks) == 2
        assert plan.phases[0].subtasks[0].blocks == []
        assert plan.phases[0].subtasks[0].blocked_by == []

    def test_legacy_plan_get_next_subtask_works(self):
        """get_next_subtask works on legacy plans (no explicit deps)."""
        plan_data = {
            "feature": "Legacy Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "subtasks": [
                        {"id": "task-1", "description": "First", "status": "pending"},
                        {"id": "task-2", "description": "Second", "status": "pending"},
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)
        result = plan.get_next_subtask()

        # Should return first pending subtask
        assert result is not None
        _, subtask = result
        assert subtask.id == "task-1"

    def test_legacy_plan_validation_passes(self):
        """Validation passes on legacy plans (no deps to validate)."""
        plan_data = {
            "feature": "Legacy Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "subtasks": [
                        {"id": "task-1", "description": "Task 1"},
                        {"id": "task-2", "description": "Task 2"},
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)
        is_valid, errors = plan.validate_all_dependencies()

        assert is_valid is True
        assert errors == []

    def test_mixed_legacy_and_new_subtasks(self):
        """Plan with mix of legacy and new subtasks works correctly."""
        plan_data = {
            "feature": "Mixed Feature",
            "workflow_type": "feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "subtasks": [
                        # Legacy subtask (no blocks field)
                        {"id": "task-1", "description": "Legacy task"},
                        # New subtask with explicit dep
                        {
                            "id": "task-2",
                            "description": "New task",
                            "blocks": ["task-1"],
                        },
                    ],
                }
            ],
        }

        plan = ImplementationPlan.from_dict(plan_data)

        assert plan.phases[0].subtasks[0].blocks == []
        assert plan.phases[0].subtasks[1].blocks == ["task-1"]

        # blocked_by should be computed
        assert plan.phases[0].subtasks[0].blocked_by == ["task-2"]
