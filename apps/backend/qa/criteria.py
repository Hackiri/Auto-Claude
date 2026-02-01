"""
QA Acceptance Criteria Handling
================================

Manages acceptance criteria validation and status tracking.
"""

import json
from pathlib import Path

from progress import is_build_complete

# =============================================================================
# IMPLEMENTATION PLAN I/O
# =============================================================================


def load_implementation_plan(spec_dir: Path) -> dict | None:
    """Load the implementation plan JSON."""
    plan_file = spec_dir / "implementation_plan.json"
    if not plan_file.exists():
        return None
    try:
        with open(plan_file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def save_implementation_plan(spec_dir: Path, plan: dict) -> bool:
    """Save the implementation plan JSON."""
    plan_file = spec_dir / "implementation_plan.json"
    try:
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
        return True
    except OSError:
        return False


# =============================================================================
# QA SIGN-OFF STATUS
# =============================================================================


def get_qa_signoff_status(spec_dir: Path) -> dict | None:
    """Get the current QA sign-off status from implementation plan."""
    plan = load_implementation_plan(spec_dir)
    if not plan:
        return None
    return plan.get("qa_signoff")


def is_qa_approved(spec_dir: Path) -> bool:
    """Check if QA has approved the build."""
    status = get_qa_signoff_status(spec_dir)
    if not status:
        return False
    return status.get("status") == "approved"


def is_qa_rejected(spec_dir: Path) -> bool:
    """Check if QA has rejected the build (needs fixes)."""
    status = get_qa_signoff_status(spec_dir)
    if not status:
        return False
    return status.get("status") == "rejected"


def is_fixes_applied(spec_dir: Path) -> bool:
    """Check if fixes have been applied and ready for re-validation."""
    status = get_qa_signoff_status(spec_dir)
    if not status:
        return False
    return status.get("status") == "fixes_applied" and status.get(
        "ready_for_qa_revalidation", False
    )


def get_qa_iteration_count(spec_dir: Path) -> int:
    """Get the number of QA iterations so far."""
    status = get_qa_signoff_status(spec_dir)
    if not status:
        return 0
    return status.get("qa_session", 0)


# =============================================================================
# QA READINESS CHECKS
# =============================================================================


def should_run_qa(spec_dir: Path) -> bool:
    """
    Determine if QA validation should run.

    QA should run when:
    - All subtasks are completed
    - QA has not yet approved
    """
    if not is_build_complete(spec_dir):
        return False

    if is_qa_approved(spec_dir):
        return False

    return True


def should_run_fixes(spec_dir: Path) -> bool:
    """
    Determine if QA fixes should run.

    Fixes should run when:
    - QA has rejected the build
    - Max iterations not reached
    """
    from .loop import MAX_QA_ITERATIONS

    if not is_qa_rejected(spec_dir):
        return False

    iterations = get_qa_iteration_count(spec_dir)
    if iterations >= MAX_QA_ITERATIONS:
        return False

    return True


# =============================================================================
# ACCEPTANCE CRITERIA EXTRACTION & TRACKING
# =============================================================================


def extract_acceptance_criteria(spec_dir: Path) -> list[dict[str, str]]:
    """
    Extract acceptance criteria from spec.md file.

    Parses the spec.md looking for "## Acceptance Criteria" section
    and extracts each criterion with its text and checkbox status.

    Args:
        spec_dir: Spec directory containing spec.md

    Returns:
        List of criteria dicts with 'id', 'text', 'checked' fields.
        Empty list if spec.md doesn't exist or has no criteria.
    """
    spec_file = spec_dir / "spec.md"
    if not spec_file.exists():
        return []

    try:
        content = spec_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    criteria = []
    in_criteria_section = False
    criterion_id = 0

    for line in content.split("\n"):
        # Start of acceptance criteria section
        if "## Acceptance Criteria" in line:
            in_criteria_section = True
            continue

        # End of section (next heading)
        if in_criteria_section and line.startswith("## "):
            break

        # Parse criterion lines (markdown checkboxes)
        if in_criteria_section and line.strip():
            stripped = line.strip()

            # Handle checkbox format: "- [ ] criterion" or "- [x] criterion"
            if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                checked = stripped.startswith("- [x]")
                text = stripped[6:].strip()  # Remove "- [ ] " or "- [x] "
                criterion_id += 1
                criteria.append(
                    {
                        "id": f"criterion-{criterion_id}",
                        "text": text,
                        "checked": checked,
                    }
                )
            # Handle plain list format: "- criterion"
            elif stripped.startswith("- "):
                text = stripped[2:].strip()
                criterion_id += 1
                criteria.append(
                    {
                        "id": f"criterion-{criterion_id}",
                        "text": text,
                        "checked": False,
                    }
                )

    return criteria


def get_criterion_results(spec_dir: Path) -> list[dict]:
    """
    Get the current validation results for all acceptance criteria.

    Returns:
        List of criterion result dicts with status, evidence, etc.
        Empty list if no results exist.
    """
    plan = load_implementation_plan(spec_dir)
    if not plan:
        return []
    return plan.get("qa_criterion_results", [])


def update_criterion_result(
    spec_dir: Path,
    criterion_id: str,
    status: str,
    evidence: dict | None = None,
) -> bool:
    """
    Update the validation result for a specific criterion.

    Args:
        spec_dir: Spec directory
        criterion_id: ID of the criterion (e.g., "criterion-1")
        status: "passed", "failed", or "pending"
        evidence: Optional dict with error_message, screenshot_path, etc.

    Returns:
        True if updated successfully
    """
    from datetime import datetime, timezone

    plan = load_implementation_plan(spec_dir)
    if not plan:
        plan = {}

    if "qa_criterion_results" not in plan:
        plan["qa_criterion_results"] = []

    # Find existing result for this criterion
    existing_index = None
    for i, result in enumerate(plan["qa_criterion_results"]):
        if result.get("criterion_id") == criterion_id:
            existing_index = i
            break

    result_record = {
        "criterion_id": criterion_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if evidence:
        result_record["evidence"] = evidence

    if existing_index is not None:
        plan["qa_criterion_results"][existing_index] = result_record
    else:
        plan["qa_criterion_results"].append(result_record)

    return save_implementation_plan(spec_dir, plan)


def record_criterion_results(
    spec_dir: Path,
    results: list[dict],
    iteration: int,
) -> bool:
    """
    Record validation results for multiple criteria at once.

    Args:
        spec_dir: Spec directory
        results: List of dicts with criterion_id, status, evidence
        iteration: QA iteration number

    Returns:
        True if recorded successfully
    """
    from datetime import datetime, timezone

    plan = load_implementation_plan(spec_dir)
    if not plan:
        plan = {}

    # Initialize criteria tracking if not present
    if "qa_criterion_results" not in plan:
        plan["qa_criterion_results"] = []

    timestamp = datetime.now(timezone.utc).isoformat()

    # Update each criterion result
    for result in results:
        criterion_id = result.get("criterion_id")
        if not criterion_id:
            continue

        result_record = {
            "criterion_id": criterion_id,
            "criterion_text": result.get("criterion_text", ""),
            "status": result.get("status", "pending"),
            "timestamp": timestamp,
            "iteration": iteration,
        }

        # Add evidence if present
        if result.get("evidence"):
            result_record["evidence"] = result["evidence"]

        # Find and update or append
        existing_index = None
        for i, existing in enumerate(plan["qa_criterion_results"]):
            if existing.get("criterion_id") == criterion_id:
                existing_index = i
                break

        if existing_index is not None:
            plan["qa_criterion_results"][existing_index] = result_record
        else:
            plan["qa_criterion_results"].append(result_record)

    # Update summary stats
    total = len(plan["qa_criterion_results"])
    passed = sum(
        1 for r in plan["qa_criterion_results"] if r.get("status") == "passed"
    )
    failed = sum(
        1 for r in plan["qa_criterion_results"] if r.get("status") == "failed"
    )

    plan["qa_criterion_stats"] = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pending": total - passed - failed,
        "pass_rate": passed / total if total > 0 else 0,
        "last_updated": timestamp,
    }

    return save_implementation_plan(spec_dir, plan)


def get_criterion_stats(spec_dir: Path) -> dict:
    """
    Get summary statistics for criterion validation.

    Returns:
        Dict with total, passed, failed, pending counts and pass_rate.
    """
    plan = load_implementation_plan(spec_dir)
    if not plan:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pending": 0,
            "pass_rate": 0,
        }

    return plan.get(
        "qa_criterion_stats",
        {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pending": 0,
            "pass_rate": 0,
        },
    )


