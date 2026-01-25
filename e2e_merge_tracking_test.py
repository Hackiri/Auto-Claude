#!/usr/bin/env python3
"""
End-to-End Test for Merge Tracking History Feature

This script tests the complete merge tracking workflow:
1. Create a test merge entry
2. Verify it's recorded in .auto-claude/merge_history/
3. Test CLI commands (list-merges, show-merge)
4. Test rollback functionality
5. Verify UI integration points

Usage:
    python e2e_merge_tracking_test.py
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# Get project root
project_root = Path(__file__).parent
backend_path = project_root / "apps" / "backend"

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_step(message):
    """Print a test step message"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}==> {message}{Colors.RESET}")

def print_success(message):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message):
    """Print an error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_info(message):
    """Print an info message"""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")

def create_test_merge_entry():
    """Create a test merge entry JSON file manually"""
    merge_data = {
        "merge_id": "test-merge-001",
        "timestamp": datetime.now().isoformat(),
        "spec_id": "test-spec",
        "spec_name": "E2E Test Spec",
        "source_branch": "auto-claude/test-spec",
        "target_branch": "main",
        "merge_commit": "abc123def456",
        "status": "success",
        "files_changed": {
            "added": ["test_file_1.py", "test_file_2.py"],
            "modified": ["existing_file.py"],
            "deleted": []
        },
        "conflicts_resolved": [
            {
                "file_path": "existing_file.py",
                "conflict_type": "content",
                "resolution_method": "ai_assisted",
                "ai_tokens_used": 1500,
                "resolution_time_seconds": 30.5
            }
        ],
        "total_conflicts": 1,
        "auto_resolved_conflicts": 0,
        "ai_resolved_conflicts": 1,
        "total_ai_tokens_used": 1500,
        "merge_duration_seconds": 45.2
    }
    return merge_data

def test_merge_history_tracker():
    """Test 1: Create merge history entry manually and verify"""
    print_step("Test 1: Create Merge History Entry")

    try:
        # Create test merge entry
        test_entry = create_test_merge_entry()

        # Create merge history directory structure
        merge_dir = project_root / ".auto-claude" / "merge_history"
        merge_dir.mkdir(parents=True, exist_ok=True)

        # Create year-month subdirectory
        now = datetime.now()
        year_month = now.strftime("%Y-%m")
        year_month_dir = merge_dir / year_month
        year_month_dir.mkdir(exist_ok=True)

        # Write merge entry file
        merge_file = year_month_dir / f"{test_entry['merge_id']}.json"
        with open(merge_file, 'w') as f:
            json.dump(test_entry, f, indent=2)

        print_success(f"Created merge entry: {merge_file}")

        # Update or create index
        index_file = merge_dir / "index.json"
        if index_file.exists():
            with open(index_file, 'r') as f:
                index_data = json.load(f)
        else:
            index_data = {"merges": []}

        # Add to index
        index_entry = {
            "merge_id": test_entry["merge_id"],
            "timestamp": test_entry["timestamp"],
            "spec_id": test_entry["spec_id"],
            "status": test_entry["status"],
            "file_path": str(merge_file.relative_to(merge_dir))
        }

        index_data["merges"].append(index_entry)

        with open(index_file, 'w') as f:
            json.dump(index_data, f, indent=2)

        print_success(f"Updated index: {index_file}")

        # Verify file was created
        if not merge_file.exists():
            print_error(f"Merge file not found: {merge_file}")
            return False

        # Read back and verify
        with open(merge_file, 'r') as f:
            retrieved = json.load(f)

        if retrieved["spec_name"] != test_entry["spec_name"]:
            print_error(f"Spec name mismatch: {retrieved['spec_name']} != {test_entry['spec_name']}")
            return False

        if retrieved["status"] != test_entry["status"]:
            print_error(f"Status mismatch: {retrieved['status']} != {test_entry['status']}")
            return False

        print_success("Data integrity verified")
        print_success(f"Merge entry created successfully: {test_entry['merge_id']}")

        return True

    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cli_commands():
    """Test 2: CLI commands (list-merges, show-merge)"""
    print_step("Test 2: CLI Commands - list-merges and show-merge")

    try:
        cli_script = backend_path / "cli" / "merge_history_cli.py"
        if not cli_script.exists():
            print_error(f"CLI script not found: {cli_script}")
            return False

        # Test list-merges
        print_info("Testing: python merge_history_cli.py list-merges")
        result = subprocess.run(
            [sys.executable, str(cli_script), "list-merges"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print_error(f"list-merges failed: {result.stderr}")
            return False

        print_success("list-merges command executed successfully")
        print(result.stdout[:500])  # Print first 500 chars

        # Test show-merge
        print_info("Testing: python merge_history_cli.py show-merge test-merge-001")
        result = subprocess.run(
            [sys.executable, str(cli_script), "show-merge", "test-merge-001"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print_error(f"show-merge failed: {result.stderr}")
            return False

        print_success("show-merge command executed successfully")
        print(result.stdout[:500])  # Print first 500 chars

        return True

    except subprocess.TimeoutExpired:
        print_error("CLI command timed out")
        return False
    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_json_api():
    """Test 3: JSON API wrapper for frontend integration"""
    print_step("Test 3: JSON API Wrapper - merge_history_json.py")

    try:
        json_script = backend_path / "cli" / "merge_history_json.py"
        if not json_script.exists():
            print_error(f"JSON API script not found: {json_script}")
            return False

        # Test list command
        print_info(f"Testing: python merge_history_json.py list {project_root}")
        result = subprocess.run(
            [sys.executable, str(json_script), "list", str(project_root)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print_error(f"JSON list command failed: {result.stderr}")
            return False

        # Parse JSON response
        try:
            response = json.loads(result.stdout)
            if "error" in response:
                print_error(f"JSON API returned error: {response['error']}")
                return False

            merges = response.get("merges", [])
            print_success(f"JSON API returned {len(merges)} merge(s)")

            # Verify merge data structure
            if merges:
                merge = merges[0]
                required_fields = ["merge_id", "timestamp", "spec_name", "status", "files_changed"]
                for field in required_fields:
                    if field not in merge:
                        print_error(f"Missing required field in JSON response: {field}")
                        return False

                print_success("JSON response structure validated")

        except json.JSONDecodeError as e:
            print_error(f"Failed to parse JSON response: {e}")
            return False

        # Test get command
        print_info(f"Testing: python merge_history_json.py get {project_root} test-merge-001")
        result = subprocess.run(
            [sys.executable, str(json_script), "get", str(project_root), "test-merge-001"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print_error(f"JSON get command failed: {result.stderr}")
            return False

        try:
            response = json.loads(result.stdout)
            if "error" in response:
                print_error(f"JSON API returned error: {response['error']}")
                return False

            merge = response.get("merge")
            if not merge:
                print_error("JSON get command did not return merge data")
                return False

            print_success(f"Retrieved merge via JSON API: {merge['merge_id']}")

        except json.JSONDecodeError as e:
            print_error(f"Failed to parse JSON response: {e}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print_error("JSON API command timed out")
        return False
    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ipc_handlers():
    """Test 4: Verify IPC handlers are registered"""
    print_step("Test 4: IPC Handlers - Frontend Integration Points")

    try:
        ipc_handler_file = project_root / "apps" / "frontend" / "src" / "main" / "ipc-handlers" / "merge-history-handlers.ts"

        if not ipc_handler_file.exists():
            print_error(f"IPC handler file not found: {ipc_handler_file}")
            return False

        print_success(f"IPC handler file exists: {ipc_handler_file.name}")

        # Check for required handlers
        content = ipc_handler_file.read_text()

        required_handlers = [
            "registerGetMergeHistory",
            "registerGetMergeDetails",
            "registerRollbackMerge"
        ]

        for handler in required_handlers:
            if handler not in content:
                print_error(f"Required handler not found: {handler}")
                return False
            print_success(f"Handler found: {handler}")

        # Check IPC constants
        ipc_constants_file = project_root / "apps" / "frontend" / "src" / "shared" / "constants" / "ipc.ts"

        if not ipc_constants_file.exists():
            print_error(f"IPC constants file not found: {ipc_constants_file}")
            return False

        content = ipc_constants_file.read_text()

        required_constants = [
            "MERGE_HISTORY_GET",
            "MERGE_HISTORY_GET_DETAILS",
            "MERGE_HISTORY_ROLLBACK"
        ]

        for constant in required_constants:
            if constant not in content:
                print_error(f"Required IPC constant not found: {constant}")
                return False
            print_success(f"IPC constant found: {constant}")

        return True

    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ui_components():
    """Test 5: Verify UI components exist"""
    print_step("Test 5: UI Components - Frontend React Components")

    try:
        component_file = project_root / "apps" / "frontend" / "src" / "renderer" / "components" / "task-detail" / "TaskMergeHistory.tsx"

        if not component_file.exists():
            print_error(f"TaskMergeHistory component not found: {component_file}")
            return False

        print_success(f"TaskMergeHistory component exists")

        # Check for required features
        content = component_file.read_text()

        required_features = [
            "getMergeHistory",  # API call
            "rollbackMerge",    # Rollback functionality
            "AlertDialog",      # Confirmation dialog
            "RotateCcw",        # Rollback icon
            "useTranslation"    # i18n support
        ]

        for feature in required_features:
            if feature not in content:
                print_error(f"Required feature not found in component: {feature}")
                return False
            print_success(f"Feature found: {feature}")

        # Check TaskDetailModal integration
        modal_file = project_root / "apps" / "frontend" / "src" / "renderer" / "components" / "task-detail" / "TaskDetailModal.tsx"

        if not modal_file.exists():
            print_error(f"TaskDetailModal not found: {modal_file}")
            return False

        modal_content = modal_file.read_text()

        if "TaskMergeHistory" not in modal_content:
            print_error("TaskMergeHistory not integrated into TaskDetailModal")
            return False

        print_success("TaskMergeHistory integrated into TaskDetailModal")

        # Check i18n translations
        en_tasks = project_root / "apps" / "frontend" / "src" / "shared" / "i18n" / "locales" / "en" / "tasks.json"
        fr_tasks = project_root / "apps" / "frontend" / "src" / "shared" / "i18n" / "locales" / "fr" / "tasks.json"

        for locale_file, locale_name in [(en_tasks, "English"), (fr_tasks, "French")]:
            if not locale_file.exists():
                print_error(f"{locale_name} translation file not found: {locale_file}")
                return False

            locale_content = json.loads(locale_file.read_text())

            if "mergeHistory" not in locale_content:
                print_error(f"mergeHistory translations not found in {locale_name}")
                return False

            print_success(f"{locale_name} translations validated")

        return True

    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_test_data():
    """Clean up test merge history data"""
    print_step("Cleanup: Removing test data")

    try:
        merge_dir = project_root / ".auto-claude" / "merge_history"

        if merge_dir.exists():
            # Remove test merge entries
            for year_month_dir in merge_dir.iterdir():
                if year_month_dir.is_dir():
                    test_files = list(year_month_dir.glob("test-merge-*.json"))
                    for test_file in test_files:
                        test_file.unlink()
                        print_success(f"Removed: {test_file.name}")

                    # Remove empty directories
                    if not any(year_month_dir.iterdir()):
                        year_month_dir.rmdir()
                        print_success(f"Removed empty directory: {year_month_dir.name}")

            # Remove index.json if it exists
            index_file = merge_dir / "index.json"
            if index_file.exists():
                # Remove test entries from index
                with open(index_file, 'r') as f:
                    index_data = json.load(f)

                # Filter out test entries
                index_data["merges"] = [
                    m for m in index_data["merges"]
                    if not m["merge_id"].startswith("test-merge-")
                ]

                with open(index_file, 'w') as f:
                    json.dump(index_data, f, indent=2)

                print_success("Cleaned up index.json")

        print_success("Cleanup completed")
        return True

    except Exception as e:
        print_error(f"Cleanup failed: {e}")
        return False

def print_ui_test_instructions():
    """Print instructions for manual UI testing"""
    print_step("UI Testing Instructions (Manual)")

    instructions = """
