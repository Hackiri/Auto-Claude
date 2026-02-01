"""
QA Validation Package
=====================

Modular QA validation system with:
- Acceptance criteria validation
- Criterion-level tracking with evidence capture
- Issue tracking and reporting
- Recurring issue detection
- QA reviewer and fixer agents
- Main orchestration loop

Usage:
    from qa import run_qa_validation_loop, should_run_qa, is_qa_approved
    from qa import extract_acceptance_criteria, record_criterion_result

Module structure:
    - loop.py: Main QA orchestration loop
    - reviewer.py: QA reviewer agent session
    - fixer.py: QA fixer agent session
    - report.py: Issue tracking, reporting, escalation, criterion results
    - criteria.py: Acceptance criteria extraction and status management
"""

# Configuration constants
# Criteria & status
from .criteria import (
    extract_acceptance_criteria,
    get_criterion_results,
    get_criterion_stats,
    get_qa_iteration_count,
    get_qa_signoff_status,
    initialize_criteria_tracking,
    is_fixes_applied,
    is_qa_approved,
    is_qa_rejected,
    load_implementation_plan,
    print_qa_status,
    record_criterion_results,
    save_implementation_plan,
    should_run_fixes,
    should_run_qa,
    update_criterion_result,
)
from .fixer import (
    load_qa_fixer_prompt,
    run_qa_fixer_session,
)

# Main loop
from .loop import MAX_QA_ITERATIONS, run_qa_validation_loop

# Report & tracking
from .report import (
    ISSUE_SIMILARITY_THRESHOLD,
    RECURRING_ISSUE_THRESHOLD,
    _issue_similarity,
    # Private functions exposed for testing
    _normalize_issue_key,
    check_test_discovery,
    clear_criterion_results,
    create_manual_test_plan,
    escalate_to_human,
    get_criterion_results_for_iteration,
    get_criterion_validation_summary,
    get_iteration_history,
    get_latest_criterion_results,
    get_recurring_issue_summary,
    has_recurring_issues,
    is_no_test_project,
    record_criteria_batch,
    record_criterion_result,
    record_iteration,
)

# Agent sessions
from .reviewer import run_qa_agent_session

# Public API
__all__ = [
    # Configuration
    "MAX_QA_ITERATIONS",
    "RECURRING_ISSUE_THRESHOLD",
    "ISSUE_SIMILARITY_THRESHOLD",
    # Main loop
    "run_qa_validation_loop",
    # Criteria & status
    "load_implementation_plan",
    "save_implementation_plan",
    "get_qa_signoff_status",
    "is_qa_approved",
    "is_qa_rejected",
    "is_fixes_applied",
    "get_qa_iteration_count",
    "should_run_qa",
    "should_run_fixes",
    "print_qa_status",
    # Criterion-level tracking (from criteria.py)
    "extract_acceptance_criteria",
    "get_criterion_results",
    "get_criterion_stats",
    "initialize_criteria_tracking",
    "record_criterion_results",
    "update_criterion_result",
    # Criterion-level tracking (from report.py)
    "record_criterion_result",
    "record_criteria_batch",
    "get_latest_criterion_results",
    "get_criterion_results_for_iteration",
    "get_criterion_validation_summary",
    "clear_criterion_results",
    # Report & tracking
    "get_iteration_history",
    "record_iteration",
    "has_recurring_issues",
    "get_recurring_issue_summary",
    "escalate_to_human",
    "create_manual_test_plan",
    "check_test_discovery",
    "is_no_test_project",
    "_normalize_issue_key",
    "_issue_similarity",
    # Agent sessions
    "run_qa_agent_session",
    "load_qa_fixer_prompt",
    "run_qa_fixer_session",
]
