"""
Ralph Loop Reporter Module
===========================

Handles overnight run summary reporting, iteration history tracking,
and progress report generation for the Ralph Wiggum iterative loop.

Generates ralph_loop_report.md with comprehensive run statistics including:
- Total iterations and duration
- Success/failure breakdown
- Approach variations attempted
- Completion promise results
- Recommendations for future runs
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import RalphLoopConfig, get_default_config
from .promises import CompletionPromise, PromiseResult


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class IterationRecord:
    """Record of a single iteration in the Ralph loop.

    Attributes:
        iteration: Iteration number (1-indexed)
        phase: Which phase this iteration was in ("coder" or "qa")
        status: Outcome of the iteration ("success", "failure", "skipped", "error")
        timestamp: When this iteration started
        duration_seconds: How long the iteration took
        subtask_id: ID of the subtask being worked on (if applicable)
        approach: Approach category used for this iteration
        error_message: Error message if status is "failure" or "error"
        details: Additional details about the iteration
    """

    iteration: int
    phase: str
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float | None = None
    subtask_id: str | None = None
    approach: str | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary for serialization."""
        return {
            "iteration": self.iteration,
            "phase": self.phase,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "subtask_id": self.subtask_id,
            "approach": self.approach,
            "error_message": self.error_message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IterationRecord:
        """Create record from dictionary."""
        return cls(
            iteration=data.get("iteration", 0),
            phase=data.get("phase", "unknown"),
            status=data.get("status", "unknown"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            duration_seconds=data.get("duration_seconds"),
            subtask_id=data.get("subtask_id"),
            approach=data.get("approach"),
            error_message=data.get("error_message"),
            details=data.get("details", {}),
        )


@dataclass
class RalphLoopSummary:
    """Summary statistics for a Ralph loop run.

    Attributes:
        total_iterations: Total number of iterations executed
        successful_iterations: Number of successful iterations
        failed_iterations: Number of failed iterations
        total_duration_seconds: Total time spent in the loop
        start_time: When the loop started
        end_time: When the loop ended
        final_status: Overall outcome ("completed", "max_iterations", "failed", "interrupted")
        phases_executed: List of phases that were executed
        subtasks_completed: Number of subtasks completed
        subtasks_total: Total number of subtasks
        approaches_used: Counter of approach categories used
        promise_results: Results of completion promise evaluations
        config_used: Configuration that was used for this run
    """

    total_iterations: int = 0
    successful_iterations: int = 0
    failed_iterations: int = 0
    total_duration_seconds: float = 0.0
    start_time: str | None = None
    end_time: str | None = None
    final_status: str = "pending"
    phases_executed: list[str] = field(default_factory=list)
    subtasks_completed: int = 0
    subtasks_total: int = 0
    approaches_used: dict[str, int] = field(default_factory=dict)
    promise_results: list[dict[str, Any]] = field(default_factory=list)
    config_used: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary for serialization."""
        return {
            "total_iterations": self.total_iterations,
            "successful_iterations": self.successful_iterations,
            "failed_iterations": self.failed_iterations,
            "total_duration_seconds": self.total_duration_seconds,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "final_status": self.final_status,
            "phases_executed": self.phases_executed,
            "subtasks_completed": self.subtasks_completed,
            "subtasks_total": self.subtasks_total,
            "approaches_used": self.approaches_used,
            "promise_results": self.promise_results,
            "config_used": self.config_used,
        }


# =============================================================================
# RALPH LOOP REPORTER CLASS
# =============================================================================


class RalphLoopReporter:
    """
    Reporter for tracking and summarizing Ralph loop runs.

    The reporter maintains iteration history and generates comprehensive
    run reports for overnight builds. It integrates with the implementation
    plan for persistent storage.

    Usage:
        reporter = RalphLoopReporter(spec_dir)
        reporter.start_run(config)

        # During the loop
        reporter.record_iteration(
            phase="coder",
            status="success",
            subtask_id="subtask-1-1"
        )

        # At the end
        reporter.finish_run("completed")
        reporter.generate_report()
    """

    def __init__(self, spec_dir: Path):
        """
        Initialize the reporter.

        Args:
            spec_dir: Path to the spec directory
        """
        self.spec_dir = spec_dir
        self.history: list[IterationRecord] = []
        self.summary = RalphLoopSummary()
        self._current_iteration = 0
        self._run_started = False

        # Load any existing history from the plan
        self._load_history()

    def _load_history(self) -> None:
        """Load existing Ralph loop history from implementation_plan.json."""
        plan_path = self.spec_dir / "implementation_plan.json"
        if not plan_path.exists():
            return

        try:
            with open(plan_path) as f:
                plan = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        # Load iteration history if present
        ralph_data = plan.get("ralph_loop_data", {})
        history_data = ralph_data.get("iteration_history", [])

        for record_data in history_data:
            try:
                record = IterationRecord.from_dict(record_data)
                self.history.append(record)
            except (KeyError, ValueError):
                pass

        # Set current iteration based on history
        if self.history:
            self._current_iteration = max(r.iteration for r in self.history)

    def _save_history(self) -> bool:
        """Save Ralph loop history to implementation_plan.json."""
        plan_path = self.spec_dir / "implementation_plan.json"

        # Load existing plan
        plan = {}
        if plan_path.exists():
            try:
                with open(plan_path) as f:
                    plan = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # Update Ralph loop data
        plan["ralph_loop_data"] = {
            "iteration_history": [r.to_dict() for r in self.history],
            "summary": self.summary.to_dict(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Save back
        try:
            with open(plan_path, "w") as f:
                json.dump(plan, f, indent=2)
            return True
        except OSError:
            return False

    def start_run(self, config: RalphLoopConfig | None = None) -> None:
        """
        Start a new Ralph loop run.

        Args:
            config: Configuration for this run (uses defaults if not provided)
        """
        self._run_started = True
        self.summary.start_time = datetime.now(timezone.utc).isoformat()
        self.summary.config_used = dict(config) if config else dict(get_default_config())

    def record_iteration(
        self,
        phase: str,
        status: str,
        duration_seconds: float | None = None,
        subtask_id: str | None = None,
        approach: str | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> IterationRecord:
        """
        Record a single iteration of the Ralph loop.

        Args:
            phase: Which phase ("coder" or "qa")
            status: Outcome ("success", "failure", "skipped", "error")
            duration_seconds: How long the iteration took
            subtask_id: ID of the subtask being worked on
            approach: Approach category used
            error_message: Error message if applicable
            details: Additional details

        Returns:
            The created IterationRecord
        """
        self._current_iteration += 1

        record = IterationRecord(
            iteration=self._current_iteration,
            phase=phase,
            status=status,
            duration_seconds=duration_seconds,
            subtask_id=subtask_id,
            approach=approach,
            error_message=error_message,
            details=details or {},
        )

        self.history.append(record)

        # Update summary statistics
        self.summary.total_iterations = self._current_iteration

        if status in ("success", "completed"):
            self.summary.successful_iterations += 1
        elif status in ("failure", "error"):
            self.summary.failed_iterations += 1

        if duration_seconds:
            self.summary.total_duration_seconds += duration_seconds

        if phase not in self.summary.phases_executed:
            self.summary.phases_executed.append(phase)

        if approach:
            if approach not in self.summary.approaches_used:
                self.summary.approaches_used[approach] = 0
            self.summary.approaches_used[approach] += 1

        # Persist to disk
        self._save_history()

        return record

    def record_promise_result(self, result: PromiseResult) -> None:
        """
        Record a completion promise evaluation result.

        Args:
            result: The PromiseResult from evaluation
        """
        self.summary.promise_results.append({
            "name": result.promise.name,
            "passed": result.passed,
            "message": result.message,
            "required": result.promise.required,
        })
        self._save_history()

    def finish_run(
        self,
        final_status: str,
        subtasks_completed: int = 0,
        subtasks_total: int = 0,
    ) -> None:
        """
        Finish the Ralph loop run.

        Args:
            final_status: Overall outcome ("completed", "max_iterations", "failed", "interrupted")
            subtasks_completed: Number of subtasks completed
            subtasks_total: Total number of subtasks
        """
        self.summary.end_time = datetime.now(timezone.utc).isoformat()
        self.summary.final_status = final_status
        self.summary.subtasks_completed = subtasks_completed
        self.summary.subtasks_total = subtasks_total
        self._run_started = False
        self._save_history()

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the Ralph loop run.

        Returns:
            Dictionary of statistics
        """
        # Calculate duration
        total_duration = self.summary.total_duration_seconds
        hours = int(total_duration // 3600)
        minutes = int((total_duration % 3600) // 60)
        seconds = int(total_duration % 60)
        duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

        # Calculate success rate
        total = self.summary.total_iterations
        success_rate = (
            self.summary.successful_iterations / total if total > 0 else 0
        )

        # Count iterations by phase
        phase_counts: Counter[str] = Counter()
        for record in self.history:
            phase_counts[record.phase] += 1

        # Count errors by type
        error_counts: Counter[str] = Counter()
        for record in self.history:
            if record.error_message:
                # Extract error type from message
                error_type = record.error_message.split(":")[0] if ":" in record.error_message else "Unknown"
                error_counts[error_type] += 1

        return {
            "total_iterations": total,
            "successful_iterations": self.summary.successful_iterations,
            "failed_iterations": self.summary.failed_iterations,
            "success_rate": success_rate,
            "total_duration": duration_str,
            "total_duration_seconds": total_duration,
            "phases": dict(phase_counts),
            "approaches_used": self.summary.approaches_used,
            "error_types": dict(error_counts),
            "subtasks_completed": self.summary.subtasks_completed,
            "subtasks_total": self.summary.subtasks_total,
            "final_status": self.summary.final_status,
        }

    def generate_report(self) -> Path:
        """
        Generate the ralph_loop_report.md file.

        Returns:
            Path to the generated report file
        """
        report_path = self.spec_dir / "ralph_loop_report.md"
        stats = self.get_statistics()

        # Build the report content
        content = self._build_report_content(stats)

        # Write the report
        report_path.write_text(content)
        return report_path

    def _build_report_content(self, stats: dict[str, Any]) -> str:
        """Build the markdown content for the report."""
        now = datetime.now(timezone.utc).isoformat()

        content = f"""# Ralph Loop Run Report

**Generated**: {now}
**Final Status**: {stats["final_status"].upper()}

## Summary

| Metric | Value |
|--------|-------|
| Total Iterations | {stats["total_iterations"]} |
| Successful | {stats["successful_iterations"]} |
| Failed | {stats["failed_iterations"]} |
| Success Rate | {stats["success_rate"]:.1%} |
| Total Duration | {stats["total_duration"]} |
| Subtasks Completed | {stats["subtasks_completed"]}/{stats["subtasks_total"]} |

## Configuration Used

| Setting | Value |
|---------|-------|
| Max Coder Iterations | {self.summary.config_used.get("max_coder_iterations", "N/A")} |
| Max QA Iterations | {self.summary.config_used.get("max_qa_iterations", "N/A")} |
| Retry Strategy | {self.summary.config_used.get("retry_strategy", "N/A")} |
| Overnight Mode | {self.summary.config_used.get("overnight_mode", False)} |

## Phases Executed

"""
        # Add phase breakdown
        for phase, count in stats["phases"].items():
            content += f"- **{phase.title()}**: {count} iterations\n"

        # Add approaches section if any were used
        if stats["approaches_used"]:
            content += "\n## Approach Variations\n\n"
            content += "The following approach categories were used during retry attempts:\n\n"
            for approach, count in sorted(
                stats["approaches_used"].items(), key=lambda x: x[1], reverse=True
            ):
                content += f"- **{approach}**: {count} times\n"

        # Add completion promise results
        if self.summary.promise_results:
            content += "\n## Completion Promise Results\n\n"
            content += "| Promise | Status | Required | Message |\n"
            content += "|---------|--------|----------|--------|\n"

            for result in self.summary.promise_results:
                status_emoji = "\u2705" if result["passed"] else "\u274c"
                required = "Yes" if result["required"] else "No"
                content += f"| {result['name']} | {status_emoji} | {required} | {result['message']} |\n"

        # Add error breakdown if any errors occurred
        if stats["error_types"]:
            content += "\n## Error Breakdown\n\n"
            for error_type, count in sorted(
                stats["error_types"].items(), key=lambda x: x[1], reverse=True
            ):
                content += f"- **{error_type}**: {count} occurrences\n"

        # Add iteration history (last 20 iterations)
        content += "\n## Recent Iteration History\n\n"
        content += "| # | Phase | Status | Duration | Subtask | Approach |\n"
        content += "|---|-------|--------|----------|---------|----------|\n"

        recent_history = self.history[-20:]  # Last 20 iterations
        for record in recent_history:
            duration = f"{record.duration_seconds:.1f}s" if record.duration_seconds else "N/A"
            subtask = record.subtask_id or "N/A"
            approach = record.approach or "N/A"
            status_emoji = {
                "success": "\u2705",
                "completed": "\u2705",
                "failure": "\u274c",
                "error": "\u26a0\ufe0f",
                "skipped": "\u23ed\ufe0f",
            }.get(record.status, "\u2753")
            content += f"| {record.iteration} | {record.phase} | {status_emoji} {record.status} | {duration} | {subtask} | {approach} |\n"

        # Add recommendations section
        content += self._build_recommendations(stats)

        content += f"""

---

*Report generated by Ralph Loop Reporter*
*Start Time: {self.summary.start_time or "N/A"}*
*End Time: {self.summary.end_time or "N/A"}*
"""

        return content

    def _build_recommendations(self, stats: dict[str, Any]) -> str:
        """Build recommendations section based on run statistics."""
        recommendations = []

        # Check success rate
        if stats["success_rate"] < 0.5:
            recommendations.append(
                "**Low success rate detected**: Consider breaking down subtasks into "
                "smaller, more manageable pieces, or increasing the detail in specifications."
            )

        # Check if max iterations was hit
        if stats["final_status"] == "max_iterations":
            recommendations.append(
                "**Max iterations reached**: The loop was terminated due to reaching "
                "the maximum iteration limit. Consider increasing `max_coder_iterations` "
                "or simplifying the remaining subtasks."
            )

        # Check if certain approaches were overused
        if stats["approaches_used"]:
            max_approach = max(stats["approaches_used"].items(), key=lambda x: x[1])
            if max_approach[1] > 5:
                recommendations.append(
                    f"**Heavy use of '{max_approach[0]}' approach**: This approach was "
                    f"used {max_approach[1]} times. Consider whether the underlying issue "
                    "needs different handling."
                )

        # Check for many errors
        if stats["failed_iterations"] > stats["successful_iterations"]:
            recommendations.append(
                "**More failures than successes**: Review error messages to identify "
                "patterns. Common issues may include environment setup problems, "
                "missing dependencies, or unclear requirements."
            )

        # Check completion status
        if stats["subtasks_completed"] < stats["subtasks_total"]:
            remaining = stats["subtasks_total"] - stats["subtasks_completed"]
            recommendations.append(
                f"**{remaining} subtasks remaining**: Not all subtasks were completed. "
                "Manual review may be needed to address blocking issues."
            )

        if not recommendations:
            recommendations.append(
                "**Run completed successfully**: No issues detected. Consider using "
                "similar configuration for future overnight runs."
            )

        content = "\n## Recommendations\n\n"
        for i, rec in enumerate(recommendations, 1):
            content += f"{i}. {rec}\n\n"

        return content


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def generate_ralph_report(
    spec_dir: Path,
    final_status: str = "completed",
    subtasks_completed: int = 0,
    subtasks_total: int = 0,
) -> Path:
    """
    Generate a Ralph loop report for the given spec.

    This is a convenience function that creates a RalphLoopReporter,
    finishes the run, and generates the report.

    Args:
        spec_dir: Path to the spec directory
        final_status: Overall outcome of the run
        subtasks_completed: Number of subtasks completed
        subtasks_total: Total number of subtasks

    Returns:
        Path to the generated report file
    """
    reporter = RalphLoopReporter(spec_dir)
    reporter.finish_run(
        final_status=final_status,
        subtasks_completed=subtasks_completed,
        subtasks_total=subtasks_total,
    )
    return reporter.generate_report()


def get_ralph_run_status(spec_dir: Path) -> dict[str, Any]:
    """
    Get the current status of a Ralph loop run.

    Args:
        spec_dir: Path to the spec directory

    Returns:
        Dictionary with run status information
    """
    reporter = RalphLoopReporter(spec_dir)

    if not reporter.history:
        return {
            "has_run": False,
            "message": "No Ralph loop run history found",
        }

    stats = reporter.get_statistics()

    return {
        "has_run": True,
        "in_progress": reporter._run_started,
        "statistics": stats,
        "last_iteration": reporter.history[-1].to_dict() if reporter.history else None,
        "summary": reporter.summary.to_dict(),
    }


def clear_ralph_history(spec_dir: Path) -> bool:
    """
    Clear Ralph loop history from the spec directory.

    Args:
        spec_dir: Path to the spec directory

    Returns:
        True if cleared successfully
    """
    plan_path = spec_dir / "implementation_plan.json"

    if not plan_path.exists():
        return True

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    # Remove Ralph loop data
    if "ralph_loop_data" in plan:
        del plan["ralph_loop_data"]

    try:
        with open(plan_path, "w") as f:
            json.dump(plan, f, indent=2)
        return True
    except OSError:
        return False
