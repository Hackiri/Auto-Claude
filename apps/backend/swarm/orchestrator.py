"""
Swarm Orchestrator Module
==========================

Coordinates multiple concurrent worker agents to execute subtasks in parallel.
Each worker claims tasks atomically from a shared queue, creates its own SDK client,
and reports progress to a shared swarm_state.json file.
"""

from __future__ import annotations

import asyncio
import importlib.util as _imputil
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.client import create_client
from phase_config import get_phase_model, get_phase_thinking_budget
from progress import get_next_subtask, is_build_complete

# Import file_lock directly to avoid runners.github.__init__ side effects
_fl_spec = _imputil.spec_from_file_location(
    "file_lock",
    Path(__file__).resolve().parent.parent / "runners" / "github" / "file_lock.py",
)
_fl_mod = _imputil.module_from_spec(_fl_spec)  # type: ignore[arg-type]
_fl_spec.loader.exec_module(_fl_mod)  # type: ignore[union-attr]
FileLock = _fl_mod.FileLock

if TYPE_CHECKING:
    from task_logger import TaskLogger
from prompt_generator import (
    format_context_for_prompt,
    generate_subtask_prompt,
    load_subtask_context,
)
from recovery import RecoveryManager

from .config import SwarmConfig

logger = logging.getLogger(__name__)


@dataclass
class WorkerState:
    """State of a single swarm worker."""

    id: str
    status: str = "idle"  # idle, claiming, working, done, error
    current_task: str | None = None
    tasks_completed: int = 0
    errors: list[str] = field(default_factory=list)


