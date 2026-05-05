"""app/services/agents/router.py — Dispatch intention vers agent."""
from app.services.agents import agent_clients

INTENT_TO_AGENT = {
    "price_estimation":    ("BO3", agent_clients.call_bo3),
    "investment_analysis": ("BO4", agent_clients.call_bo4),
    "location_analysis":   ("BO2", agent_clients.call_bo2),
    "legal_verification":  ("BO5", agent_clients.call_bo5),
    "report_generation":   ("BO2", agent_clients.call_bo2),
    "general_query":       ("BO1", agent_clients.call_bo1),
    "unknown":             ("BO1", agent_clients.call_bo1),
}

def get_agent_for_intent(intent: str) -> tuple:
    return INTENT_TO_AGENT.get(intent, ("BO1", agent_clients.call_bo1))
