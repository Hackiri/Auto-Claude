"""
Merge History Tracker
======================

Service for persisting merge completion records to disk.

This module handles:
- Recording merge completions with full details
- Loading merge history from storage
- Providing merge records for UI display
- Supporting rollback operations via git
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .merge_history_models import MergeHistoryEntry

logger = logging.getLogger(__name__)

# Import debug utilities
try:
    from debug import debug, debug_success, debug_warning
except ImportError:

    def debug(*args, **kwargs):
        pass

    def debug_success(*args, **kwargs):
        pass

    def debug_warning(*args, **kwargs):
        pass


MODULE = "merge.merge_history"


class MergeHistoryTracker:
    """
    Central service for tracking and persisting merge completion history.

    This provides the audit trail of all merges, enabling:
    - Complete history viewing in UI
    - Rollback capability
    - Conflict resolution audit
    """

    def __init__(self, storage_path: Path):
        """
        Initialize the merge history tracker.

        Args:
            storage_path: Root directory for storage (e.g., .auto-claude/)
        """
        debug(MODULE, "Initializing MergeHistoryTracker", storage_path=str(storage_path))

        self.storage_path = Path(storage_path).resolve()
        self.history_dir = self.storage_path / "merge_history"

        # Ensure storage directory exists
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Index file for quick lookups
        self.index_file = self.history_dir / "index.json"

        debug_success(MODULE, "MergeHistoryTracker initialized")

    def record_merge(self, entry: MergeHistoryEntry) -> None:
        """
        Record a merge completion to persistent storage.

        Args:
            entry: The merge history entry to record
        """
        debug(
            MODULE,
            f"Recording merge: {entry.merge_id}",
            task_id=entry.task_id,
            files_changed=len(entry.files_changed),
        )

        try:
            # Save individual merge record
            merge_file = self._get_merge_file_path(entry.merge_id)
            merge_file.parent.mkdir(parents=True, exist_ok=True)

            with open(merge_file, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, indent=2)

            # Update index
            self._update_index(entry)

            debug_success(MODULE, f"Merge {entry.merge_id} recorded successfully")

        except Exception as e:
            logger.error(f"Failed to record merge {entry.merge_id}: {e}")
            debug_warning(MODULE, f"Failed to record merge: {e}")

    def get_merge(self, merge_id: str) -> MergeHistoryEntry | None:
        """
        Retrieve a specific merge record by ID.

        Args:
            merge_id: Unique identifier for the merge

        Returns:
            The merge history entry, or None if not found
        """
        from .merge_history_models import MergeHistoryEntry

        merge_file = self._get_merge_file_path(merge_id)

        if not merge_file.exists():
            return None

        try:
            with open(merge_file, encoding="utf-8") as f:
                data = json.load(f)
            return MergeHistoryEntry.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load merge {merge_id}: {e}")
            return None

    def get_all_merges(self) -> list[MergeHistoryEntry]:
        """
        Retrieve all merge records, sorted by timestamp (newest first).

        Returns:
            List of merge history entries
        """
        from .merge_history_models import MergeHistoryEntry

        merges = []
        index = self._load_index()

        for merge_id in index.get("merges", []):
            merge = self.get_merge(merge_id)
            if merge:
                merges.append(merge)

        # Sort by started_at timestamp, newest first
        merges.sort(key=lambda m: m.started_at, reverse=True)

        return merges

    def get_merges_for_task(self, task_id: str) -> list[MergeHistoryEntry]:
        """
        Retrieve all merge records for a specific task.

        Args:
            task_id: The task identifier

        Returns:
            List of merge history entries for this task
        """
        all_merges = self.get_all_merges()
        return [m for m in all_merges if m.task_id == task_id]

    def rollback_merge(self, merge_id: str, project_path: Path) -> bool:
        """
        Rollback a merge to its pre-merge state using git revert.

        Args:
            merge_id: The merge to rollback
            project_path: Path to the git repository

        Returns:
            True if rollback succeeded, False otherwise
        """
        debug(MODULE, f"Rolling back merge: {merge_id}")

        merge = self.get_merge(merge_id)
        if not merge:
            logger.error(f"Merge {merge_id} not found for rollback")
            return False

        if not merge.merge_commit:
            logger.error(f"Merge {merge_id} has no merge_commit hash for rollback")
            return False

        try:
            import subprocess

            # Use git revert to create a new commit that undoes the merge
            result = subprocess.run(
                ["git", "revert", "-m", "1", merge.merge_commit],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=True,
            )

            debug_success(MODULE, f"Merge {merge_id} rolled back successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to rollback merge {merge_id}: {e.stderr}")
            debug_warning(MODULE, f"Rollback failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during rollback of {merge_id}: {e}")
            return False

    def _get_merge_file_path(self, merge_id: str) -> Path:
        """
        Get the storage path for a merge record.

        Args:
            merge_id: The merge identifier

        Returns:
            Path to the merge JSON file
        """
        # Store merges in YYYY-MM subdirectories for organization
        # merge_id format: YYYYMMDD-HHMMSS-taskid
        if len(merge_id) >= 6:
            year_month = f"{merge_id[:4]}-{merge_id[4:6]}"
            return self.history_dir / year_month / f"{merge_id}.json"
        else:
            # Fallback for non-standard merge IDs
            return self.history_dir / f"{merge_id}.json"

    def _load_index(self) -> dict:
        """
        Load the merge index from disk.

        Returns:
            Index dictionary with merge metadata
        """
        if not self.index_file.exists():
            return {"merges": [], "last_updated": None}

        try:
            with open(self.index_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load merge index: {e}")
            return {"merges": [], "last_updated": None}

    def _update_index(self, entry: MergeHistoryEntry) -> None:
        """
        Update the merge index with a new entry.

        Args:
            entry: The merge history entry to add to index
        """
        index = self._load_index()

        # Add merge ID if not already present
        if entry.merge_id not in index.get("merges", []):
            index.setdefault("merges", []).append(entry.merge_id)

        # Update timestamp
        index["last_updated"] = datetime.now().isoformat()

        # Save index
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update merge index: {e}")
