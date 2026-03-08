"""
agents/merger_agent.py
----------------------
LLM Agent: Merges text extraction + visual detection results,
handles cross-page question continuations, and coordinates
image cropping via the crop_region tool.
"""

from __future__ import annotations

from google.adk.agents import Agent

from agents.config import get_model, load_instruction
from tools.crop_image import crop_region


def create_merger_agent() -> Agent:
    """Create and return a MergerAgent instance."""
    return Agent(
        name="merger_agent",
        model=get_model(),
        description=(
            "Merges text extraction and visual detection results from "
            "exam pages. Handles cross-page question continuations and "
            "crops visual elements using the crop_region tool."
        ),
        instruction=load_instruction("merger.md"),
        tools=[crop_region],
    )
