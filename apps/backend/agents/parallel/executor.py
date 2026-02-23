"""
Parallel Executor
=================

Orchestrates parallel execution of sub-agents for concurrent subtask processing.
This is the main entry point for running multiple subtasks simultaneously.
"""

import asyncio
import logging
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.client import create_client
from prompt_generator import (
    format_context_for_prompt,
    generate_subtask_prompt,
    load_subtask_context,
)
from recovery import RecoveryManager
from ui import highlight, print_key_value, print_status

from .aggregator import ParallelResults, aggregate_results
from .dependency import DependencyAnalyzer
from .mcp_fetcher import MCPContext, MCPInfoFetcher
from .subagent import SubagentConfig, SubagentResult, SubagentStatus

logger = logging.getLogger(__name__)


# Maximum concurrent sub-agents to prevent resource exhaustion
MAX_CONCURRENT_SUBAGENTS = int(os.environ.get("MAX_CONCURRENT_SUBAGENTS", "4"))


@dataclass
class ParallelConfig:
    """Configuration for parallel execution."""

    # Maximum concurrent sub-agents
    max_concurrent: int = MAX_CONCURRENT_SUBAGENTS

    # Enable/disable parallel execution
    enabled: bool = True

    # MCP servers to enable for sub-agents
    mcp_servers: list[str] = field(default_factory=lambda: ["context7", "graphiti"])

    # Whether to fetch MCP context before execution
    fetch_mcp_context: bool = True

    # Extended thinking budget per sub-agent
    max_thinking_tokens: int | None = None

    # Timeout per sub-agent in seconds
    timeout_seconds: int = 600

    # Model to use for sub-agents (inherits from parent if not set)
    model: str | None = None

    # Whether to stop all sub-agents if one fails
    fail_fast: bool = False


