"""
agents/page_text_agent.py
-------------------------
LLM Agent: Extracts question text from a single exam page image.

Uses Gemini or GPT-4o-mini vision capabilities to OCR the page and
return structured JSON of all questions with their options.
"""

from __future__ import annotations

from google.adk.agents import Agent

from agents.config import get_model, load_instruction


def create_page_text_agent() -> Agent:
    """Create and return a PageTextAgent instance."""
    return Agent(
        name="page_text_agent",
        model=get_model(),
        description=(
            "Extracts all question text and options from a single "
            "exam page image using OCR and vision capabilities."
        ),
        instruction=load_instruction("text_extraction.md"),
    )
