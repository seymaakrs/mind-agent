"""Sales agent instruction prompts."""

from .reklam_uzmani import REKLAM_UZMANI_INSTRUCTIONS
from .manager import SALES_DIRECTOR_INSTRUCTIONS, SALES_MANAGER_INSTRUCTIONS
from .qualifier import QUALIFIER_INSTRUCTIONS

# Geriye donuk uyum alias'i.
META_AGENT_INSTRUCTIONS = REKLAM_UZMANI_INSTRUCTIONS

__all__ = [
    "REKLAM_UZMANI_INSTRUCTIONS",
    "META_AGENT_INSTRUCTIONS",  # deprecated alias
    "SALES_MANAGER_INSTRUCTIONS",
    "SALES_DIRECTOR_INSTRUCTIONS",  # Faz 1: Sales Director (yeni isim)
    "QUALIFIER_INSTRUCTIONS",  # Faz 5: Qualifier Agent
]

