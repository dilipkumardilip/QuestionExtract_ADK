"""
agents/config.py
----------------
Central configuration for the multi-agent pipeline.

Supports dual model providers:
  - "openai"  → uses LiteLlm(model="openai/gpt-4o-mini")
  - "gemini"  → uses native "gemini-2.0-flash" string

Set MODEL_PROVIDER in .env to switch between them.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────────────────────────
_project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=_project_root / ".env", override=False)
load_dotenv(override=False)

# ── Model provider ───────────────────────────────────────────────────────────
MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "openai").lower().strip()

# ── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(os.getenv("IMAGES_OUTPUT_DIR", "images_output")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "pages").mkdir(parents=True, exist_ok=True)

# ── Instructions directory ───────────────────────────────────────────────────
INSTRUCTIONS_DIR: Path = _project_root / "instructions"


def get_model():
    """Return the appropriate model object based on MODEL_PROVIDER.

    Returns:
        For "gemini": the string "gemini-2.0-flash" (ADK native)
        For "openai": a LiteLlm wrapper around "openai/gpt-4o-mini"
    """
    if MODEL_PROVIDER == "gemini":
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set.\n"
                "Add it to your .env file:  GOOGLE_API_KEY=your_key_here"
            )
        return "gemini-2.0-flash"

    elif MODEL_PROVIDER == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set.\n"
                "Add it to your .env file:  OPENAI_API_KEY=your_key_here"
            )
        from google.adk.models.lite_llm import LiteLlm
        return LiteLlm(model="openai/gpt-4o-mini")

    else:
        raise ValueError(
            f"Unknown MODEL_PROVIDER='{MODEL_PROVIDER}'. "
            "Accepted values: 'openai', 'gemini'"
        )


def load_instruction(filename: str) -> str:
    """Load an instruction file from the instructions/ directory.

    Args:
        filename: Name of the instruction file (e.g. 'text_extraction.md')

    Returns:
        The file contents as a string.
    """
    path = INSTRUCTIONS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Instruction file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
