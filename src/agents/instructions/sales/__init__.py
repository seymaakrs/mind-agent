"""Sales agent instructions package."""
from __future__ import annotations

from src.agents.instructions.sales.clay import CLAY_AGENT_INSTRUCTIONS
from src.agents.instructions.sales.ig_dm import IG_DM_AGENT_INSTRUCTIONS
from src.agents.instructions.sales.linkedin import LINKEDIN_AGENT_INSTRUCTIONS
from src.agents.instructions.sales.meta import META_LEAD_AGENT_INSTRUCTIONS
from src.agents.instructions.sales.query import SALES_QUERY_AGENT_INSTRUCTIONS

__all__ = [
    "SALES_QUERY_AGENT_INSTRUCTIONS",
    "CLAY_AGENT_INSTRUCTIONS",
    "IG_DM_AGENT_INSTRUCTIONS",
    "LINKEDIN_AGENT_INSTRUCTIONS",
    "META_LEAD_AGENT_INSTRUCTIONS",
]
