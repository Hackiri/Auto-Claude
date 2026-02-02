"""
Conflict Monitor
================

Background monitor that periodically checks all active worktrees for
potential merge conflicts using ConflictPredictor.

Runs on a configurable interval (default 5 minutes) using threading.Timer,
enumerates active worktrees via WorktreeManager, and stores results in
.auto-claude/conflict_reports/.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .conflict_predictor import ConflictPredictor, PredictionResult

# Import debug utilities
try:
    from debug import debug, debug_error, debug_section, debug_success, debug_warning
except ImportError:

    def debug(*args, **kwargs):
        pass

    def debug_error(*args, **kwargs):
        pass

    def debug_section(*args, **kwargs):
        pass

    def debug_success(*args, **kwargs):
        pass

    def debug_warning(*args, **kwargs):
        pass


logger = logging.getLogger(__name__)
MODULE = "merge.conflict_monitor"

# Default check interval: 5 minutes
DEFAULT_CHECK_INTERVAL = 300


@dataclass
class WorktreeConflictStatus:
    """Conflict status for a single worktree."""

    spec_name: str
    worktree_path: str
    prediction: PredictionResult
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "spec_name": self.spec_name,
            "worktree_path": self.worktree_path,
            "prediction": self.prediction.to_dict(),
            "checked_at": self.checked_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorktreeConflictStatus:
        """Create from dictionary."""
        return cls(
            spec_name=data["spec_name"],
            worktree_path=data["worktree_path"],
            prediction=PredictionResult.from_dict(data["prediction"]),
            checked_at=data["checked_at"],
        )


@dataclass
class ConflictReport:
    """
    Aggregated conflict report across all active worktrees.

    Attributes:
        timestamp: When the report was generated
        worktrees_checked: Number of worktrees analyzed
        worktrees_with_conflicts: Number of worktrees with conflicts
        statuses: Per-worktree conflict status
        errors: Any errors encountered during checking
    """

    timestamp: str = ""
    worktrees_checked: int = 0
    worktrees_with_conflicts: int = 0
    statuses: list[WorktreeConflictStatus] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "worktrees_checked": self.worktrees_checked,
            "worktrees_with_conflicts": self.worktrees_with_conflicts,
            "statuses": [s.to_dict() for s in self.statuses],
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConflictReport:
        """Create from dictionary."""
        return cls(
            timestamp=data.get("timestamp", ""),
            worktrees_checked=data.get("worktrees_checked", 0),
            worktrees_with_conflicts=data.get("worktrees_with_conflicts", 0),
            statuses=[
                WorktreeConflictStatus.from_dict(s)
                for s in data.get("statuses", [])
            ],
            errors=data.get("errors", []),
        )

    @property
    def has_conflicts(self) -> bool:
        """Whether any worktree has conflicts."""
        return self.worktrees_with_conflicts > 0

    @property
    def total_conflicts(self) -> int:
        """Total number of conflicts across all worktrees."""
        return sum(
            len(s.prediction.conflicts)
            for s in self.statuses
        )


class ConflictMonitor:
    """
    Background monitor for merge conflicts across active worktrees.

    Periodically runs ConflictPredictor on each active worktree and
    stores aggregated results in .auto-claude/conflict_reports/.

    Example:
        monitor = ConflictMonitor(project_dir=Path("/path/to/project"))
        monitor.start()

        # Get latest results
        report = monitor.latest_report

        # Force immediate check
        report = monitor.check_now()

        # Stop monitoring
        monitor.stop()
    """

    def __init__(
        self,
        project_dir: Path,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        base_branch: str | None = None,
    ):
        """
        Initialize the conflict monitor.

        Args:
            project_dir: Root directory of the project
            check_interval: Seconds between checks (default 300 = 5 min)
            base_branch: Base branch for conflict prediction (auto-detected if None)
        """
        self._project_dir = Path(project_dir).resolve()
        self._check_interval = check_interval
        self._base_branch = base_branch
        self._timer: threading.Timer | None = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_report: ConflictReport | None = None

        # Reports directory
        self._reports_dir = self._project_dir / ".auto-claude" / "conflict_reports"

        debug_section(MODULE, "Initializing ConflictMonitor")
        debug(
            MODULE,
            "Configuration",
            project_dir=str(project_dir),
            check_interval=check_interval,
        )

    @property
    def latest_report(self) -> ConflictReport | None:
        """Get the latest conflict report."""
        with self._lock:
            return self._latest_report

    @property
    def is_running(self) -> bool:
        """Whether the monitor is actively running."""
        return self._running

    def start(self) -> None:
        """Start the background conflict monitor."""
        if self._running:
            debug_warning(MODULE, "Monitor already running")
            return

        debug(MODULE, "Starting conflict monitor")
        self._running = True
        self._schedule_check()

    def stop(self) -> None:
        """Stop the background conflict monitor."""
        debug(MODULE, "Stopping conflict monitor")
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def check_now(self) -> ConflictReport:
        """
        Run an immediate conflict check across all active worktrees.

        Returns:
            ConflictReport with results from all worktrees
        """
        debug_section(MODULE, "Running conflict check")
        return self._run_check()

    def _schedule_check(self) -> None:
        """Schedule the next background check."""
        if not self._running:
            return

        self._timer = threading.Timer(self._check_interval, self._background_check)
        self._timer.daemon = True
        self._timer.start()

    def _background_check(self) -> None:
        """Execute a background check and schedule the next one."""
        if not self._running:
            return

        try:
            self._run_check()
        except Exception as e:
            debug_error(MODULE, f"Background check failed: {e}")
            logger.exception("Background conflict check failed")
        finally:
            self._schedule_check()

    def _run_check(self) -> ConflictReport:
        """
        Run conflict prediction on all active worktrees.

        Returns:
            ConflictReport with aggregated results
        """
        report = ConflictReport(
            timestamp=datetime.now().isoformat(),
        )

        # Get active worktrees
        worktrees = self._enumerate_worktrees()

        for spec_name, worktree_path in worktrees:
            try:
                base_branch = self._base_branch or self._detect_base_branch()
                predictor = ConflictPredictor(
                    worktree_path=worktree_path,
                    base_branch=base_branch,
                )
                prediction = predictor.predict()

                status = WorktreeConflictStatus(
                    spec_name=spec_name,
                    worktree_path=str(worktree_path),
                    prediction=prediction,
                    checked_at=datetime.now().isoformat(),
                )
                report.statuses.append(status)
                report.worktrees_checked += 1

                if prediction.has_conflicts:
                    report.worktrees_with_conflicts += 1
                    debug_warning(
                        MODULE,
                        f"Conflicts detected in {spec_name}",
                        count=len(prediction.conflicts),
                    )
                else:
                    debug_success(MODULE, f"No conflicts in {spec_name}")

            except Exception as e:
                error_msg = f"Failed to check {spec_name}: {e}"
                report.errors.append(error_msg)
                debug_error(MODULE, error_msg)
                logger.exception(f"Failed to check worktree {spec_name}")

        # Store results
        with self._lock:
            self._latest_report = report

        self._save_report(report)

        if report.has_conflicts:
            debug_warning(
                MODULE,
                f"Check complete: {report.worktrees_with_conflicts}/"
                f"{report.worktrees_checked} worktrees have conflicts",
            )
        else:
            debug_success(
                MODULE,
                f"Check complete: {report.worktrees_checked} worktrees clean",
            )

        return report

    def _enumerate_worktrees(self) -> list[tuple[str, Path]]:
        """
        Enumerate active worktrees using WorktreeManager.

        Returns:
            List of (spec_name, worktree_path) tuples
        """
        worktrees: list[tuple[str, Path]] = []
        worktrees_dir = self._project_dir / ".auto-claude" / "worktrees" / "tasks"

        if not worktrees_dir.exists():
            debug(MODULE, "No worktrees directory found")
            return worktrees

        for entry in worktrees_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                # Verify it's a valid git worktree by checking for .git
                git_marker = entry / ".git"
                if git_marker.exists():
                    worktrees.append((entry.name, entry))

        debug(MODULE, f"Found {len(worktrees)} active worktrees")
        return worktrees

    def _detect_base_branch(self) -> str:
        """Detect the base branch from WorktreeManager or default."""
        try:
            from core.worktree import WorktreeManager

            manager = WorktreeManager(self._project_dir)
            return manager.base_branch
        except Exception:
            return "main"

    def _save_report(self, report: ConflictReport) -> None:
        """Save the conflict report to disk."""
        try:
            self._reports_dir.mkdir(parents=True, exist_ok=True)

            # Save latest report
            latest_path = self._reports_dir / "latest.json"
            latest_path.write_text(
                json.dumps(report.to_dict(), indent=2),
                encoding="utf-8",
            )

            # Save timestamped report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            timestamped_path = self._reports_dir / f"report_{timestamp}.json"
            timestamped_path.write_text(
                json.dumps(report.to_dict(), indent=2),
                encoding="utf-8",
            )

            debug(MODULE, f"Report saved to {latest_path}")

        except Exception as e:
            debug_error(MODULE, f"Failed to save report: {e}")
            logger.exception("Failed to save conflict report")

    @classmethod
    def load_latest_report(cls, project_dir: Path) -> ConflictReport | None:
        """
        Load the latest conflict report from disk.

        Args:
            project_dir: Root directory of the project

        Returns:
            ConflictReport if found, None otherwise
        """
        latest_path = (
            project_dir / ".auto-claude" / "conflict_reports" / "latest.json"
        )
        if not latest_path.exists():
            return None

        try:
            data = json.loads(latest_path.read_text(encoding="utf-8"))
            return ConflictReport.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load conflict report: {e}")
            return None
