"""Backward compatibility: legacy `from .pipeline import run_pipeline` still works."""

from .pipeline_agents import run_full_pipeline as run_pipeline

__all__ = ["run_pipeline"]
