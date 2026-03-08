"""
agents/__init__.py
------------------
Exports the run_pipeline function for the core programmatic flow.
The single agent architecture calls the LLM directly within the pipeline.
"""

from agents.pipeline import run_pipeline

__all__ = ["run_pipeline"]
