"""
agents/__init__.py
------------------
ADK agent package for the qextract multi-agent pipeline.

Exports the root_agent for ADK discovery, plus the run_pipeline()
function for server/CLI usage.
"""

from agents.orchestrator_agent import root_agent  # noqa: F401
from agents.pipeline import run_pipeline  # noqa: F401

__all__ = ["root_agent", "run_pipeline"]
