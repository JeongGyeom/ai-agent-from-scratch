"""Run the Chapter 4 ReAct agent example from the command line."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

from dotenv import load_dotenv


def find_project_root() -> Path:
    """Find this checkout so the script also works from another directory."""
    script_dir = Path(__file__).resolve().parent
    for path in (script_dir, *script_dir.parents):
        if (path / "pyproject.toml").is_file() and (path / "scratch_agents").is_dir():
            return path
    raise RuntimeError("Could not find the project root (pyproject.toml and scratch_agents).")


async def run(prompt: str, model_name: str) -> None:
    project_root = find_project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    load_dotenv(project_root / ".env")

    from scratch_agents import Agent, LlmClient
    from scratch_agents.tools import calculator, search_web

    agent = Agent(
        model=LlmClient(model=model_name),
        tools=[calculator, search_web],
        instructions="You are a helpful assistant",
    )
    result = await agent.run(prompt)
    print(result.output if result.output is not None else "Agent reached the step limit without a final answer.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Chapter 4 ReAct agent example.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="What is 1234 * 5678?",
        help="Question to send to the agent (defaults to the notebook example).",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.4-mini",
        help="LiteLLM model name (default: gpt-5.4-mini).",
    )
    args = parser.parse_args()
    asyncio.run(run(args.prompt, args.model))


if __name__ == "__main__":
    main()
