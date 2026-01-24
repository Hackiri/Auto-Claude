#!/usr/bin/env python3
"""
Skills Generation Runner
========================

AI-powered Claude Code skills generation for projects.
Analyzes project architecture and generates contextual skills.

Usage:
    python auto-claude/runners/skills_runner.py --project /path/to/project
    python auto-claude/runners/skills_runner.py --project /path/to/project --model sonnet
    python auto-claude/runners/skills_runner.py --project /path/to/project --refresh
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add auto-claude to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Validate platform-specific dependencies BEFORE any imports that might
# trigger graphiti_core -> real_ladybug -> pywintypes import chain (ACS-253)
from core.dependency_validator import validate_platform_dependencies

validate_platform_dependencies()

# Load .env file with centralized error handling
from cli.utils import import_dotenv

load_dotenv = import_dotenv()

env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from client import create_client
from phase_config import get_thinking_budget, resolve_model_id
from ui import print_status, print_header


class SkillsGenerator:
    """Generates Claude Code skills using AI agents."""

    def __init__(
        self,
        project_dir: Path,
        output_dir: Path | None = None,
        model: str = "sonnet",
        thinking_level: str = "medium",
        max_skills: int = 8,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.output_dir = Path(output_dir) if output_dir else self.project_dir / ".auto-claude" / "skills"
        self.model = model
        self.thinking_level = thinking_level
        self.thinking_budget = get_thinking_budget(thinking_level)
        self.max_skills = max_skills
        self.prompts_dir = Path(__file__).parent.parent / "prompts"

    async def run(self) -> bool:
        """Run the skills generation process."""
        print_header("Skills Generation")
        print_status(f"Project: {self.project_dir}", "info")
        print_status(f"Output: {self.output_dir}", "info")
        print_status(f"Model: {self.model} (thinking: {self.thinking_level})", "info")
        print()

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Note: AI will explore project directly, no project_index.json required

        # Load prompt
        prompt_path = self.prompts_dir / "skills_generator.md"
        if not prompt_path.exists():
            print_status(f"Prompt not found: {prompt_path}", "error")
            print_status("SKILLS_GENERATION_ERROR:Prompt not found", "error")
            return False

        prompt = prompt_path.read_text(encoding="utf-8")

        # Add context to prompt
        prompt += f"\n\n---\n\n**Output Directory**: {self.output_dir}\n"
        prompt += f"**Project Directory**: {self.project_dir}\n"
        prompt += f"**Max Skills**: {self.max_skills}\n"

        # Run the agent
        print_status("Analyzing project architecture...", "info")
        print("SKILLS_GENERATION_PROGRESS:analyzing:10")

        success, response = await self._run_agent(prompt)

        if not success:
            print_status(f"Skills generation failed: {response}", "error")
            print(f"SKILLS_GENERATION_ERROR:{response}")
            return False

        # Validate output
        output_file = self.output_dir / "generated_skills.json"
        if not output_file.exists():
            print_status("Skills output file not created by agent", "error")
            print("SKILLS_GENERATION_ERROR:Output file not created")
            return False

        # Validate JSON
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                skills_data = json.load(f)

            skills = skills_data.get("skills", [])
            if not skills:
                print_status("No skills generated", "warning")
                print("SKILLS_GENERATION_ERROR:No skills generated")
                return False

            # Emit completion marker with skill count
            print_status(f"Generated {len(skills)} skills", "success")
            print(f"SKILLS_GENERATION_COMPLETE:{len(skills)}")

            # Print summary
            print()
            print_header("Generated Skills")
            for i, skill in enumerate(skills, 1):
                print(f"  {i}. {skill.get('name', 'unnamed')}")
                print(f"     {skill.get('description', 'No description')[:80]}")

            return True

        except json.JSONDecodeError as e:
            print_status(f"Invalid JSON in output: {e}", "error")
            print(f"SKILLS_GENERATION_ERROR:Invalid JSON: {e}")
            return False

    async def _run_agent(self, prompt: str) -> tuple[bool, str]:
        """Run the Claude agent with the given prompt."""
        print("SKILLS_GENERATION_PROGRESS:generating:30")

        client = create_client(
            self.project_dir,
            self.output_dir,
            resolve_model_id(self.model),
            max_thinking_tokens=self.thinking_budget,
        )

        try:
            async with client:
                await client.query(prompt)

                response_text = ""
                tool_count = 0
                # Track progress: 30% start, 90% before completion
                # Progress increases with each tool use (simulating work done)
                base_progress = 30
                max_progress = 90  # Leave room for final completion

                async for msg in client.receive_response():
                    msg_type = type(msg).__name__

                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            block_type = type(block).__name__
                            if block_type == "TextBlock" and hasattr(block, "text"):
                                response_text += block.text
                                print(block.text, end="", flush=True)
                            elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                                tool_count += 1
                                # Calculate progress based on tool usage
                                # Assume ~10 tool calls for a typical generation
                                progress = min(
                                    max_progress,
                                    base_progress + (tool_count * 6)  # ~6% per tool use
                                )
                                print(f"\n[Tool: {block.name}]", flush=True)
                                print(f"SKILLS_GENERATION_PROGRESS:generating:{progress}")

                print()
                print("SKILLS_GENERATION_PROGRESS:finalizing:95")
                print("SKILLS_GENERATION_PROGRESS:complete:100")
                return True, response_text

        except Exception as e:
            return False, str(e)


async def run_skills_generation(
    project_dir: Path,
    output_dir: Path | None = None,
    model: str = "sonnet",
    thinking_level: str = "medium",
    max_skills: int = 8,
    refresh: bool = False,
) -> bool:
    """
    Run skills generation.

    Args:
        project_dir: Path to the project
        output_dir: Output directory for skills (default: project/.auto-claude/skills)
        model: Model to use (haiku, sonnet, opus)
        thinking_level: Thinking level (none, low, medium, high, ultrathink)
        max_skills: Maximum number of skills to generate
        refresh: Force regeneration even if skills exist

    Returns:
        True if generation succeeded
    """
    output = output_dir or project_dir / ".auto-claude" / "skills"

    # Check for existing skills if not refreshing
    output_file = Path(output) / "generated_skills.json"
    if not refresh and output_file.exists():
        print_status("Skills already exist. Use --refresh to regenerate.", "info")
        print("SKILLS_GENERATION_SKIP:existing")
        return True

    generator = SkillsGenerator(
        project_dir=project_dir,
        output_dir=output,
        model=model,
        thinking_level=thinking_level,
        max_skills=max_skills,
    )

    return await generator.run()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI-powered Claude Code skills generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for skills files (default: project/.auto-claude/skills)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="sonnet",
        help="Model to use (haiku, sonnet, opus, or full model ID)",
    )
    parser.add_argument(
        "--thinking-level",
        type=str,
        default="medium",
        choices=["none", "low", "medium", "high", "ultrathink"],
        help="Thinking level for extended reasoning (default: medium)",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=8,
        help="Maximum number of skills to generate (default: 8)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force regeneration even if skills exist",
    )

    args = parser.parse_args()

    # Validate project directory
    project_dir = args.project.resolve()
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        sys.exit(1)

    try:
        success = asyncio.run(
            run_skills_generation(
                project_dir=project_dir,
                output_dir=args.output,
                model=args.model,
                thinking_level=args.thinking_level,
                max_skills=args.max_skills,
                refresh=args.refresh,
            )
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSkills generation interrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
