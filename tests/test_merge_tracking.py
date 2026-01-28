"""
Integration Tests for Merge Tracking
======================================

End-to-end tests for the complete merge tracking flow covering:
- Workspace merge completion recording
- Merge history persistence and retrieval
- CLI commands for listing and viewing merges
- Rollback functionality
- Integration between workspace.py, MergeHistoryTracker, and CLI
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add apps/backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from core.git_executable import run_git
from merge.merge_history import MergeHistoryTracker
from merge.merge_history_models import MergeHistoryEntry


class TestMergeTrackingIntegration:
    """Integration tests for merge tracking flow."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory with git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Initialize git repo with 'main' as default branch
            run_git(["init", "-b", "main"], cwd=project_dir)
            run_git(["config", "user.name", "Test User"], cwd=project_dir)
            run_git(["config", "user.email", "test@example.com"], cwd=project_dir)
            # Disable GPG signing for test commits
            run_git(["config", "commit.gpgsign", "false"], cwd=project_dir)

            # Create initial commit
            test_file = project_dir / "test.txt"
            test_file.write_text("initial content")
            run_git(["add", "."], cwd=project_dir)
            run_git(["commit", "-m", "Initial commit"], cwd=project_dir)

            # Create .auto-claude directory
            auto_claude_dir = project_dir / ".auto-claude"
            auto_claude_dir.mkdir()

            yield project_dir

    @pytest.fixture
    def tracker(self, temp_project):
        """Create a tracker instance for temp project."""
        return MergeHistoryTracker(temp_project / ".auto-claude")

    def test_end_to_end_merge_recording(self, temp_project, tracker):
        """
        Test complete flow: Create merge entry, record it, retrieve it.

        This simulates what happens when workspace.py calls _record_merge_completion.
        """
        # Simulate a merge completion
        now = datetime.now()
        spec_name = "test-feature"

        # Get current commit (simulating merge commit)
        result = run_git(["rev-parse", "HEAD"], cwd=temp_project)
        merge_commit = result.stdout.strip()

        # Create merge entry like workspace.py does
        entry = MergeHistoryEntry(
            merge_id=f"{spec_name}-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id=spec_name,
            spec_name=spec_name,
            started_at=now,
            completed_at=now,
            source_worktree=f".auto-claude/worktrees/{spec_name}",
            source_branch=f"auto-claude/{spec_name}",
            target_branch="main",
            files_changed=["test.txt"],
            files_added=[],
            files_deleted=[],
            total_conflicts=0,
            auto_resolved_count=0,
            ai_resolved_count=0,
            pre_merge_commit="",
            merge_commit=merge_commit,
            success=True,
            ai_tokens_used=0,
            duration_seconds=10.5,
        )

        # Record the merge
        tracker.record_merge(entry)

        # Verify it was persisted
        history_dir = temp_project / ".auto-claude" / "merge_history"
        assert history_dir.exists()

        # Verify we can retrieve it
        retrieved = tracker.get_merge(entry.merge_id)
        assert retrieved is not None
        assert retrieved.merge_id == entry.merge_id
        assert retrieved.task_id == spec_name
        assert retrieved.merge_commit == merge_commit

        # Verify it appears in get_all_merges
        all_merges = tracker.get_all_merges()
        assert len(all_merges) == 1
        assert all_merges[0].merge_id == entry.merge_id

    def test_multiple_merges_for_same_task(self, tracker):
        """Test recording multiple merges for the same task."""
        task_id = "feature-001"

        # Create 3 merges for the same task
        for i in range(3):
            now = datetime.now()
            entry = MergeHistoryEntry(
                merge_id=f"{task_id}-{now.strftime('%Y%m%d-%H%M%S')}-{i}",
                task_id=task_id,
                spec_name=task_id,
                started_at=now,
                merge_commit=f"commit{i}",
            )
            tracker.record_merge(entry)

        # Verify all 3 are recorded
        task_merges = tracker.get_merges_for_task(task_id)
        assert len(task_merges) == 3

    def test_merge_history_cli_integration(self, temp_project, tracker):
        """
        Test that CLI can read merge history recorded by workspace.py.

        This verifies the integration between MergeHistoryTracker and CLI.
        """
        # Record a merge
        now = datetime.now()
        entry = MergeHistoryEntry(
            merge_id=f"cli-test-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id="cli-test",
            spec_name="cli-test",
            started_at=now,
            completed_at=now,
            merge_commit="abc123",
            files_changed=["file1.py", "file2.py"],
        )
        tracker.record_merge(entry)

        # Verify CLI can read it by checking the file directly
        # (We're not actually calling the CLI executable, just verifying the data format)
        merge_file = tracker._get_merge_file_path(entry.merge_id)
        assert merge_file.exists()

        with open(merge_file, encoding="utf-8") as f:
            data = json.load(f)

        # Verify data is in the format CLI expects
        assert "merge_id" in data
        assert "task_id" in data
        assert "merge_commit" in data
        assert "files_changed" in data
        assert data["merge_id"] == entry.merge_id

    def test_rollback_integration(self, temp_project):
        """
        Test rollback functionality with a real git repository.

        This tests the integration between MergeHistoryTracker and git operations.
        """
        # Create tracker with the temp project's .auto-claude directory
        tracker = MergeHistoryTracker(temp_project / ".auto-claude")

        # Create a new branch and commit
        result = run_git(["checkout", "-b", "feature"], cwd=temp_project)
        assert result.returncode == 0, f"checkout failed: {result.stderr}"

        feature_file = temp_project / "feature.txt"
        feature_file.write_text("feature content")

        result = run_git(["add", "."], cwd=temp_project)
        assert result.returncode == 0, f"add failed: {result.stderr}"

        result = run_git(["commit", "-m", "Add feature"], cwd=temp_project)
        assert result.returncode == 0, f"commit failed: {result.stderr}"

        # Merge back to main
        result = run_git(["checkout", "main"], cwd=temp_project)
        assert result.returncode == 0, f"checkout main failed: {result.stderr}"

        result = run_git(["merge", "feature", "--no-ff", "-m", "Merge feature"], cwd=temp_project)
        assert result.returncode == 0, f"merge failed: {result.stderr}"

        # Get the merge commit
        result = run_git(["rev-parse", "HEAD"], cwd=temp_project)
        assert result.returncode == 0, f"rev-parse failed: {result.stderr}"
        merge_commit = result.stdout.strip()

        # Verify we have a valid commit hash
        assert len(merge_commit) == 40, f"Invalid merge commit hash: '{merge_commit}', stderr: {result.stderr}"

        # Record the merge
        now = datetime.now()
        entry = MergeHistoryEntry(
            merge_id=f"rollback-test-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id="rollback-test",
            spec_name="rollback-test",
            started_at=now,
            merge_commit=merge_commit,
            files_changed=["feature.txt"],
        )
        tracker.record_merge(entry)

        # Verify the merge was recorded with correct commit hash
        retrieved = tracker.get_merge(entry.merge_id)
        assert retrieved is not None
        assert retrieved.merge_commit == merge_commit

        # Verify feature.txt exists
        assert feature_file.exists()

        # Perform rollback using the resolved temp_project path
        success = tracker.rollback_merge(entry.merge_id, temp_project.resolve())
        assert success is True, f"Rollback failed for merge commit {merge_commit}"

        # Verify rollback created a revert commit
        log_result = run_git(["log", "--oneline", "-1"], cwd=temp_project)
        assert "Revert" in log_result.stdout

    def test_workspace_record_merge_completion_integration(self, temp_project):
        """
        Test _record_merge_completion function from workspace.py.

        This verifies the actual integration point between workspace.py and MergeHistoryTracker.
        """
        # Import the actual function
        sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))
        from core.workspace import _record_merge_completion

        # Create test scenario
        spec_name = "integration-test"
        resolved_files = ["file1.py", "file2.py"]

        # Call the function
        _record_merge_completion(temp_project, spec_name, resolved_files)

        # Verify merge was recorded
        tracker = MergeHistoryTracker(temp_project / ".auto-claude")
        merges = tracker.get_merges_for_task(spec_name)

        # Should have at least one merge recorded
        assert len(merges) >= 1

        # Verify the merge has the correct data
        latest_merge = merges[0]
        assert latest_merge.task_id == spec_name
        assert latest_merge.spec_name == spec_name
        assert latest_merge.files_changed == resolved_files
        assert latest_merge.success is True

    def test_concurrent_merge_recording(self, tracker):
        """Test that concurrent merge recordings don't corrupt the index."""
        import threading

        def record_merge(task_id):
            now = datetime.now()
            entry = MergeHistoryEntry(
                merge_id=f"{task_id}-{now.strftime('%Y%m%d-%H%M%S%f')}",
                task_id=task_id,
                spec_name=task_id,
                started_at=now,
                merge_commit=f"commit-{task_id}",
            )
            tracker.record_merge(entry)

        # Record 10 merges concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=record_merge, args=(f"task-{i}",))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all 10 merges were recorded
        all_merges = tracker.get_all_merges()
        assert len(all_merges) == 10

        # Verify index has all 10
        with open(tracker.index_file, encoding="utf-8") as f:
            index = json.load(f)
        assert len(index["merges"]) == 10

    def test_merge_history_persistence_across_tracker_instances(self, temp_project):
        """Test that merge history persists when creating new tracker instances."""
        # Create first tracker and record merge
        tracker1 = MergeHistoryTracker(temp_project / ".auto-claude")

        now = datetime.now()
        entry = MergeHistoryEntry(
            merge_id=f"persistence-test-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id="persistence-test",
            spec_name="persistence-test",
            started_at=now,
            merge_commit="abc123",
        )
        tracker1.record_merge(entry)

        # Create new tracker instance
        tracker2 = MergeHistoryTracker(temp_project / ".auto-claude")

        # Should be able to retrieve the merge
        retrieved = tracker2.get_merge(entry.merge_id)
        assert retrieved is not None
        assert retrieved.merge_id == entry.merge_id

    def test_large_merge_history(self, tracker):
        """Test performance with many merge entries."""
        # Record 100 merges
        for i in range(100):
            now = datetime.now()
            entry = MergeHistoryEntry(
                merge_id=f"task-{i:03d}-{now.strftime('%Y%m%d-%H%M%S%f')}",
                task_id=f"task-{i}",
                spec_name=f"spec-{i}",
                started_at=now,
                merge_commit=f"commit{i}",
            )
            tracker.record_merge(entry)

        # Should be able to retrieve all
        all_merges = tracker.get_all_merges()
        assert len(all_merges) == 100

        # Should be sorted by timestamp
        for i in range(len(all_merges) - 1):
            assert all_merges[i].started_at >= all_merges[i + 1].started_at

    def test_merge_with_full_conflict_details(self, tracker):
        """Test recording and retrieving merges with complete conflict information."""
        from merge.merge_history_models import MergeConflictRecord

        # Create merge with conflicts
        conflict1 = MergeConflictRecord(
            file_path="src/module.py",
            conflict_type="content",
            resolution_method="ai",
            base_content="base version",
            task_content="task version",
            main_content="main version",
            resolved_content="merged version",
            ai_reasoning="Chose task version because it's newer",
            ai_tokens_used=500,
            resolved_at=datetime.now(),
        )

        conflict2 = MergeConflictRecord(
            file_path="src/utils.py",
            conflict_type="semantic",
            resolution_method="auto",
            resolved_at=datetime.now(),
        )

        now = datetime.now()
        entry = MergeHistoryEntry(
            merge_id=f"conflicts-test-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id="conflicts-test",
            spec_name="conflicts-test",
            started_at=now,
            conflicts_resolved=[conflict1, conflict2],
            total_conflicts=2,
            auto_resolved_count=1,
            ai_resolved_count=1,
            ai_tokens_used=500,
            merge_commit="abc123",
        )

        tracker.record_merge(entry)

        # Retrieve and verify conflicts
        retrieved = tracker.get_merge(entry.merge_id)
        assert len(retrieved.conflicts_resolved) == 2
        assert retrieved.total_conflicts == 2
        assert retrieved.auto_resolved_count == 1
        assert retrieved.ai_resolved_count == 1

        # Verify first conflict details
        c1 = retrieved.conflicts_resolved[0]
        assert c1.file_path == "src/module.py"
        assert c1.resolution_method == "ai"
        assert c1.ai_reasoning == "Chose task version because it's newer"
        assert c1.ai_tokens_used == 500

    def test_failed_merge_recording(self, tracker):
        """Test recording a failed merge."""
        now = datetime.now()
        entry = MergeHistoryEntry(
            merge_id=f"failed-merge-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id="failed-merge",
            spec_name="failed-merge",
            started_at=now,
            completed_at=None,  # Not completed
            success=False,
            error_message="Merge conflicts could not be resolved automatically",
            merge_commit="",  # No commit for failed merge
        )

        tracker.record_merge(entry)

        retrieved = tracker.get_merge(entry.merge_id)
        assert retrieved is not None
        assert retrieved.success is False
        assert retrieved.error_message == "Merge conflicts could not be resolved automatically"
        assert retrieved.completed_at is None


