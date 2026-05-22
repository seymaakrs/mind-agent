"""Sales agent instruction prompts."""

from .reklam_uzmani import REKLAM_UZMANI_INSTRUCTIONS
from .ads_expert import ADS_EXPERT_INSTRUCTIONS
from .analyst import SALES_ANALYST_INSTRUCTIONS  # deprecated, kept for back-compat
from .manager import SALES_DIRECTOR_INSTRUCTIONS, SALES_MANAGER_INSTRUCTIONS

# Geriye donuk uyum alias'i.
META_AGENT_INSTRUCTIONS = REKLAM_UZMANI_INSTRUCTIONS

__all__ = [
    "ADS_EXPERT_INSTRUCTIONS",
    "REKLAM_UZMANI_INSTRUCTIONS",
    "META_AGENT_INSTRUCTIONS",  # deprecated alias
    "SALES_ANALYST_INSTRUCTIONS",  # deprecated
    "SALES_MANAGER_INSTRUCTIONS",
    "SALES_DIRECTOR_INSTRUCTIONS",  # Faz 1: Sales Director (yeni isim)
]

