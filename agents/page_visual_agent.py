"""
agents/page_visual_agent.py
---------------------------
LLM Agent: Detects visual elements (diagrams, figures, charts, etc.)
on a single exam page image and returns their bounding boxes.
"""

from __future__ import annotations

from google.adk.agents import Agent

from agents.config import get_model, load_instruction


def create_page_visual_agent() -> Agent:
    """Create and return a PageVisualAgent instance."""
    return Agent(
        name="page_visual_agent",
        model=get_model(),
        description=(
            "Detects all visual elements (diagrams, figures, charts, "
            "graphs, maps, shapes, equations-as-images) on a single "
            "exam page image and returns their bounding-box coordinates."
        ),
        instruction=load_instruction("visual_detection.md"),
    )
