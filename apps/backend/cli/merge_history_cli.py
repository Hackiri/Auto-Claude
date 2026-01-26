"""
Merge History CLI
==================

CLI interface for the MergeHistoryTracker service.
Used for viewing merge history and performing rollbacks.

Usage:
    python apps/backend/cli/merge_history_cli.py list-merges
    python apps/backend/cli/merge_history_cli.py show-merge <merge_id>
    python apps/backend/cli/merge_history_cli.py rollback-merge <merge_id>
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to Python path for imports
_script_dir = Path(__file__).resolve().parent
_backend_dir = _script_dir.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def find_project_root() -> Path:
    """Find the project root by looking for .auto-claude or .git directory."""
    current = Path.cwd()

    # Walk up until we find .auto-claude or .git
    while current != current.parent:
        if (current / ".auto-claude").exists() or (current / ".git").exists():
            return current
        current = current.parent

    # Default to cwd
    return Path.cwd()


def get_tracker():
    """Get the MergeHistoryTracker instance for this project."""
    from merge.merge_history import MergeHistoryTracker

    project_path = find_project_root()
    storage_path = project_path / ".auto-claude"
    return MergeHistoryTracker(storage_path), project_path


def cmd_list_merges(args):
    """List all merge history entries."""
    tracker, _ = get_tracker()

    merges = tracker.get_all_merges()

    if not merges:
        print("No merges recorded")
        return

    print(f"\n=== Merge History ({len(merges)} merges) ===\n")

    for merge in merges:
        status = "✓" if merge.success else "✗"
        duration = f"{merge.duration_seconds:.1f}s" if merge.duration_seconds else "N/A"
        conflicts = (
            f"{merge.total_conflicts} conflicts"
            if merge.total_conflicts
            else "no conflicts"
        )

        print(f"{status} [{merge.merge_id}] {merge.task_id}")
        print(f"   Spec: {merge.spec_name}")
        print(f"   Started: {merge.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duration: {duration}, {conflicts}")
        print(
            f"   Files: {len(merge.files_changed)} changed, {len(merge.files_added)} added, {len(merge.files_deleted)} deleted"
        )
        if merge.merge_commit:
            print(f"   Commit: {merge.merge_commit[:8]}")
        if not merge.success and merge.error_message:
            print(f"   Error: {merge.error_message}")
        print()


def cmd_show_merge(args):
    """Show detailed information about a specific merge."""
    tracker, _ = get_tracker()
    merge_id = args.merge_id

    merge = tracker.get_merge(merge_id)
    if not merge:
        print(f"Merge not found: {merge_id}")
        sys.exit(1)

    print(f"\n=== Merge Details: {merge_id} ===\n")

    # Basic info
    print(f"Task ID: {merge.task_id}")
    print(f"Spec: {merge.spec_name}")
    print(f"Status: {'Success' if merge.success else 'Failed'}")
    print(f"Started: {merge.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if merge.completed_at:
        print(f"Completed: {merge.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {merge.duration_seconds:.1f}s")

    # Source info
    print(f"\nSource Worktree: {merge.source_worktree}")
    print(f"Source Branch: {merge.source_branch}")
    print(f"Target Branch: {merge.target_branch}")

    # Git info
    if merge.pre_merge_commit:
        print(f"\nPre-merge Commit: {merge.pre_merge_commit}")
    if merge.merge_commit:
        print(f"Merge Commit: {merge.merge_commit}")

    # Files
    print(f"\n--- Files Changed ({len(merge.files_changed)}) ---")
    for file_path in merge.files_changed:
        print(f"  M {file_path}")

    if merge.files_added:
        print(f"\n--- Files Added ({len(merge.files_added)}) ---")
        for file_path in merge.files_added:
            print(f"  A {file_path}")

    if merge.files_deleted:
        print(f"\n--- Files Deleted ({len(merge.files_deleted)}) ---")
        for file_path in merge.files_deleted:
            print(f"  D {file_path}")

    # Conflicts
    if merge.total_conflicts > 0:
        print(f"\n--- Conflicts Resolved ({merge.total_conflicts}) ---")
        print(f"Auto-resolved: {merge.auto_resolved_count}")
        print(f"AI-resolved: {merge.ai_resolved_count}")

        for i, conflict in enumerate(merge.conflicts_resolved, 1):
            print(f"\n  [{i}] {conflict.file_path}")
            print(f"      Type: {conflict.conflict_type}")
            print(f"      Resolution: {conflict.resolution_method}")
            if conflict.ai_reasoning:
                print(f"      AI Reasoning: {conflict.ai_reasoning[:100]}...")
            print(
                f"      Resolved at: {conflict.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

    # AI usage
    if merge.ai_tokens_used > 0:
        print(f"\nAI Tokens Used: {merge.ai_tokens_used:,}")

    # Error info
    if not merge.success and merge.error_message:
        print("\n--- Error ---")
        print(f"{merge.error_message}")


def cmd_rollback_merge(args):
    """Rollback a specific merge."""
    tracker, project_path = get_tracker()
    merge_id = args.merge_id

    # Verify merge exists
    merge = tracker.get_merge(merge_id)
    if not merge:
        print(f"Merge not found: {merge_id}")
        sys.exit(1)

    print(f"\n=== Rolling back merge: {merge_id} ===\n")
    print(f"Task: {merge.task_id}")
    print(f"Spec: {merge.spec_name}")
    print(f"Files affected: {len(merge.files_changed)}")

    if not merge.merge_commit:
        print("\nError: No merge commit found. Cannot rollback.")
        sys.exit(1)

    print(f"\nThis will revert commit: {merge.merge_commit[:8]}")

    # Confirm rollback (unless --force flag is used)
    if not args.force:
        response = input("\nAre you sure you want to rollback this merge? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("Rollback cancelled.")
            sys.exit(0)

    # Perform rollback
    print("\nPerforming rollback...")
    success = tracker.rollback_merge(merge_id, project_path)

    if success:
        print("\n✓ Rollback completed successfully!")
        print("  A new revert commit has been created.")
        print("  Run 'git log' to see the changes.")
    else:
        print("\n✗ Rollback failed!")
        print("  Check the error messages above.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Merge History CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list-merges
    list_parser = subparsers.add_parser(
        "list-merges", help="List all merge history entries"
    )
    list_parser.set_defaults(func=cmd_list_merges)

    # show-merge
    show_parser = subparsers.add_parser(
        "show-merge", help="Show detailed information about a specific merge"
    )
    show_parser.add_argument("merge_id", help="The merge ID to show")
    show_parser.set_defaults(func=cmd_show_merge)

    # rollback-merge
    rollback_parser = subparsers.add_parser(
        "rollback-merge", help="Rollback a specific merge"
    )
    rollback_parser.add_argument("merge_id", help="The merge ID to rollback")
    rollback_parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompt"
    )
    rollback_parser.set_defaults(func=cmd_rollback_merge)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