def initialize_criteria_tracking(spec_dir: Path) -> list[dict]:
    """
    Initialize criterion tracking from spec.md.

    Extracts acceptance criteria and creates pending result records
    for each criterion.

    Args:
        spec_dir: Spec directory

    Returns:
        List of initialized criterion records
    """
    criteria = extract_acceptance_criteria(spec_dir)
    if not criteria:
        return []

    # Create initial records with pending status
    initial_results = [
        {
            "criterion_id": c["id"],
            "criterion_text": c["text"],
            "status": "pending",
        }
        for c in criteria
    ]

    record_criterion_results(spec_dir, initial_results, iteration=0)
    return initial_results


# =============================================================================
# STATUS DISPLAY
# =============================================================================


def print_qa_status(spec_dir: Path) -> None:
    """Print the current QA status."""
    from .report import get_iteration_history, get_recurring_issue_summary

    status = get_qa_signoff_status(spec_dir)

    if not status:
        print("QA Status: Not started")
        return

    qa_status = status.get("status", "unknown")
    qa_session = status.get("qa_session", 0)
    timestamp = status.get("timestamp", "unknown")

    print(f"QA Status: {qa_status.upper()}")
    print(f"QA Sessions: {qa_session}")
    print(f"Last Updated: {timestamp}")

    if qa_status == "approved":
        tests = status.get("tests_passed", {})
        print(
            f"Tests: Unit {tests.get('unit', '?')}, Integration {tests.get('integration', '?')}, E2E {tests.get('e2e', '?')}"
        )
    elif qa_status == "rejected":
        issues = status.get("issues_found", [])
        print(f"Issues Found: {len(issues)}")
        for issue in issues[:3]:  # Show first 3
            print(
                f"  - {issue.get('title', 'Unknown')}: {issue.get('type', 'unknown')}"
            )
        if len(issues) > 3:
            print(f"  ... and {len(issues) - 3} more")

    # Show iteration history summary
    history = get_iteration_history(spec_dir)
    if history:
        summary = get_recurring_issue_summary(history)
        print("\nIteration History:")
        print(f"  Total iterations: {len(history)}")
        print(f"  Approved: {summary.get('iterations_approved', 0)}")
        print(f"  Rejected: {summary.get('iterations_rejected', 0)}")
        if summary.get("most_common"):
            print("  Most common issues:")
            for issue in summary["most_common"][:3]:
                print(f"    - {issue['title']} ({issue['occurrences']} occurrences)")
