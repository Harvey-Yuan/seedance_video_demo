"""向后兼容：旧代码 `from .pipeline import run_pipeline` 仍可用。"""

from .pipeline_agents import run_full_pipeline as run_pipeline

__all__ = ["run_pipeline"]
