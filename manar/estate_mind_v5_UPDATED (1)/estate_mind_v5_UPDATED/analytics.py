"""
analytics.py — Estate Mind ANALYTICS — FastAPI
================================================
Serveur dédié à l'historique et au dashboard XAI/NLP.
Port : 8001
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Depends, Query
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.engine import engine, get_db
from app.db.repositories.chat_repo import get_history
from app.models.schemas import HistoryResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

log = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("estate_mind_analytics_starting")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM bo6_tracking.chat_sessions LIMIT 1"))
        log.info("supabase_connected")
    except Exception as e:
        log.warning("supabase_check_failed", error=str(e))
    yield
    await engine.dispose()
    log.info("estate_mind_analytics_stopped")


app = FastAPI(
    title="Estate Mind — Analytics & XAI",
    description="Historique des interactions + Métriques NLP/XAI",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router analytics ──────────────────────────────────────────
analytics_router = APIRouter(prefix="/api/v1")


@analytics_router.get("/history", response_model=HistoryResponse, tags=["History"])
async def history(
    session_id: uuid.UUID | None = None,
    user_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retourne l'historique paginé des interactions."""
    return await get_history(
        db,
        session_id=session_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )


app.include_router(analytics_router)

# ── Frontend analytics ────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/", tags=["Root"])
async def root():
    return RedirectResponse(url="/frontend/dashboard_nlp.html")


@app.get("/analytics", tags=["Frontend"])
async def go_analytics():
    return RedirectResponse(url="/frontend/dashboard_nlp.html")