class SwarmOrchestrator:
    """
    Orchestrates multiple concurrent worker agents for parallel subtask execution.

    Workers claim tasks from a shared queue using file locking for atomicity,
    execute them via SDK client sessions, and report progress to swarm_state.json.
    """

    def __init__(
        self,
        project_dir: Path,
        spec_dir: Path,
        model: str,
        swarm_config: SwarmConfig,
        recovery_manager: RecoveryManager,
        task_logger: TaskLogger | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.spec_dir = spec_dir
        self.model = model
        self.max_workers = swarm_config.get("max_workers", 3)
        self.recovery_manager = recovery_manager
        self.task_logger = task_logger
        self.state_file = spec_dir / "swarm_state.json"
        self._lock_file = spec_dir / ".swarm_state.lock"
        self._workers: list[WorkerState] = []
        self._started_at: str | None = None
        self._logger_lock = asyncio.Lock()

    async def run_swarm_build(self) -> None:
        """
        Run the swarm build: spawn N worker coroutines that claim and execute
        subtasks concurrently until all tasks are complete or no more are available.
        """
        self._started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._workers = [
            WorkerState(id=f"worker-{i + 1}") for i in range(self.max_workers)
        ]

        # Initialize swarm state file
        self._write_swarm_state()

        logger.info(
            f"Swarm build starting with {self.max_workers} workers"
        )

        # Spawn worker coroutines
        tasks = [
            self._worker_loop(worker) for worker in self._workers
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Mark all workers as done
        for worker in self._workers:
            worker.status = "done"
        self._write_swarm_state()

        logger.info("Swarm build finished")

    async def _worker_loop(self, worker: WorkerState) -> None:
        """
        Main loop for a single worker: claim tasks and execute them until none remain.
        """
        while True:
            # Check if build is complete
            if is_build_complete(self.spec_dir):
                worker.status = "done"
                self._write_swarm_state()
                break

            # Try to claim a task
            worker.status = "claiming"
            self._write_swarm_state()

            subtask = self._claim_next_task(worker.id)
            if subtask is None:
                # No more tasks available
                worker.status = "idle"
                worker.current_task = None
                self._write_swarm_state()

                # Wait briefly and check again (other workers may fail and release tasks)
                await asyncio.sleep(3)

                # If build is complete, stop. Don't check get_next_subtask outside
                # the lock — that causes a race where multiple workers see the same task.
                if is_build_complete(self.spec_dir):
                    worker.status = "done"
                    self._write_swarm_state()
                    break
                continue

            subtask_id = subtask.get("id", "unknown")
            worker.status = "working"
            worker.current_task = subtask_id
            self._update_task_status(subtask_id, "in_progress", worker.id)
            self._write_swarm_state()

            logger.info(f"{worker.id}: Executing subtask {subtask_id}")
            await self._log_event(
                subtask_id, worker.id, f"{worker.id}: Claiming {subtask_id}"
            )

            try:
                success = await self._execute_subtask(worker, subtask)
                if success:
                    worker.tasks_completed += 1
                    self._update_task_status(subtask_id, "completed", worker.id)
                    await self._log_event(
                        subtask_id, worker.id, f"{worker.id}: Completed {subtask_id}"
                    )
                else:
                    self._update_task_status(subtask_id, "failed", worker.id)
                    worker.errors.append(f"{subtask_id}: execution failed")
                    await self._log_event(
                        subtask_id, worker.id, f"{worker.id}: Failed {subtask_id}"
                    )
            except Exception as e:
                logger.error(f"{worker.id}: Error executing {subtask_id}: {e}")
                self._update_task_status(subtask_id, "failed", worker.id)
                worker.errors.append(f"{subtask_id}: {str(e)[:200]}")
                await self._log_event(
                    subtask_id, worker.id, f"{worker.id}: Failed {subtask_id}: {e}"
                )

            worker.current_task = None
            self._write_swarm_state()

            # Brief pause between tasks
            await asyncio.sleep(1)

    def _claim_next_task(self, worker_id: str) -> dict[str, Any] | None:
        """
        Atomically claim the next available subtask using file locking.

        Returns:
            The claimed subtask dict, or None if no tasks available.
        """
        try:
            with FileLock(self._lock_file, timeout=5.0):
                subtask = get_next_subtask(self.spec_dir)
                if subtask is None:
                    return None

                # Mark as in_progress in the implementation plan to prevent
                # other workers from claiming it
                subtask_id = subtask.get("id")
                if subtask_id:
                    self._mark_subtask_in_progress(subtask_id)

                return subtask
        except OSError as e:
            logger.error(f"Failed to acquire lock for task claiming: {e}")
            return None

    def _mark_subtask_in_progress(self, subtask_id: str) -> None:
        """Mark a subtask as in_progress in the implementation plan."""
        plan_path = self.spec_dir / "implementation_plan.json"
        if not plan_path.exists():
            return

        try:
            with open(plan_path) as f:
                plan = json.load(f)

            for phase in plan.get("phases", []):
                for subtask in phase.get("subtasks", []):
                    if subtask.get("id") == subtask_id:
                        subtask["status"] = "in_progress"
                        break

            with open(plan_path, "w") as f:
                json.dump(plan, f, indent=2)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to mark subtask {subtask_id} in progress: {e}")

    async def _execute_subtask(
        self, worker: WorkerState, subtask: dict[str, Any]
    ) -> bool:
        """
        Execute a single subtask by creating an SDK client and running a session.

        Returns:
            True if subtask completed successfully.
        """
        subtask_id = subtask.get("id", "unknown")
        phase_model = get_phase_model(self.spec_dir, "coding", self.model)
        phase_thinking = get_phase_thinking_budget(self.spec_dir, "coding")

        client = create_client(
            self.project_dir,
            self.spec_dir,
            phase_model,
            agent_type="coder",
            max_thinking_tokens=phase_thinking,
        )

        # Load implementation plan to get phase context
        plan = self._load_plan()
        phase = self._find_phase_for_subtask(plan, subtask_id) if plan else {}

        # Generate prompt
        attempt_count = self.recovery_manager.get_attempt_count(subtask_id)
        recovery_hints = (
            self.recovery_manager.get_recovery_hints(subtask_id)
            if attempt_count > 0
            else None
        )

        prompt = generate_subtask_prompt(
            spec_dir=self.spec_dir,
            project_dir=self.project_dir,
            subtask=subtask,
            phase=phase or {},
            attempt_count=attempt_count,
            recovery_hints=recovery_hints,
        )

        # Load file context
        context = load_subtask_context(self.spec_dir, self.project_dir, subtask)
        if context.get("patterns") or context.get("files_to_modify"):
            prompt += "\n\n" + format_context_for_prompt(context)

        # Run session
        from agents.session import run_agent_session

        async with client:
            status, _response = await run_agent_session(
                client, prompt, self.spec_dir, verbose=False
            )

        return status != "error"

    def _load_plan(self) -> dict[str, Any] | None:
        """Load the implementation plan."""
        plan_path = self.spec_dir / "implementation_plan.json"
        if not plan_path.exists():
            return None
        try:
            with open(plan_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _find_phase_for_subtask(
        self, plan: dict[str, Any], subtask_id: str
    ) -> dict[str, Any]:
        """Find the phase containing the given subtask."""
        for phase in plan.get("phases", []):
            for subtask in phase.get("subtasks", []):
                if subtask.get("id") == subtask_id:
                    return phase
        return {}

    def _update_task_status(
        self, subtask_id: str, status: str, worker_id: str
    ) -> None:
        """Update the task status in the implementation plan and swarm state."""
        plan_path = self.spec_dir / "implementation_plan.json"
        if not plan_path.exists():
            return

        try:
            with FileLock(plan_path, timeout=5.0):
                with open(plan_path) as f:
                    plan = json.load(f)

                for phase in plan.get("phases", []):
                    for subtask in phase.get("subtasks", []):
                        if subtask.get("id") == subtask_id:
                            subtask["status"] = status
                            break

                # Atomic write: temp file + rename
                fd, tmp_path = tempfile.mkstemp(
                    dir=plan_path.parent,
                    prefix=f".{plan_path.name}.tmp.",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(plan, f, indent=2)
                    os.replace(tmp_path, plan_path)
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    raise
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"Failed to update subtask {subtask_id} status to {status}: {e}"
            )

        self._write_swarm_state()

    async def _log_event(
        self, subtask_id: str, worker_id: str, message: str
    ) -> None:
        """Log a swarm event via task_logger, serializing concurrent writes."""
        if self.task_logger is None:
            return
        async with self._logger_lock:
            # Extract session number from worker_id (e.g. "worker-1" -> 1)
            try:
                session_num = int(worker_id.split("-")[-1])
            except (ValueError, IndexError):
                session_num = 0
            self.task_logger.set_session(session_num)
            self.task_logger.set_subtask(subtask_id)
            self.task_logger.log_info(message)
            self.task_logger.set_subtask(None)

    def _write_swarm_state(self) -> None:
        """Write current swarm state to swarm_state.json for frontend monitoring."""
        # Build tasks map from implementation plan
        tasks_map: dict[str, dict[str, Any]] = {}
        plan = self._load_plan()
        total_tasks = 0
        completed_tasks = 0

        if plan:
            for phase in plan.get("phases", []):
                for subtask in phase.get("subtasks", []):
                    sid = subtask.get("id", "")
                    st = subtask.get("status", "pending")
                    assigned = None
                    for w in self._workers:
                        if w.current_task == sid:
                            assigned = w.id
                            break
                    tasks_map[sid] = {
                        "status": st,
                        "assigned_to": assigned,
                    }
                    total_tasks += 1
                    if st == "completed":
                        completed_tasks += 1

        state = {
            "workers": [
                {
                    "id": w.id,
                    "status": w.status,
                    "current_task": w.current_task,
                    "tasks_completed": w.tasks_completed,
                }
                for w in self._workers
            ],
            "tasks": tasks_map,
            "started_at": self._started_at,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
        }

        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to write swarm state: {e}")