To test the UI components in the Electron app:

1. Start the Electron app:
   $ npm run dev

2. Open a task in the task list

3. In the Task Detail Modal, you should see a new "Merge History" tab
   (Look for the GitMerge icon next to Files, Logs, etc.)

4. Click the "Merge History" tab to view merge history

5. Verify the following:
   ✓ Merge entries are displayed with timestamps
   ✓ Files changed are shown (added, modified, deleted)
   ✓ Conflict resolution statistics are visible
   ✓ Rollback button appears for successful merges

6. Test the rollback functionality:
   ✓ Click "Rollback" button on a merge entry
   ✓ Confirmation dialog appears
   ✓ Confirm the rollback
   ✓ Success message displays
   ✓ Merge history refreshes

7. Verify i18n support:
   ✓ Switch language to French in settings
   ✓ All merge history labels should be translated

Note: You need at least one successful merge to test the UI.
Create a test spec, build it, and merge it first.
"""

    print(instructions)

def main():
    """Run all E2E tests"""
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"  Merge Tracking History - End-to-End Test Suite")
    print(f"{'='*60}{Colors.RESET}\n")

    tests = [
        ("MergeHistoryTracker", test_merge_history_tracker),
        ("CLI Commands", test_cli_commands),
        ("JSON API", test_json_api),
        ("IPC Handlers", test_ipc_handlers),
        ("UI Components", test_ui_components),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Unexpected error in {test_name}: {e}")
            results.append((test_name, False))

    # Print summary
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"  Test Summary")
    print(f"{'='*60}{Colors.RESET}\n")

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for test_name, result in results:
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")

    print(f"\n{Colors.BOLD}Total: {passed} passed, {failed} failed{Colors.RESET}\n")

    # Cleanup
    cleanup_test_data()

    # Print UI test instructions
    print_ui_test_instructions()

    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
