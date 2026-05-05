"""
main.py — Estate Mind BO6 — FastAPI Application
================================================
Orchestrateur principal du systeme multi-agents Estate Mind.
Port : 8000

ARCHITECTURE :
  BO6 orchestre, ne lit PAS PostgreSQL directement (sauf tables BO6).
  Communication avec BO1-BO5 uniquement via HTTP JSON.
  Base de données : Supabase (schéma bo6_tracking).
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.engine import engine
from app.services.nlp.naive_bayes import get_classifier

log = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("estate_mind_starting", version=settings.app_version)

    # Vérification connexion Supabase (tables déjà créées via SQL Editor)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM bo6_tracking.chat_sessions LIMIT 1"))
        log.info("supabase_connected", schema="bo6_tracking")
    except Exception as e:
        log.warning("supabase_check_failed", error=str(e))

    # Pre-entrainer le classifieur NB
    clf = get_classifier()
    log.info("nb_classifier_ready", vocab_size=clf.vocab_size, trained=clf.trained)

    yield

    # Shutdown
    await engine.dispose()
    log.info("estate_mind_stopped")


app = FastAPI(
    title="Estate Mind BO6 — Orchestrateur",
    description="Plateforme Immobiliere Intelligente Tunisienne — Agent Orchestrateur",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes API
app.include_router(api_router)

# Frontend statique
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Estate Mind BO6",
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "chat": "/api/v1/chat",
        "health": "/api/v1/health",
        "frontend": "/frontend/index.html",
    }
