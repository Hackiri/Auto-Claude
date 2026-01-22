"""
Parallel Execution Module
=========================

Provides parallel sub-agent execution capabilities for the Auto-Claude build system.
This module enables running multiple independent subtasks concurrently when they:
1. Have no dependencies on each other
2. Don't modify overlapping files
3. Are marked as parallel_safe in the implementation plan

Key components:
- ParallelExecutor: Orchestrates parallel sub-agent execution
- SubagentConfig: Configuration for individual sub-agents
- ParallelResults: Aggregated results from parallel execution
- DependencyAnalyzer: Determines which subtasks can run in parallel
"""

from .aggregator import ParallelResults, aggregate_results
from .dependency import DependencyAnalyzer, can_run_in_parallel
from .executor import ParallelConfig, ParallelExecutor
from .mcp_fetcher import MCPInfoFetcher
from .subagent import SubagentConfig, SubagentResult

__all__ = [
    "ParallelExecutor",
    "ParallelConfig",
    "DependencyAnalyzer",
    "can_run_in_parallel",
    "SubagentConfig",
    "SubagentResult",
    "ParallelResults",
    "aggregate_results",
    "MCPInfoFetcher",
]
