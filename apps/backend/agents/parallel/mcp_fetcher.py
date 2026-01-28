"""
MCP Information Fetcher
=======================

Fetches up-to-date information from MCP servers during planning and execution phases.
Supports parallel fetching from multiple sources for comprehensive context gathering.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPFetchResult:
    """Result from fetching information from an MCP server."""

    server_name: str
    query: str
    success: bool
    data: Any = None
    error: str | None = None
    fetch_time_ms: float = 0.0
    cached: bool = False


@dataclass
class MCPContext:
    """Aggregated context from multiple MCP sources."""

    # Documentation context (from context7)
    documentation: list[dict] = field(default_factory=list)

    # Memory context (from graphiti)
    patterns: list[str] = field(default_factory=list)
    gotchas: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)

    # Project tracking (from linear)
    related_issues: list[dict] = field(default_factory=list)
    team_context: str | None = None

    # Fetch metadata
    fetch_results: list[MCPFetchResult] = field(default_factory=list)
    total_fetch_time_ms: float = 0.0

    def to_prompt_context(self) -> str:
        """Format as context for agent prompts."""
        sections = []

        if self.documentation:
            sections.append("## Relevant Documentation")
            for doc in self.documentation[:5]:  # Limit to top 5
                title = doc.get("title", "Unknown")
                content = doc.get("content", "")[:500]
                sections.append(f"### {title}\n{content}")

        if self.patterns:
            sections.append("## Codebase Patterns (from memory)")
            for pattern in self.patterns[:10]:
                sections.append(f"- {pattern}")

        if self.gotchas:
            sections.append("## Known Gotchas (from memory)")
            for gotcha in self.gotchas[:5]:
                sections.append(f"- {gotcha}")

        if self.insights:
            sections.append("## Recent Insights (from memory)")
            for insight in self.insights[:5]:
                sections.append(f"- {insight}")

        if self.related_issues:
            sections.append("## Related Issues (from Linear)")
            for issue in self.related_issues[:5]:
                title = issue.get("title", "Unknown")
                status = issue.get("status", "unknown")
                sections.append(f"- [{status}] {title}")

        return "\n\n".join(sections) if sections else ""


class MCPInfoFetcher:
    """
    Fetches information from configured MCP servers.

    Supports:
    - Context7 for documentation lookups
    - Graphiti for memory/pattern retrieval
    - Linear for project tracking context

    All fetches happen in parallel when possible.
    """

    def __init__(
        self,
        project_dir: str,
        spec_dir: str | None = None,
    ):
        """
        Initialize the MCP info fetcher.

        Args:
            project_dir: Project root directory
            spec_dir: Optional spec directory for memory context
        """
        self.project_dir = project_dir
        self.spec_dir = spec_dir
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl_seconds = 300  # 5 minute cache

    def _is_context7_enabled(self) -> bool:
        """Check if Context7 MCP is enabled."""
        return os.environ.get("CONTEXT7_ENABLED", "true").lower() == "true"

    def _is_graphiti_enabled(self) -> bool:
        """Check if Graphiti is enabled for memory."""
        return os.environ.get("GRAPHITI_ENABLED", "false").lower() == "true"

    def _is_linear_enabled(self) -> bool:
        """Check if Linear MCP is enabled."""
        return bool(os.environ.get("LINEAR_API_KEY"))

    async def fetch_documentation(
        self, query: str, libraries: list[str] | None = None
    ) -> MCPFetchResult:
        """
        Fetch documentation using Context7 MCP.

        Args:
            query: Search query for documentation
            libraries: Optional list of library names to search

        Returns:
            MCPFetchResult with documentation data
        """
        if not self._is_context7_enabled():
            return MCPFetchResult(
                server_name="context7",
                query=query,
                success=False,
                error="Context7 not enabled",
            )

        start_time = datetime.now()

        try:
            # Context7 integration - search for relevant docs
            # This will be called via the MCP server in the agent session
            # For now, we just prepare the query structure
            result = MCPFetchResult(
                server_name="context7",
                query=query,
                success=True,
                data={
                    "query": query,
                    "libraries": libraries or [],
                    "ready_for_mcp": True,
                },
            )
            result.fetch_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result

        except Exception as e:
            logger.warning(f"Context7 fetch failed: {e}")
            return MCPFetchResult(
                server_name="context7",
                query=query,
                success=False,
                error=str(e),
                fetch_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def fetch_memory_context(self, subtask_description: str) -> MCPFetchResult:
        """
        Fetch memory context from Graphiti.

        Args:
            subtask_description: Description of the current subtask

        Returns:
            MCPFetchResult with memory data
        """
        if not self._is_graphiti_enabled():
            return MCPFetchResult(
                server_name="graphiti",
                query=subtask_description,
                success=False,
                error="Graphiti not enabled",
            )

        if not self.spec_dir:
            return MCPFetchResult(
                server_name="graphiti",
                query=subtask_description,
                success=False,
                error="No spec directory configured",
            )

        start_time = datetime.now()

        try:
            # Import here to avoid circular dependency
            from pathlib import Path

            from agents.memory_manager import get_graphiti_context

            context = await get_graphiti_context(
                Path(self.spec_dir),
                Path(self.project_dir),
                {"description": subtask_description},
            )

            result = MCPFetchResult(
                server_name="graphiti",
                query=subtask_description,
                success=True,
                data={"context": context} if context else {},
            )
            result.fetch_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result

        except Exception as e:
            logger.warning(f"Graphiti fetch failed: {e}")
            return MCPFetchResult(
                server_name="graphiti",
                query=subtask_description,
                success=False,
                error=str(e),
                fetch_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def fetch_linear_context(self, feature_description: str) -> MCPFetchResult:
        """
        Fetch related issues from Linear.

        Args:
            feature_description: Description of the feature being implemented

        Returns:
            MCPFetchResult with Linear data
        """
        if not self._is_linear_enabled():
            return MCPFetchResult(
                server_name="linear",
                query=feature_description,
                success=False,
                error="Linear not enabled",
            )

        start_time = datetime.now()

        try:
            # Linear context will be fetched via MCP during agent session
            result = MCPFetchResult(
                server_name="linear",
                query=feature_description,
                success=True,
                data={
                    "query": feature_description,
                    "ready_for_mcp": True,
                },
            )
            result.fetch_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result

        except Exception as e:
            logger.warning(f"Linear fetch failed: {e}")
            return MCPFetchResult(
                server_name="linear",
                query=feature_description,
                success=False,
                error=str(e),
                fetch_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    async def fetch_all_context(
        self,
        subtask_description: str,
        feature_name: str | None = None,
        libraries: list[str] | None = None,
    ) -> MCPContext:
        """
        Fetch context from all available MCP servers in parallel.

        Args:
            subtask_description: Current subtask description
            feature_name: Optional feature name for Linear context
            libraries: Optional libraries for documentation lookup

        Returns:
            MCPContext with aggregated data
        """
        # Create tasks for all enabled sources
        tasks = []

        if self._is_context7_enabled():
            tasks.append(
                (
                    "documentation",
                    self.fetch_documentation(subtask_description, libraries),
                )
            )

        if self._is_graphiti_enabled():
            tasks.append(("memory", self.fetch_memory_context(subtask_description)))

        if self._is_linear_enabled() and feature_name:
            tasks.append(("linear", self.fetch_linear_context(feature_name)))

        # Run all fetches in parallel
        context = MCPContext()

        if tasks:
            task_results = await asyncio.gather(
                *[task[1] for task in tasks],
                return_exceptions=True,
            )

            for i, (source_name, _) in enumerate(tasks):
                result = task_results[i]
                if isinstance(result, Exception):
                    context.fetch_results.append(
                        MCPFetchResult(
                            server_name=source_name,
                            query=subtask_description,
                            success=False,
                            error=str(result),
                        )
                    )
                else:
                    context.fetch_results.append(result)
                    if result.success and result.data:
                        # Process based on source
                        if source_name == "documentation":
                            context.documentation = result.data.get("docs", [])
                        elif source_name == "memory":
                            mem_context = result.data.get("context", "")
                            if mem_context:
                                # Parse memory context string
                                context.insights.append(mem_context)
                        elif source_name == "linear":
                            context.related_issues = result.data.get("issues", [])

        # Calculate total fetch time
        context.total_fetch_time_ms = sum(
            r.fetch_time_ms for r in context.fetch_results
        )

        return context


async def fetch_planning_context(
    project_dir: str,
    spec_dir: str,
    feature_description: str,
    tech_stack: list[str] | None = None,
) -> MCPContext:
    """
    Fetch comprehensive context for planning phase.

    This is the main entry point for gathering MCP context during planning.

    Args:
        project_dir: Project root directory
        spec_dir: Spec directory for memory
        feature_description: What feature is being planned
        tech_stack: Optional detected tech stack for documentation

    Returns:
        MCPContext with all available information
    """
    fetcher = MCPInfoFetcher(project_dir, spec_dir)
    return await fetcher.fetch_all_context(
        subtask_description=feature_description,
        feature_name=feature_description,
        libraries=tech_stack,
    )