class ParallelExecutor:
    """
    Orchestrates parallel execution of sub-agents.

    Usage:
        executor = ParallelExecutor(project_dir, spec_dir, config)
        results = await executor.execute_parallel(subtasks, plan)
    """

    def __init__(
        self,
        project_dir: Path,
        spec_dir: Path,
        config: ParallelConfig | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        recovery_manager: RecoveryManager | None = None,
    ):
        """
        Initialize the parallel executor.

        Args:
            project_dir: Root directory of the project
            spec_dir: Directory containing the spec
            config: Parallel execution configuration
            model: Claude model to use
            recovery_manager: Optional recovery manager for tracking
        """
        self.project_dir = project_dir
        self.spec_dir = spec_dir
        self.config = config or ParallelConfig()
        self.model = self.config.model or model
        self.recovery_manager = recovery_manager or RecoveryManager(
            spec_dir, project_dir
        )

        # MCP fetcher for context gathering
        self.mcp_fetcher = MCPInfoFetcher(str(project_dir), str(spec_dir))

        # Dependency analyzer (set when executing)
        self._dependency_analyzer: DependencyAnalyzer | None = None

        # Semaphore for concurrency control
        self._semaphore: asyncio.Semaphore | None = None

        # Cancel flag for fail-fast mode
        self._cancel_requested = False

        # Progress callback
        self._on_progress: Callable[[str, SubagentStatus], None] | None = None

    def set_progress_callback(self, callback: Callable[[str, SubagentStatus], None]):
        """Set callback to receive progress updates."""
        self._on_progress = callback

    async def execute_parallel(
        self,
        subtasks: list[dict],
        plan: dict,
        phase: dict | None = None,
        session_num: int = 1,
    ) -> ParallelResults:
        """
        Execute subtasks in parallel where possible.

        Args:
            subtasks: List of subtask dictionaries from implementation plan
            plan: Full implementation plan for dependency analysis
            phase: Optional phase containing these subtasks
            session_num: Current session number for tracking

        Returns:
            ParallelResults with aggregated outcomes
        """
        if not subtasks:
            return ParallelResults(
                batch_id=str(uuid.uuid4()),
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )

        batch_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        print_status(f"Starting parallel execution batch: {batch_id}", "progress")
        print_key_value("Subtasks", str(len(subtasks)))
        print_key_value("Max concurrent", str(self.config.max_concurrent))

        # Initialize dependency analyzer
        self._dependency_analyzer = DependencyAnalyzer(plan)

        # Initialize semaphore
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Reset cancel flag
        self._cancel_requested = False

        # Create configs for each subtask
        configs = [SubagentConfig.from_subtask(subtask, phase) for subtask in subtasks]

        # Fetch MCP context if enabled
        mcp_context: MCPContext | None = None
        if self.config.fetch_mcp_context:
            feature_desc = plan.get("feature", "Implementation")
            print_status("Fetching MCP context for parallel execution...", "progress")
            mcp_context = await self.mcp_fetcher.fetch_all_context(
                subtask_description=feature_desc,
                feature_name=feature_desc,
            )
            if mcp_context.fetch_results:
                successful = sum(1 for r in mcp_context.fetch_results if r.success)
                print_status(
                    f"MCP context: {successful}/{len(mcp_context.fetch_results)} sources",
                    "success" if successful > 0 else "warning",
                )

        # Group subtasks by parallelizability
        subtask_ids = [s.get("id", "") for s in subtasks if s.get("id")]
        parallel_groups = self._dependency_analyzer.get_parallel_groups(subtask_ids)

        print_key_value(
            "Parallel groups",
            ", ".join(f"[{len(g)}]" for g in parallel_groups),
        )

        # Execute groups sequentially, but subtasks within groups in parallel
        all_results: list[SubagentResult] = []
        completed_ids: set[str] = set()

        for group_idx, group in enumerate(parallel_groups):
            if self._cancel_requested:
                print_status("Execution cancelled", "warning")
                break

            group_size = len(group)
            print_status(
                f"Executing group {group_idx + 1}/{len(parallel_groups)} "
                f"({group_size} subtask{'s' if group_size > 1 else ''})",
                "progress",
            )

            # Get configs for this group
            group_configs = [c for c in configs if c.subtask_id in group]

            # Execute this group in parallel
            group_results = await self._execute_group(
                group_configs,
                subtasks,
                session_num,
                mcp_context,
            )

            all_results.extend(group_results)

            # Track completed for dependency resolution
            for result in group_results:
                if result.success:
                    completed_ids.add(result.subtask_id)

            # Check for fail-fast
            if self.config.fail_fast:
                failed = [r for r in group_results if not r.success]
                if failed:
                    print_status(
                        f"Fail-fast: stopping due to {len(failed)} failures",
                        "error",
                    )
                    self._cancel_requested = True
                    break

        # Aggregate results
        results = aggregate_results(batch_id, all_results, started_at)

        # Print summary
        print()
        print_status(
            f"Parallel batch complete: {results.completed_count}/{results.total_subtasks}",
            "success" if results.all_successful else "warning",
        )
        if results.has_conflicts:
            print_status(
                f"File conflicts detected: {', '.join(results.conflict_files[:5])}",
                "error",
            )

        return results

    async def _execute_group(
        self,
        configs: list[SubagentConfig],
        subtasks: list[dict],
        session_num: int,
        mcp_context: MCPContext | None,
    ) -> list[SubagentResult]:
        """Execute a group of subtasks in parallel."""
        tasks = []
        active_configs: list[SubagentConfig] = []

        for config in configs:
            # Find the full subtask dict
            subtask = next(
                (s for s in subtasks if s.get("id") == config.subtask_id),
                None,
            )
            if not subtask:
                continue

            active_configs.append(config)
            task = self._execute_single(config, subtask, session_num, mcp_context)
            tasks.append(task)

        if not tasks:
            return []

        # Execute all tasks in this group concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        # Use active_configs (not configs) to maintain 1:1 index mapping with tasks
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                config = active_configs[i]
                failed_result = SubagentResult(
                    subtask_id=config.subtask_id,
                    config=config,
                )
                failed_result.mark_failed(str(result))
                final_results.append(failed_result)
            else:
                final_results.append(result)

        return final_results

    async def _execute_single(
        self,
        config: SubagentConfig,
        subtask: dict,
        session_num: int,
        mcp_context: MCPContext | None,
    ) -> SubagentResult:
        """Execute a single subtask with semaphore control."""
        result = SubagentResult(
            subtask_id=config.subtask_id,
            config=config,
        )

        async with self._semaphore:
            if self._cancel_requested:
                result.mark_cancelled()
                return result

            result.mark_running()

            # Notify progress
            if self._on_progress:
                self._on_progress(config.subtask_id, SubagentStatus.RUNNING)

            print(f"  {highlight(config.subtask_id)}: Starting...")

            try:
                # Capture git state
                from agents.utils import get_commit_count, get_latest_commit

                result.commit_before = get_latest_commit(self.project_dir)
                commit_count_before = get_commit_count(self.project_dir)

                # Generate prompt for this subtask
                prompt = generate_subtask_prompt(
                    spec_dir=self.spec_dir,
                    project_dir=self.project_dir,
                    subtask=subtask,
                    phase={"name": config.phase_name, "phase": config.phase_number}
                    if config.phase_name
                    else {},
                    attempt_count=self.recovery_manager.get_attempt_count(
                        config.subtask_id
                    ),
                    recovery_hints=self.recovery_manager.get_recovery_hints(
                        config.subtask_id
                    ),
                )

                # Add file context
                context = load_subtask_context(self.spec_dir, self.project_dir, subtask)
                if context.get("patterns") or context.get("files_to_modify"):
                    prompt += "\n\n" + format_context_for_prompt(context)

                # Add MCP context if available
                if mcp_context:
                    mcp_prompt = mcp_context.to_prompt_context()
                    if mcp_prompt:
                        prompt += (
                            "\n\n## Additional Context (from MCP)\n\n" + mcp_prompt
                        )

                # Create client for this sub-agent
                client = create_client(
                    self.project_dir,
                    self.spec_dir,
                    self.model,
                    agent_type="coder",
                    max_thinking_tokens=self.config.max_thinking_tokens,
                )

                # Run agent session with timeout
                from agents.session import run_agent_session
                from task_logger import LogPhase

                async with client:
                    try:
                        status, response, _error_info = await asyncio.wait_for(
                            run_agent_session(
                                client,
                                prompt,
                                self.spec_dir,
                                verbose=False,
                                phase=LogPhase.CODING,
                            ),
                            timeout=config.timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        result.mark_failed(f"Timeout after {config.timeout_seconds}s")
                        return result

                # Check git state after execution
                result.commit_after = get_latest_commit(self.project_dir)
                commit_count_after = get_commit_count(self.project_dir)
                result.commits_made = commit_count_after - commit_count_before

                # Determine success based on status
                success = status in ("complete", "continue")
                result.mark_completed(success, response)

                # Record attempt
                self.recovery_manager.record_attempt(
                    subtask_id=config.subtask_id,
                    session=session_num,
                    success=success,
                    approach=f"Parallel execution: {config.subtask_description[:100]}",
                )

                # Track good commit
                if result.commit_after and result.commit_after != result.commit_before:
                    self.recovery_manager.record_good_commit(
                        result.commit_after, config.subtask_id
                    )

                print(
                    f"  {highlight(config.subtask_id)}: "
                    f"{'Done' if success else 'Failed'} "
                    f"({result.commits_made} commits)"
                )

            except Exception as e:
                logger.exception(f"Sub-agent failed for {config.subtask_id}")
                result.mark_failed(str(e))
                print(f"  {highlight(config.subtask_id)}: Error - {str(e)[:50]}")

            # Notify progress
            if self._on_progress:
                self._on_progress(config.subtask_id, result.status)

            return result

    def cancel(self):
        """Request cancellation of parallel execution."""
        self._cancel_requested = True


async def run_parallel_subtasks(
    project_dir: Path,
    spec_dir: Path,
    subtasks: list[dict],
    plan: dict,
    model: str = "claude-sonnet-4-5-20250929",
    max_concurrent: int = MAX_CONCURRENT_SUBAGENTS,
) -> ParallelResults:
    """
    Convenience function to run subtasks in parallel.

    Args:
        project_dir: Project root directory
        spec_dir: Spec directory
        subtasks: List of subtask dictionaries
        plan: Full implementation plan
        model: Claude model to use
        max_concurrent: Maximum concurrent sub-agents

    Returns:
        ParallelResults with execution outcomes
    """
    config = ParallelConfig(max_concurrent=max_concurrent)
    executor = ParallelExecutor(project_dir, spec_dir, config, model)
    return await executor.execute_parallel(subtasks, plan)
