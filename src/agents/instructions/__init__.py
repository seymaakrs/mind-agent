"""Agent instruction prompts — extracted for maintainability."""

from .marketing import MARKETING_AGENT_INSTRUCTIONS
from .analysis import ANALYSIS_AGENT_INSTRUCTIONS
from .orchestrator import build_orchestrator_instructions
from .image import IMAGE_AGENT_CORE_INSTRUCTIONS, DEFAULT_IMAGE_PERSONA
from .video import VIDEO_AGENT_CORE_INSTRUCTIONS, DEFAULT_VIDEO_PERSONA
from .customer import CUSTOMER_AGENT_INSTRUCTIONS

__all__ = [
    "MARKETING_AGENT_INSTRUCTIONS",
    "ANALYSIS_AGENT_INSTRUCTIONS",
    "build_orchestrator_instructions",
    "IMAGE_AGENT_CORE_INSTRUCTIONS",
    "DEFAULT_IMAGE_PERSONA",
    "VIDEO_AGENT_CORE_INSTRUCTIONS",
    "DEFAULT_VIDEO_PERSONA",
    "CUSTOMER_AGENT_INSTRUCTIONS",
]
