"""Agentic DMS orchestration package.

Backend tools are discovered dynamically from ``dms.agent.tools``.
"""

from dms.agent.orchestrator import is_agentic_enabled, runtime_probe

__all__ = ["is_agentic_enabled", "runtime_probe"]
