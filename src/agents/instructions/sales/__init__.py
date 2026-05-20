"""Sales agent instruction prompts."""

from .meta import META_AGENT_INSTRUCTIONS
from .analyst import SALES_ANALYST_INSTRUCTIONS  # deprecated, kept for back-compat
from .manager import SALES_MANAGER_INSTRUCTIONS

__all__ = [
    "META_AGENT_INSTRUCTIONS",
    "SALES_ANALYST_INSTRUCTIONS",  # deprecated
    "SALES_MANAGER_INSTRUCTIONS",
]
