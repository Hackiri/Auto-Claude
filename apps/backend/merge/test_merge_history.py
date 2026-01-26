"""
Tests for Merge History Tracker
=================================

Comprehensive test suite for merge history tracking system covering:
- Merge entry persistence and retrieval
- Index management
- Sorting and filtering
- File path organization (YYYY-MM subdirectories)
- Error handling
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from merge.merge_history import MergeHistoryTracker
from merge.merge_history_models import MergeConflictRecord, MergeHistoryEntry


class TestMergeHistoryTracker:
    """Test merge history tracking functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def tracker(self, temp_storage):
        """Create a tracker instance with temp storage."""
        return MergeHistoryTracker(temp_storage)

    @pytest.fixture
    def sample_entry(self):
        """Create a sample merge entry for testing."""
        now = datetime.now()
        return MergeHistoryEntry(
            merge_id=f"test-task-{now.strftime('%Y%m%d-%H%M%S')}",
            task_id="test-task",
            spec_name="test-spec",
            started_at=now,
            completed_at=now,
            source_worktree=".auto-claude/worktrees/test-task",
            source_branch="auto-claude/test-task",
            target_branch="main",
            files_changed=["file1.py", "file2.py"],
            files_added=["file3.py"],
            files_deleted=["file4.py"],
            total_conflicts=2,
            auto_resolved_count=1,
            ai_resolved_count=1,
            pre_merge_commit="abc123",
            merge_commit="def456",
            success=True,
            ai_tokens_used=1000,
            duration_seconds=45.5,
        )

    def test_initialization(self, temp_storage):
        """Tracker initializes with correct directory structure."""
        tracker = MergeHistoryTracker(temp_storage)

        # Use resolve() on both sides since macOS resolves /var -> /private/var
        assert tracker.storage_path == temp_storage.resolve()
        assert tracker.history_dir == (temp_storage / "merge_history").resolve()
        assert tracker.index_file == (temp_storage / "merge_history" / "index.json").resolve()
        assert tracker.history_dir.exists()

    def test_record_merge_creates_file(self, tracker, sample_entry):
        """Recording a merge creates the JSON file."""
        tracker.record_merge(sample_entry)

        # File should exist in YYYY-MM subdirectory
        merge_file = tracker._get_merge_file_path(sample_entry.merge_id)
        assert merge_file.exists()

        # File should contain correct data
        with open(merge_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["merge_id"] == sample_entry.merge_id
        assert data["task_id"] == sample_entry.task_id
        assert data["files_changed"] == sample_entry.files_changed

    def test_record_merge_updates_index(self, tracker, sample_entry):
        """Recording a merge updates the index."""
        tracker.record_merge(sample_entry)

        # Index should contain the merge ID
        with open(tracker.index_file, encoding="utf-8") as f:
            index = json.load(f)

        assert sample_entry.merge_id in index["merges"]
        assert index["last_updated"] is not None

    def test_get_merge_returns_correct_entry(self, tracker, sample_entry):
        """get_merge retrieves the correct merge entry."""
        tracker.record_merge(sample_entry)

        retrieved = tracker.get_merge(sample_entry.merge_id)

        assert retrieved is not None
        assert retrieved.merge_id == sample_entry.merge_id
        assert retrieved.task_id == sample_entry.task_id
        assert retrieved.files_changed == sample_entry.files_changed
        assert retrieved.ai_tokens_used == sample_entry.ai_tokens_used

    def test_get_merge_returns_none_for_nonexistent(self, tracker):
        """get_merge returns None for non-existent merge."""
        result = tracker.get_merge("nonexistent-merge-id")
        assert result is None

    def test_get_all_merges_returns_sorted(self, tracker):
        """get_all_merges returns merges sorted by timestamp (newest first)."""
        # Create 3 merges with different timestamps
        now = datetime.now()

        entry1 = MergeHistoryEntry(
            merge_id="task1-20240101-120000",
            task_id="task1",
            spec_name="spec1",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 0, 0),
            merge_commit="abc1",
        )

        entry2 = MergeHistoryEntry(
            merge_id="task2-20240102-120000",
            task_id="task2",
            spec_name="spec2",
            started_at=datetime(2024, 1, 2, 12, 0, 0),
            completed_at=datetime(2024, 1, 2, 12, 0, 0),
            merge_commit="abc2",
        )

        entry3 = MergeHistoryEntry(
            merge_id="task3-20240103-120000",
            task_id="task3",
            spec_name="spec3",
            started_at=datetime(2024, 1, 3, 12, 0, 0),
            completed_at=datetime(2024, 1, 3, 12, 0, 0),
            merge_commit="abc3",
        )

        tracker.record_merge(entry1)
        tracker.record_merge(entry2)
        tracker.record_merge(entry3)

        all_merges = tracker.get_all_merges()

        assert len(all_merges) == 3
        assert all_merges[0].merge_id == "task3-20240103-120000"  # Newest first
        assert all_merges[1].merge_id == "task2-20240102-120000"
        assert all_merges[2].merge_id == "task1-20240101-120000"  # Oldest last

    def test_get_merges_for_task_filters_correctly(self, tracker):
        """get_merges_for_task returns only merges for the specified task."""
        # Create merges for different tasks
        entry1 = MergeHistoryEntry(
            merge_id="task1-20240101-120000",
            task_id="task1",
            spec_name="spec1",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            merge_commit="abc1",
        )

        entry2 = MergeHistoryEntry(
            merge_id="task1-20240102-120000",
            task_id="task1",
            spec_name="spec1",
            started_at=datetime(2024, 1, 2, 12, 0, 0),
            merge_commit="abc2",
        )

        entry3 = MergeHistoryEntry(
            merge_id="task2-20240103-120000",
            task_id="task2",
            spec_name="spec2",
            started_at=datetime(2024, 1, 3, 12, 0, 0),
            merge_commit="abc3",
        )

        tracker.record_merge(entry1)
        tracker.record_merge(entry2)
        tracker.record_merge(entry3)

        task1_merges = tracker.get_merges_for_task("task1")

        assert len(task1_merges) == 2
        assert all(m.task_id == "task1" for m in task1_merges)

    def test_merge_file_path_uses_subdirectories(self, tracker):
        """Merge files are stored in YYYY-MM subdirectories."""
        merge_id = "20240315-123456-task"
        path = tracker._get_merge_file_path(merge_id)

        assert "2024-03" in str(path)
        assert path.name == f"{merge_id}.json"

    def test_merge_file_path_fallback_for_short_ids(self, tracker):
        """Short merge IDs use fallback path without subdirectory."""
        merge_id = "short"
        path = tracker._get_merge_file_path(merge_id)

        assert path == tracker.history_dir / f"{merge_id}.json"

    def test_rollback_merge_success(self, tracker, sample_entry):
        """rollback_merge successfully reverts a merge."""
        tracker.record_merge(sample_entry)

        with patch("core.git_executable.run_git") as mock_run_git:
            # Mock successful git revert
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Reverted successfully"
            mock_result.stderr = ""
            mock_run_git.return_value = mock_result

            project_path = Path("/fake/project")
            result = tracker.rollback_merge(sample_entry.merge_id, project_path)

            assert result is True
            mock_run_git.assert_called_once_with(
                ["revert", "-m", "1", sample_entry.merge_commit],
                cwd=project_path,
                timeout=60,
            )

    def test_rollback_merge_fails_for_nonexistent(self, tracker):
        """rollback_merge fails for non-existent merge."""
        result = tracker.rollback_merge("nonexistent", Path("/fake/project"))
        assert result is False

    def test_rollback_merge_fails_for_missing_commit(self, tracker):
        """rollback_merge fails when merge has no commit hash."""
        entry = MergeHistoryEntry(
            merge_id="test-merge",
            task_id="test-task",
            spec_name="test-spec",
            started_at=datetime.now(),
            merge_commit="",  # Empty commit hash
        )
        tracker.record_merge(entry)

        result = tracker.rollback_merge("test-merge", Path("/fake/project"))
        assert result is False

    def test_rollback_merge_handles_git_error(self, tracker, sample_entry):
        """rollback_merge handles git command errors gracefully."""
        tracker.record_merge(sample_entry)

        with patch("core.git_executable.run_git") as mock_run_git:
            # Mock failed git revert
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "error: could not revert"
            mock_run_git.return_value = mock_result

            result = tracker.rollback_merge(sample_entry.merge_id, Path("/fake/project"))

            assert result is False

    def test_record_merge_with_conflicts(self, tracker):
        """Recording a merge with conflict records works correctly."""
        conflict = MergeConflictRecord(
            file_path="test.py",
            conflict_type="content",
            resolution_method="ai",
            base_content="base",
            task_content="task",
            main_content="main",
            resolved_content="resolved",
            ai_reasoning="AI decided to use task version",
            ai_tokens_used=500,
            resolved_at=datetime.now(),
        )

        entry = MergeHistoryEntry(
            merge_id="test-20240101-120000",
            task_id="test-task",
            spec_name="test-spec",
            started_at=datetime.now(),
            conflicts_resolved=[conflict],
            total_conflicts=1,
            ai_resolved_count=1,
            merge_commit="abc123",
        )

        tracker.record_merge(entry)
        retrieved = tracker.get_merge(entry.merge_id)

        assert retrieved is not None
        assert len(retrieved.conflicts_resolved) == 1
        assert retrieved.conflicts_resolved[0].file_path == "test.py"
        assert retrieved.conflicts_resolved[0].ai_reasoning == "AI decided to use task version"

    def test_index_not_duplicated(self, tracker, sample_entry):
        """Recording the same merge twice doesn't duplicate index entries."""
        tracker.record_merge(sample_entry)
        tracker.record_merge(sample_entry)  # Record again

        with open(tracker.index_file, encoding="utf-8") as f:
            index = json.load(f)

        # Should only appear once in index
        count = index["merges"].count(sample_entry.merge_id)
        assert count == 1

    def test_load_index_handles_missing_file(self, tracker):
        """_load_index returns default when index file doesn't exist."""
        # Delete index if it exists
        if tracker.index_file.exists():
            tracker.index_file.unlink()

        index = tracker._load_index()

        assert index == {"merges": [], "last_updated": None}

    def test_load_index_handles_corrupted_file(self, tracker):
        """_load_index returns default when index file is corrupted."""
        # Write invalid JSON
        tracker.index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tracker.index_file, "w") as f:
            f.write("invalid json {")

        index = tracker._load_index()

        assert index == {"merges": [], "last_updated": None}

    def test_record_merge_handles_write_error(self, tracker, sample_entry):
        """record_merge handles write errors gracefully."""
        # Make directory read-only to cause write error
        tracker.history_dir.chmod(0o444)

        try:
            # Should not raise exception
            tracker.record_merge(sample_entry)
        finally:
            # Restore permissions
            tracker.history_dir.chmod(0o755)

    def test_serialization_roundtrip(self, tracker, sample_entry):
        """Merge entry survives serialization/deserialization."""
        tracker.record_merge(sample_entry)
        retrieved = tracker.get_merge(sample_entry.merge_id)

        # All important fields should match
        assert retrieved.merge_id == sample_entry.merge_id
        assert retrieved.task_id == sample_entry.task_id
        assert retrieved.spec_name == sample_entry.spec_name
        assert retrieved.files_changed == sample_entry.files_changed
        assert retrieved.files_added == sample_entry.files_added
        assert retrieved.files_deleted == sample_entry.files_deleted
        assert retrieved.total_conflicts == sample_entry.total_conflicts
        assert retrieved.auto_resolved_count == sample_entry.auto_resolved_count
        assert retrieved.ai_resolved_count == sample_entry.ai_resolved_count
        assert retrieved.pre_merge_commit == sample_entry.pre_merge_commit
        assert retrieved.merge_commit == sample_entry.merge_commit
        assert retrieved.success == sample_entry.success
        assert retrieved.ai_tokens_used == sample_entry.ai_tokens_used
        assert retrieved.duration_seconds == sample_entry.duration_seconds


