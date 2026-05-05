"""
app/services/agents/agent_clients.py
======================================
Appels HTTP vers les agents BO1-BO5.
BO6 est un orchestrateur PUR — ne touche pas a PostgreSQL.
"""
import time
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
settings = get_settings()

def _fallback(agent: str, error: str) -> dict:
    return {"agent": agent, "available": False, "error": error, "total_listings": 0,
            "message": f"Agent {agent} temporairement indisponible."}

async def _post(url: str, payload: dict, agent: str, timeout: float = None) -> tuple:
    t = timeout or float(settings.agent_timeout)
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=t, write=5.0, pool=2.0)) as client:
            r = await client.post(url, json=payload)
            ms = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                return r.json(), ms
            return _fallback(agent, f"HTTP {r.status_code}"), ms
    except httpx.TimeoutException:
        ms = int((time.monotonic() - t0) * 1000)
        return _fallback(agent, "timeout"), ms
    except httpx.ConnectError:
        ms = int((time.monotonic() - t0) * 1000)
        return _fallback(agent, "connection_refused"), ms
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return _fallback(agent, str(e)), ms

async def call_bo1(query="", session_id="", city=None, **kw) -> tuple:
    return await _post(f"{settings.agent_bo1_url}/collect", {"query": query, "session_id": session_id, "city": city}, "BO1")

async def call_bo2(query="", session_id="", city=None, transaction_type=None, **kw) -> tuple:
    return await _post(f"{settings.agent_bo2_url}/analyse", {"query": query, "session_id": session_id, "city": city, "transaction_type": transaction_type}, "BO2")

async def call_bo3(query="", session_id="", city=None, transaction_type=None, surface_m2=None, bedrooms=None, **kw) -> tuple:
    return await _post(f"{settings.agent_bo3_url}/predict", {"query": query, "session_id": session_id, "city": city, "transaction_type": transaction_type, "surface_m2": surface_m2, "bedrooms": bedrooms}, "BO3")

async def call_bo4(query="", session_id="", city=None, budget_max=None, **kw) -> tuple:
    return await _post(f"{settings.agent_bo4_url}/score", {"query": query, "session_id": session_id, "city": city, "budget_max": budget_max}, "BO4")

async def call_bo5(query="", session_id="", city=None, property_type=None, **kw) -> tuple:
    return await _post(f"{settings.agent_bo5_url}/verify", {"query": query, "session_id": session_id, "city": city, "property_type": property_type}, "BO5")

async def check_all_agents() -> dict:
    results = {}
    for name, base_url in [("BO1", settings.agent_bo1_url), ("BO2", settings.agent_bo2_url),
                            ("BO3", settings.agent_bo3_url), ("BO4", settings.agent_bo4_url),
                            ("BO5", settings.agent_bo5_url)]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{base_url}/health")
                data = r.json() if r.status_code == 200 else {}
                results[name] = "ok" if data.get("status") == "ok" else "degraded"
        except Exception:
            results[name] = "unavailable"
    return results
