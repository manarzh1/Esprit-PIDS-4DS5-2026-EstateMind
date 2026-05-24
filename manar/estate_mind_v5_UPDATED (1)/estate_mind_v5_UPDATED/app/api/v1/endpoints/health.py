"""app/api/v1/endpoints/health.py — GET /api/v1/health"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.engine import get_db
from app.models.schemas import HealthResponse
from app.services.agents.agent_clients import check_all_agents
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        # Vérification sur le schéma bo6_tracking (Supabase)
        await db.execute(text("SELECT 1 FROM bo6_tracking.chat_sessions LIMIT 1"))
    except Exception:
        db_status = "error"
    agents = await check_all_agents()
    all_ok = db_status == "ok" and any("ok" in v for v in agents.values())
    return HealthResponse(
        status="ok" if all_ok else "degraded",
        version=settings.app_version,
        environment=settings.app_env,
        database=db_status,
        agents=agents,
        components={"nlp": "ok", "templates": "ok", "pdf": "ok"},
    )