class TestMergeHistoryCLIIntegration:
    """Integration tests for merge history CLI commands."""

    @pytest.fixture
    def temp_project_with_history(self):
        """Create a temp project with some merge history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            auto_claude_dir = project_dir / ".auto-claude"
            auto_claude_dir.mkdir()

            tracker = MergeHistoryTracker(auto_claude_dir)

            # Record some merges
            for i in range(3):
                now = datetime.now()
                entry = MergeHistoryEntry(
                    merge_id=f"task-{i}-{now.strftime('%Y%m%d-%H%M%S')}",
                    task_id=f"task-{i}",
                    spec_name=f"spec-{i}",
                    started_at=now,
                    merge_commit=f"commit{i}",
                    files_changed=[f"file{i}.py"],
                )
                tracker.record_merge(entry)

            yield project_dir, tracker

    def test_cli_can_list_merges(self, temp_project_with_history):
        """Test that merge history is accessible in CLI format."""
        project_dir, tracker = temp_project_with_history

        # Verify merges are in the expected location and format
        all_merges = tracker.get_all_merges()
        assert len(all_merges) == 3

        # Verify each merge has the data CLI needs
        for merge in all_merges:
            assert merge.merge_id is not None
            assert merge.task_id is not None
            assert merge.started_at is not None
            assert merge.files_changed is not None

    def test_json_wrapper_compatibility(self, temp_project_with_history):
        """Test that merge data is compatible with merge_history_json.py wrapper."""
        project_dir, tracker = temp_project_with_history

        # Get a merge
        all_merges = tracker.get_all_merges()
        merge = all_merges[0]

        # Verify it serializes to JSON correctly (as CLI expects)
        merge_dict = merge.to_dict()
        json_str = json.dumps(merge_dict)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["merge_id"] == merge.merge_id
        assert parsed["task_id"] == merge.task_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
