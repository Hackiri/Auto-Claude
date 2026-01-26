"""
Merge History JSON API
========================

JSON API wrapper for MergeHistoryTracker.
Used by frontend IPC handlers to get merge history data.

Usage:
    python apps/backend/cli/merge_history_json.py list <project_path>
    python apps/backend/cli/merge_history_json.py get <project_path> <merge_id>
    python apps/backend/cli/merge_history_json.py rollback <project_path> <merge_id>
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend directory to Python path for imports
_script_dir = Path(__file__).resolve().parent
_backend_dir = _script_dir.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def get_tracker(project_path: str):
    """Get the MergeHistoryTracker instance for a project."""
    from merge.merge_history import MergeHistoryTracker

    storage_path = Path(project_path) / ".auto-claude"
    return MergeHistoryTracker(storage_path)


def cmd_list(args):
    """List all merge history entries as JSON."""
    tracker = get_tracker(args.project_path)

    merges = tracker.get_all_merges()

    # Convert to JSON-serializable format
    result = {"success": True, "data": [merge.to_dict() for merge in merges]}

    print(json.dumps(result, indent=2))


def cmd_get(args):
    """Get a specific merge by ID as JSON."""
    tracker = get_tracker(args.project_path)

    merge = tracker.get_merge(args.merge_id)

    if not merge:
        result = {"success": False, "error": f"Merge not found: {args.merge_id}"}
    else:
        result = {"success": True, "data": merge.to_dict()}

    print(json.dumps(result, indent=2))


def cmd_rollback(args):
    """Rollback a specific merge as JSON."""
    tracker = get_tracker(args.project_path)

    # Verify merge exists
    merge = tracker.get_merge(args.merge_id)
    if not merge:
        result = {"success": False, "error": f"Merge not found: {args.merge_id}"}
        print(json.dumps(result, indent=2))
        return

    if not merge.merge_commit:
        result = {"success": False, "error": "No merge commit found. Cannot rollback."}
        print(json.dumps(result, indent=2))
        return

    # Perform rollback
    project_path = Path(args.project_path)
    success = tracker.rollback_merge(args.merge_id, project_path)

    if success:
        result = {
            "success": True,
            "data": {
                "message": "Rollback completed successfully",
                "merge_id": args.merge_id,
            },
        }
    else:
        result = {"success": False, "error": "Rollback failed"}

    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Merge History JSON API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    list_parser = subparsers.add_parser("list", help="List all merge history entries")
    list_parser.add_argument("project_path", help="Path to the project")
    list_parser.set_defaults(func=cmd_list)

    # get
    get_parser = subparsers.add_parser("get", help="Get a specific merge by ID")
    get_parser.add_argument("project_path", help="Path to the project")
    get_parser.add_argument("merge_id", help="The merge ID to get")
    get_parser.set_defaults(func=cmd_get)

    # rollback
    rollback_parser = subparsers.add_parser(
        "rollback", help="Rollback a specific merge"
    )
    rollback_parser.add_argument("project_path", help="Path to the project")
    rollback_parser.add_argument("merge_id", help="The merge ID to rollback")
    rollback_parser.set_defaults(func=cmd_rollback)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        args.func(args)
    except Exception as e:
        result = {"success": False, "error": str(e)}
        print(json.dumps(result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
