"""
agents/orchestrator_agent.py
----------------------------
Root orchestrator agent for the qextract multi-agent pipeline.

This is the top-level agent that coordinates:
1. PDF → page image conversion
2. Parallel text + visual extraction per page
3. Merging and cross-page continuation handling

Exports `root_agent` for ADK discovery.
"""

from __future__ import annotations

from google.adk.agents import Agent

from agents.config import get_model
from tools.pdf_to_pages import convert_pdf_to_pages
from tools.crop_image import crop_region


# ── Root Agent (for ADK web UI / CLI) ────────────────────────────────────────
root_agent = Agent(
    name="qextract_orchestrator",
    model=get_model(),
    description=(
        "Root orchestrator for the qextract exam question extraction "
        "pipeline. Upload a PDF or image of an exam paper and this agent "
        "will extract all questions with text, options, and visual elements."
    ),
    instruction="""\
You are the orchestrator for an exam question extraction system.

When given a PDF file path or image path:

1. If the input is a PDF, use the `convert_pdf_to_pages` tool to convert it to page images.
2. For each page image, analyze it to extract:
   - All questions with their text (English and Hindi if present)
   - All visual elements (diagrams, figures, equations, maps, shapes) with bounding boxes
3. Use the `crop_region` tool to crop each detected visual element from the page image.
4. Combine all results into a final structured JSON.

IMPORTANT RULES:
- Extract ALL questions from every page
- Detect images, equations, maps, and shapes within questions
- Handle questions that continue across pages
- Hindi text: extract only if present, otherwise set to null
- Preserve mathematical symbols exactly: x², H₂O, √, ∫, ∞, α, β, γ, ≤, ≥, ±, Δ

Return the final result as a JSON array of questions.
""",
    tools=[convert_pdf_to_pages, crop_region],
)
