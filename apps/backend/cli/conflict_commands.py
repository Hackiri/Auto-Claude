"""
Conflict Commands
=================

CLI commands for conflict analysis and prevention (check, status, monitor start/stop)
"""

import json
import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from merge.conflict_monitor import ConflictMonitor, ConflictReport
from merge.conflict_predictor import ConflictPredictor, PredictionResult
from merge.resolution_advisor import ResolutionAdvisor
from ui import (
    Icons,
    icon,
)

from .utils import print_banner

# Module-level monitor instance for start/stop lifecycle
_active_monitor: ConflictMonitor | None = None


def _get_worktree_path(project_dir: Path, spec_name: str) -> Path | None:
    """
    Find the worktree path for a given spec name.

    Args:
        project_dir: Project root directory
        spec_name: Spec identifier (e.g., "001" or "001-feature-name")

    Returns:
        Path to the worktree, or None if not found
    """
    worktree_base = project_dir / ".auto-claude" / "worktrees" / "tasks"
    if not worktree_base.exists():
        return None

    # Try exact match
    exact = worktree_base / spec_name
    if exact.exists():
        return exact

    # Try prefix match
    for entry in worktree_base.iterdir():
        if entry.is_dir() and entry.name.startswith(spec_name + "-"):
            return entry

    return None


def _detect_base_branch(project_dir: Path) -> str:
    """Detect the default base branch for the repository."""
    import os
    import subprocess

    env_branch = os.getenv("DEFAULT_BRANCH")
    if env_branch:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", env_branch],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return env_branch

    for branch in ["main", "master"]:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return branch

    return "main"


def _load_latest_report(project_dir: Path) -> ConflictReport | None:
    """Load the most recent conflict report from disk."""
    reports_dir = project_dir / ".auto-claude" / "conflict_reports"
    if not reports_dir.exists():
        return None

    report_files = sorted(reports_dir.glob("report_*.json"), reverse=True)
    if not report_files:
        return None

    try:
        data = json.loads(report_files[0].read_text(encoding="utf-8"))
        return ConflictReport.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _print_prediction_result(spec_name: str, result: PredictionResult) -> None:
    """Print a formatted prediction result for a single spec."""
    if result.error:
        print(f"  {icon(Icons.ERROR)} Error: {result.error}")
        return

    if not result.has_conflicts:
        print(f"  {icon(Icons.SUCCESS)} No conflicts detected")
        if result.commits_behind > 0:
            print(f"    {result.commits_behind} commit(s) behind {result.base_branch}")
        return

    print(f"  {icon(Icons.WARNING)} {len(result.conflicts)} conflict(s) detected")
    print(f"    Base branch: {result.base_branch}")
    print(f"    Commits behind: {result.commits_behind}")
    if result.needs_rebase:
        print(f"    {icon(Icons.WARNING)} Rebase recommended")

    for conflict in result.conflicts:
        severity_icon = icon(Icons.ERROR) if conflict.severity.value in ("critical", "high") else icon(Icons.WARNING)
        print(f"    {severity_icon} {conflict.file_path} [{conflict.severity.value}] - {conflict.conflict_type.value}")
        if conflict.description:
            print(f"      {conflict.description}")


def _print_advice(result: PredictionResult) -> None:
    """Print resolution advice for a prediction result."""
    if not result.has_conflicts:
        return

    advisor = ResolutionAdvisor()
    advices = advisor.advise(result)
    if advices:
        print(f"\n  {icon(Icons.LIGHTNING)} Resolution Advice:")
        for advice in advices:
            print(f"    • {advice.file_path}: {advice.strategy.value} - {advice.rationale}")
            if advice.recommended_action:
                print(f"      Action: {advice.recommended_action}")


def handle_conflict_check(project_dir: Path, spec_name: str) -> None:
    """
    Run conflict prediction for a single spec's worktree.

    Args:
        project_dir: Project root directory
        spec_name: Spec identifier to check
    """
    print_banner()
    print(f"\n{icon(Icons.SEARCH)} Conflict Check: {spec_name}\n")

    worktree_path = _get_worktree_path(project_dir, spec_name)
    if worktree_path is None:
        print(f"  {icon(Icons.ERROR)} No worktree found for spec '{spec_name}'")
        print("  Use --list to see active worktrees.")
        return

    base_branch = _detect_base_branch(project_dir)
    predictor = ConflictPredictor(
        worktree_path=worktree_path,
        base_branch=base_branch,
    )

    print(f"  Analyzing {worktree_path.name} against {base_branch}...")
    result = predictor.predict()

    print()
    _print_prediction_result(spec_name, result)
    _print_advice(result)
    print()


def handle_conflict_status(project_dir: Path) -> None:
    """
    Show the latest conflict report for all worktrees.

    Args:
        project_dir: Project root directory
    """
    print_banner()
    print(f"\n{icon(Icons.INFO)} Conflict Status\n")

    report = _load_latest_report(project_dir)

    if report is None:
        print("  No conflict reports found.")
        print("  Run --conflict-check <spec> to analyze a specific spec,")
        print("  or use --conflict-monitor-start to enable background monitoring.")
        return

    print(f"  Last checked: {report.timestamp}")
    print(f"  Worktrees checked: {report.worktrees_checked}")
    print(f"  With conflicts: {report.worktrees_with_conflicts}")
    print()

    if not report.statuses:
        print("  No worktrees analyzed.")
        return

    for status in report.statuses:
        conflict_marker = icon(Icons.WARNING) if status.prediction.has_conflicts else icon(Icons.SUCCESS)
        print(f"  {conflict_marker} {status.spec_name}")
        _print_prediction_result(status.spec_name, status.prediction)
        print()

    if report.errors:
        print(f"  {icon(Icons.ERROR)} Errors:")
        for error in report.errors:
            print(f"    - {error}")


def handle_conflict_monitor_start(project_dir: Path, interval: int = 300) -> None:
    """
    Start the background conflict monitor.

    Args:
        project_dir: Project root directory
        interval: Check interval in seconds (default 300 = 5 min)
    """
    global _active_monitor

    print_banner()
    print(f"\n{icon(Icons.LIGHTNING)} Starting Conflict Monitor\n")

    if _active_monitor is not None and _active_monitor.is_running:
        print(f"  {icon(Icons.WARNING)} Monitor is already running.")
        print("  Use --conflict-monitor-stop to stop it first.")
        return

    base_branch = _detect_base_branch(project_dir)
    _active_monitor = ConflictMonitor(
        project_dir=project_dir,
        check_interval=interval,
        base_branch=base_branch,
    )
    _active_monitor.start()

    print(f"  {icon(Icons.SUCCESS)} Monitor started")
    print(f"  Check interval: {interval}s")
    print(f"  Base branch: {base_branch}")
    print(f"  Reports: {project_dir / '.auto-claude' / 'conflict_reports'}")
    print()


def handle_conflict_monitor_stop() -> None:
    """Stop the background conflict monitor."""
    global _active_monitor

    print_banner()
    print(f"\n{icon(Icons.LIGHTNING)} Stopping Conflict Monitor\n")

    if _active_monitor is None or not _active_monitor.is_running:
        print(f"  {icon(Icons.WARNING)} No active monitor to stop.")
        return

    _active_monitor.stop()
    _active_monitor = None

    print(f"  {icon(Icons.SUCCESS)} Monitor stopped")
    print()
