"""Sales agentlari (Reklam Uzmani, Sales Manager/Analyst, ileride: LinkedIn, Clay, IG DM, Takip, Itiraz)."""

from src.agents.sales.reklam_uzmani_agent import create_reklam_uzmani_agent
from src.agents.sales.sales_analyst_agent import create_sales_analyst_agent

# Geriye donuk uyum alias'i — eski kodlar create_meta_agent kullaniyorsa kirilmasin.
create_meta_agent = create_reklam_uzmani_agent

__all__ = ["create_reklam_uzmani_agent", "create_sales_analyst_agent", "create_meta_agent"]
