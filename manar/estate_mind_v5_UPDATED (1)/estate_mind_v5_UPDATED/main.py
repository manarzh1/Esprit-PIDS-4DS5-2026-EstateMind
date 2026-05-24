"""
main.py — Estate Mind CHAT — FastAPI
=====================================
Serveur dédié au chat IA.
Port : 8000
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.engine import engine
from app.services.nlp.naive_bayes import get_classifier
from sqlalchemy import text

log = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("estate_mind_chat_starting", version=settings.app_version)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM bo6_tracking.chat_sessions LIMIT 1"))
        log.info("supabase_connected", schema="bo6_tracking")
    except Exception as e:
        log.warning("supabase_check_failed", error=str(e))

    clf = get_classifier()
    log.info("nb_classifier_ready", vocab_size=clf.vocab_size, trained=clf.trained)
    yield
    await engine.dispose()
    log.info("estate_mind_chat_stopped")


app = FastAPI(
    title="Estate Mind — Chat BO6",
    description="Interface de chat immobilier intelligent — Tunisie",
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

# API chat uniquement
app.include_router(api_router)

# Frontend chat
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/", tags=["Root"])
async def root():
    return RedirectResponse(url="/frontend/index.html")


@app.get("/chat", tags=["Frontend"])
async def go_chat():
    return RedirectResponse(url="/frontend/index.html")