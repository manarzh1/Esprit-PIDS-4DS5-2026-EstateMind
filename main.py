"""
main.py — Estate Mind BO6 — FastAPI Application
================================================
Orchestrateur principal du systeme multi-agents Estate Mind.
Port : 8000
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
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
    log.info("estate_mind_starting", version=settings.app_version)
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
    log.info("estate_mind_stopped")


app = FastAPI(
    title="Estate Mind BO6 — Orchestrateur",
    description="Plateforme Immobiliere Intelligente Tunisienne",
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

app.include_router(api_router)

# Frontend : les deux interfaces depuis le même dossier
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/", tags=["Root"])
async def root():
    html = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>Estate Mind</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;
     display:flex;align-items:center;justify-content:center;min-height:100vh}
.w{text-align:center;padding:40px 20px}
.logo{font-size:52px;margin-bottom:14px}
h1{font-size:30px;font-weight:900;color:#fff;margin-bottom:6px}
.sub{color:#64748b;font-size:14px;margin-bottom:44px}
.cards{display:flex;gap:22px;justify-content:center;flex-wrap:wrap}
.card{background:#161b27;border:1px solid rgba(255,255,255,.08);border-radius:22px;
      padding:34px 30px;width:270px;text-decoration:none;color:inherit;
      transition:.22s;display:block}
.card:hover{border-color:#ff6b00;transform:translateY(-5px)}
.card-icon{font-size:38px;margin-bottom:16px}
.card-title{font-size:17px;font-weight:900;color:#fff;margin-bottom:9px}
.card-desc{font-size:13px;color:#64748b;line-height:1.65}
.badge{display:inline-block;margin-top:16px;padding:4px 13px;border-radius:999px;font-size:11px;font-weight:700}
.new{background:rgba(255,107,0,.15);color:#ff6b00}
.old{background:rgba(100,116,139,.15);color:#94a3b8}
.links{margin-top:36px;font-size:12px;color:#475569}
.links a{color:#3b82f6;text-decoration:none;margin:0 8px}
</style></head><body>
<div class="w">
  <div class="logo">🏠</div>
  <h1>Estate Mind BO6</h1>
  <p class="sub">Plateforme Immobilière Intelligente — Tunisie</p>
  <div class="cards">
    <a class="card" href="/frontend/dashboard.html">
      <div class="card-icon">🚀</div>
      <div class="card-title">Nouveau Dashboard</div>
      <div class="card-desc">Interface moderne avec chatbot IA flottant, historique DSO3 et KPI cards.</div>
      <span class="badge new">✨ Nouveau</span>
    </a>
    <a class="card" href="/frontend/index.html">
      <div class="card-icon">💬</div>
      <div class="card-title">Interface Classique</div>
      <div class="card-desc">Ancien chat BO6 avec suggestions rapides et état des agents BO1–BO5.</div>
      <span class="badge old">Version précédente</span>
    </a>
  </div>
  <p class="links">
    <a href="/docs">📖 Swagger</a>
    <a href="/api/v1/health">💚 Health</a>
    <a href="/redoc">📄 Redoc</a>
  </p>
</div></body></html>"""
    return HTMLResponse(content=html)


@app.get("/dashboard", tags=["Frontend"])
async def go_dashboard():
    return RedirectResponse(url="/frontend/dashboard.html")

@app.get("/chat", tags=["Frontend"])
async def go_chat():
    return RedirectResponse(url="/frontend/index.html")
