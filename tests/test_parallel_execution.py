"""
Tests for parallel sub-agent execution module.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from agents.parallel.subagent import SubagentConfig, SubagentResult, SubagentStatus
from agents.parallel.dependency import DependencyAnalyzer, can_run_in_parallel
from agents.parallel.aggregator import ParallelResults, aggregate_results, detect_file_conflicts


class TestSubagentConfig:
    """Tests for SubagentConfig class."""

    def test_from_subtask_basic(self):
        """Test creating config from a basic subtask."""
        subtask = {
            "id": "subtask-1",
            "description": "Create user model",
            "files_to_modify": ["models/user.py"],
            "files_to_create": ["models/profile.py"],
            "service": "backend",
        }

        config = SubagentConfig.from_subtask(subtask)

        assert config.subtask_id == "subtask-1"
        assert config.subtask_description == "Create user model"
        assert config.files_to_modify == ["models/user.py"]
        assert config.files_to_create == ["models/profile.py"]
        assert config.service == "backend"

    def test_from_subtask_with_phase(self):
        """Test creating config with phase context."""
        subtask = {
            "id": "subtask-2",
            "description": "Add API endpoint",
        }
        phase = {
            "name": "Backend API",
            "phase": 1,
        }

        config = SubagentConfig.from_subtask(subtask, phase)

        assert config.phase_name == "Backend API"
        assert config.phase_number == 1

    def test_to_dict(self):
        """Test serialization to dictionary."""
        config = SubagentConfig(
            subtask_id="test-1",
            subtask_description="Test task",
            files_to_modify=["file.py"],
            service="backend",
        )

        result = config.to_dict()

        assert result["subtask_id"] == "test-1"
        assert result["subtask_description"] == "Test task"
        assert result["files_to_modify"] == ["file.py"]
        assert result["service"] == "backend"


class TestSubagentResult:
    """Tests for SubagentResult class."""

    def test_mark_running(self):
        """Test marking result as running."""
        config = SubagentConfig(
            subtask_id="test-1",
            subtask_description="Test",
        )
        result = SubagentResult(subtask_id="test-1", config=config)

        result.mark_running()

        assert result.status == SubagentStatus.RUNNING
        assert result.started_at is not None

    def test_mark_completed_success(self):
        """Test marking result as completed successfully."""
        config = SubagentConfig(
            subtask_id="test-1",
            subtask_description="Test",
        )
        result = SubagentResult(subtask_id="test-1", config=config)
        result.mark_running()

        result.mark_completed(success=True, response="Done")

        assert result.status == SubagentStatus.COMPLETED
        assert result.success is True
        assert result.response_text == "Done"
        assert result.completed_at is not None

    def test_mark_failed(self):
        """Test marking result as failed."""
        config = SubagentConfig(
            subtask_id="test-1",
            subtask_description="Test",
        )
        result = SubagentResult(subtask_id="test-1", config=config)

        result.mark_failed("Something went wrong")

        assert result.status == SubagentStatus.FAILED
        assert result.success is False
        assert result.error_message == "Something went wrong"

    def test_duration_seconds(self):
        """Test duration calculation."""
        config = SubagentConfig(
            subtask_id="test-1",
            subtask_description="Test",
        )
        result = SubagentResult(subtask_id="test-1", config=config)

        result.mark_running()
        # Simulate some time passing
        result.started_at = datetime(2024, 1, 1, 12, 0, 0)
        result.mark_completed(success=True)
        result.completed_at = datetime(2024, 1, 1, 12, 0, 30)

        assert result.duration_seconds() == 30.0


class TestDependencyAnalyzer:
    """Tests for DependencyAnalyzer class."""

    @pytest.fixture
    def sample_plan(self):
        """Sample implementation plan for testing."""
        return {
            "feature": "Test Feature",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "parallel_safe": True,
                    "depends_on": [],
                    "subtasks": [
                        {
                            "id": "1-1",
                            "description": "Create model A",
                            "files_to_create": ["models/a.py"],
                            "status": "pending",
                        },
                        {
                            "id": "1-2",
                            "description": "Create model B",
                            "files_to_create": ["models/b.py"],
                            "status": "pending",
                        },
                        {
                            "id": "1-3",
                            "description": "Create model C",
                            "files_to_modify": ["models/a.py"],  # Conflicts with 1-1
                            "status": "pending",
                        },
                    ],
                },
                {
                    "phase": 2,
                    "name": "Phase 2",
                    "parallel_safe": False,
                    "depends_on": [1],
                    "subtasks": [
                        {
                            "id": "2-1",
                            "description": "Integration",
                            "files_to_modify": ["main.py"],
                            "status": "pending",
                        },
                    ],
                },
            ],
        }

    def test_can_run_parallel_no_conflicts(self, sample_plan):
        """Test that subtasks with different files can run in parallel."""
        analyzer = DependencyAnalyzer(sample_plan)

        can_parallel, reason = analyzer.can_run_parallel("1-1", "1-2")

        assert can_parallel is True
        assert "No conflicts" in reason

    def test_cannot_run_parallel_file_conflict(self, sample_plan):
        """Test that subtasks with file conflicts cannot run in parallel."""
        analyzer = DependencyAnalyzer(sample_plan)

        can_parallel, reason = analyzer.can_run_parallel("1-1", "1-3")

        assert can_parallel is False
        assert "overlap" in reason.lower()

    def test_cannot_run_parallel_dependency(self, sample_plan):
        """Test that subtasks with dependencies cannot run in parallel."""
        analyzer = DependencyAnalyzer(sample_plan)

        # Subtask 2-1 depends on all phase 1 subtasks
        can_parallel, reason = analyzer.can_run_parallel("1-1", "2-1")

        assert can_parallel is False

    def test_get_parallel_groups(self, sample_plan):
        """Test grouping subtasks for parallel execution."""
        analyzer = DependencyAnalyzer(sample_plan)

        groups = analyzer.get_parallel_groups(["1-1", "1-2", "1-3"])

        # Should have at least 2 groups since 1-1 and 1-3 conflict
        assert len(groups) >= 2
        # 1-1 and 1-2 should be in the same group
        for group in groups:
            if "1-1" in group and "1-3" in group:
                pytest.fail("1-1 and 1-3 should not be in the same group")

    def test_get_ready_subtasks(self, sample_plan):
        """Test finding subtasks ready to run."""
        analyzer = DependencyAnalyzer(sample_plan)

        # Initially, only phase 1 subtasks are ready
        ready = analyzer.get_ready_subtasks(["1-1", "1-2", "2-1"], completed_ids=set())

        assert "1-1" in ready
        assert "1-2" in ready
        assert "2-1" not in ready  # Depends on phase 1

    def test_get_ready_subtasks_after_completion(self, sample_plan):
        """Test finding subtasks after some are complete."""
        analyzer = DependencyAnalyzer(sample_plan)

        # After phase 1 is complete, phase 2 should be ready
        ready = analyzer.get_ready_subtasks(
            ["2-1"],
            completed_ids={"1-1", "1-2", "1-3"},
        )

        assert "2-1" in ready


class TestCanRunInParallel:
    """Tests for the can_run_in_parallel helper function."""

    def test_no_parallelism_single_subtask(self):
        """Test with only one subtask."""
        plan = {
            "phases": [
                {
                    "phase": 1,
                    "subtasks": [{"id": "1-1", "files_to_create": ["a.py"]}],
                }
            ]
        }

        can_parallel, groups = can_run_in_parallel(plan, ["1-1"])

        assert can_parallel is False

    def test_parallelism_possible(self):
        """Test when parallelism is possible."""
        plan = {
            "phases": [
                {
                    "phase": 1,
                    "parallel_safe": True,
                    "subtasks": [
                        {"id": "1-1", "files_to_create": ["a.py"]},
                        {"id": "1-2", "files_to_create": ["b.py"]},
                    ],
                }
            ]
        }

        can_parallel, groups = can_run_in_parallel(plan, ["1-1", "1-2"])

        assert can_parallel is True
        assert len(groups) >= 1
        # Both should be in the same group
        assert len(groups[0]) == 2


class TestParallelResults:
    """Tests for ParallelResults class."""

    def test_add_result_success(self):
        """Test adding a successful result."""
        results = ParallelResults(
            batch_id="test-batch",
            started_at=datetime.now(),
        )
        config = SubagentConfig(subtask_id="1-1", subtask_description="Test")
        result = SubagentResult(subtask_id="1-1", config=config)
        result.mark_completed(success=True)
        result.commits_made = 2
        result.files_changed = ["a.py", "b.py"]

        results.add_result(result)

        assert results.total_subtasks == 1
        assert results.completed_count == 1
        assert results.failed_count == 0
        assert results.commits_made_total == 2
        assert "a.py" in results.files_changed_all

    def test_add_result_failure(self):
        """Test adding a failed result."""
        results = ParallelResults(
            batch_id="test-batch",
            started_at=datetime.now(),
        )
        config = SubagentConfig(subtask_id="1-1", subtask_description="Test")
        result = SubagentResult(subtask_id="1-1", config=config)
        result.mark_failed("Error")

        results.add_result(result)

        assert results.total_subtasks == 1
        assert results.completed_count == 0
        assert results.failed_count == 1

    def test_detect_file_conflicts(self):
        """Test file conflict detection."""
        results = ParallelResults(
            batch_id="test-batch",
            started_at=datetime.now(),
        )

        # First result
        config1 = SubagentConfig(subtask_id="1-1", subtask_description="Test 1")
        result1 = SubagentResult(subtask_id="1-1", config=config1)
        result1.mark_completed(success=True)
        result1.files_changed = ["shared.py", "a.py"]
        results.add_result(result1)

        # Second result with overlapping file
        config2 = SubagentConfig(subtask_id="1-2", subtask_description="Test 2")
        result2 = SubagentResult(subtask_id="1-2", config=config2)
        result2.mark_completed(success=True)
        result2.files_changed = ["shared.py", "b.py"]
        results.add_result(result2)

        assert results.has_conflicts is True
        assert "shared.py" in results.conflict_files

    def test_finalize(self):
        """Test finalization of results."""
        results = ParallelResults(
            batch_id="test-batch",
            started_at=datetime.now(),
        )
        config = SubagentConfig(subtask_id="1-1", subtask_description="Test")
        result = SubagentResult(subtask_id="1-1", config=config)
        result.mark_completed(success=True)
        results.add_result(result)

        results.finalize()

        assert results.all_successful is True
        assert results.completed_at is not None

    def test_get_failed_subtasks(self):
        """Test getting list of failed subtasks."""
        results = ParallelResults(
            batch_id="test-batch",
            started_at=datetime.now(),
        )

        # Add successful result
        config1 = SubagentConfig(subtask_id="1-1", subtask_description="Test 1")
        result1 = SubagentResult(subtask_id="1-1", config=config1)
        result1.mark_completed(success=True)
        results.add_result(result1)

        # Add failed result
        config2 = SubagentConfig(subtask_id="1-2", subtask_description="Test 2")
        result2 = SubagentResult(subtask_id="1-2", config=config2)
        result2.mark_failed("Error")
        results.add_result(result2)

        failed = results.get_failed_subtasks()

        assert len(failed) == 1
        assert "1-2" in failed


class TestAggregateResults:
    """Tests for the aggregate_results helper function."""

    def test_aggregate_empty(self):
        """Test aggregating empty results."""
        started = datetime.now()

        aggregated = aggregate_results("batch-1", [], started)

        assert aggregated.total_subtasks == 0
        assert aggregated.all_successful is True  # No failures

    def test_aggregate_multiple(self):
        """Test aggregating multiple results."""
        started = datetime.now()

        config1 = SubagentConfig(subtask_id="1-1", subtask_description="Test 1")
        result1 = SubagentResult(subtask_id="1-1", config=config1)
        result1.mark_completed(success=True)
        result1.commits_made = 1

        config2 = SubagentConfig(subtask_id="1-2", subtask_description="Test 2")
        result2 = SubagentResult(subtask_id="1-2", config=config2)
        result2.mark_completed(success=True)
        result2.commits_made = 2

        aggregated = aggregate_results("batch-1", [result1, result2], started)

        assert aggregated.total_subtasks == 2
        assert aggregated.completed_count == 2
        assert aggregated.commits_made_total == 3
        assert aggregated.all_successful is True


class TestDetectFileConflicts:
    """Tests for the detect_file_conflicts helper function."""

    def test_no_conflicts(self):
        """Test when there are no conflicts."""
        config1 = SubagentConfig(subtask_id="1-1", subtask_description="Test 1")
        result1 = SubagentResult(subtask_id="1-1", config=config1)
        result1.files_changed = ["a.py"]

        config2 = SubagentConfig(subtask_id="1-2", subtask_description="Test 2")
        result2 = SubagentResult(subtask_id="1-2", config=config2)
        result2.files_changed = ["b.py"]

        has_conflicts, conflict_map = detect_file_conflicts([result1, result2])

        assert has_conflicts is False
        assert len(conflict_map) == 0

    def test_with_conflicts(self):
        """Test when there are conflicts."""
        config1 = SubagentConfig(subtask_id="1-1", subtask_description="Test 1")
        result1 = SubagentResult(subtask_id="1-1", config=config1)
        result1.files_changed = ["shared.py", "a.py"]

        config2 = SubagentConfig(subtask_id="1-2", subtask_description="Test 2")
        result2 = SubagentResult(subtask_id="1-2", config=config2)
        result2.files_changed = ["shared.py", "b.py"]

        has_conflicts, conflict_map = detect_file_conflicts([result1, result2])

        assert has_conflicts is True
        assert "shared.py" in conflict_map
        assert "1-1" in conflict_map["shared.py"]
        assert "1-2" in conflict_map["shared.py"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