class TestMergeHistoryModels:
    """Test merge history data models."""

    def test_merge_conflict_record_to_dict(self):
        """MergeConflictRecord serializes correctly."""
        now = datetime.now()
        record = MergeConflictRecord(
            file_path="test.py",
            conflict_type="content",
            resolution_method="ai",
            ai_reasoning="Test reasoning",
            ai_tokens_used=100,
            resolved_at=now,
        )

        data = record.to_dict()

        assert data["file_path"] == "test.py"
        assert data["conflict_type"] == "content"
        assert data["resolution_method"] == "ai"
        assert data["ai_reasoning"] == "Test reasoning"
        assert data["ai_tokens_used"] == 100
        assert data["resolved_at"] == now.isoformat()

    def test_merge_conflict_record_from_dict(self):
        """MergeConflictRecord deserializes correctly."""
        now = datetime.now()
        data = {
            "file_path": "test.py",
            "conflict_type": "content",
            "resolution_method": "auto",
            "base_content": "base",
            "task_content": "task",
            "main_content": "main",
            "resolved_content": "resolved",
            "ai_reasoning": None,
            "ai_tokens_used": 0,
            "resolved_at": now.isoformat(),
        }

        record = MergeConflictRecord.from_dict(data)

        assert record.file_path == "test.py"
        assert record.conflict_type == "content"
        assert record.resolution_method == "auto"
        assert record.ai_tokens_used == 0

    def test_merge_history_entry_to_dict(self):
        """MergeHistoryEntry serializes correctly."""
        now = datetime.now()
        entry = MergeHistoryEntry(
            merge_id="test-merge",
            task_id="test-task",
            spec_name="test-spec",
            started_at=now,
            completed_at=now,
            files_changed=["file1.py"],
            merge_commit="abc123",
        )

        data = entry.to_dict()

        assert data["merge_id"] == "test-merge"
        assert data["task_id"] == "test-task"
        assert data["spec_name"] == "test-spec"
        assert data["files_changed"] == ["file1.py"]
        assert data["merge_commit"] == "abc123"

    def test_merge_history_entry_from_dict(self):
        """MergeHistoryEntry deserializes correctly."""
        now = datetime.now()
        data = {
            "merge_id": "test-merge",
            "task_id": "test-task",
            "spec_name": "test-spec",
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "source_worktree": ".auto-claude/worktrees/test",
            "source_branch": "auto-claude/test",
            "target_branch": "main",
            "files_changed": ["file1.py"],
            "files_added": [],
            "files_deleted": [],
            "conflicts_resolved": [],
            "total_conflicts": 0,
            "auto_resolved_count": 0,
            "ai_resolved_count": 0,
            "pre_merge_commit": "pre123",
            "merge_commit": "abc123",
            "success": True,
            "error_message": None,
            "ai_tokens_used": 500,
            "duration_seconds": 30.5,
        }

        entry = MergeHistoryEntry.from_dict(data)

        assert entry.merge_id == "test-merge"
        assert entry.task_id == "test-task"
        assert entry.merge_commit == "abc123"
        assert entry.ai_tokens_used == 500
        assert entry.duration_seconds == 30.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
