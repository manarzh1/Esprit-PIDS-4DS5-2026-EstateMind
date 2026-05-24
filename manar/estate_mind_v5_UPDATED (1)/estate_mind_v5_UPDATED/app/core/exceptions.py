"""app/core/exceptions.py — Exceptions personnalisees."""
class EstateMindError(Exception):
    pass

class AgentUnavailableError(EstateMindError):
    def __init__(self, agent: str, error: str = ""):
        self.agent = agent
        super().__init__(f"Agent {agent} unavailable: {error}")

class PipelineTimeoutError(EstateMindError):
    pass
