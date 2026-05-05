"""
AI-Powered Real Estate Platform — FastAPI Backend
Endpoints: /train, /analysis, /estimate, /map-data, /chat, /status
"""
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import httpx

# Import modules internes
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from core import sarima_engine, price_estimator

# ── État global ─────────────────────────────────────────────────────────────
_sarima_ready = False
_ml_ready = False
_sarima_last_results: dict | None = None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FRONTEND_DIR   = __import__("pathlib").Path(__file__).parent.parent.parent / "frontend"
DASHBOARD_DIR  = __import__("pathlib").Path(__file__).parent.parent.parent.parent.parent.parent / "estate_mind_static_site_v2" / "estate_mind_static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage: charger les données SARIMA au lancement
    global _sarima_ready
    try:
        sarima_engine.load_data()
        _sarima_ready = True
        print("✅ Données SARIMA chargées")
    except Exception as e:
        print(f"⚠️ SARIMA: {e}")
    yield


app = FastAPI(
    title="Immo Tunisia API",
    description="API de prévision et estimation immobilière en Tunisie",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir le frontend statique
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

# Servir le dashboard Estate Mind
if DASHBOARD_DIR.exists():
    app.mount("/dash", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard_static")


# ── Modèles Pydantic ─────────────────────────────────────────────────────────
class TrainRequest(BaseModel):
    gouvernorat: str = "Tunis"
    variable: str = "PRIX_M2_MEDIAN"
    p: int = 1
    d: int = 1
    q: int = 1
    P: int = 1
    D: int = 1
    Q: int = 0
    horizon: int = 6


class EstimateRequest(BaseModel):
    city: str
    surface: float
    bedrooms: float = 2
    bathrooms: float = 1
    budget: float = 0
    etage: float = 2
    equipment_score: float = 5


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Immo Tunisia API — voir /docs"}


@app.get("/dashboard")
def dashboard():
    return RedirectResponse(url="/dash/dashboard.html")


@app.get("/api/status")
def status():
    return {
        "sarima_ready": _sarima_ready,
        "ml_ready": _ml_ready,
        "gouvernorats": sarima_engine.get_gouvernorats() if _sarima_ready else [],
        "cities": price_estimator.get_cities() if _ml_ready else [],
        "ml_metrics": price_estimator.get_metrics() if _ml_ready else {},
    }


@app.post("/api/train")
def train_sarima(req: TrainRequest):
    """Lancer/récupérer une analyse SARIMA pour un gouvernorat."""
    global _sarima_last_results
    if not _sarima_ready:
        raise HTTPException(503, "Données SARIMA non chargées")
    try:
        results = sarima_engine.fit_and_forecast(
            gouvernorat=req.gouvernorat,
            variable=req.variable,
            order=(req.p, req.d, req.q),
            seasonal_order=(req.P, req.D, req.Q, 4),
            horizon=req.horizon,
        )
        _sarima_last_results = results
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(400, f"Erreur SARIMA: {e}")


@app.get("/api/analysis")
def get_analysis():
    """Récupérer les derniers résultats SARIMA."""
    if _sarima_last_results is None:
        raise HTTPException(404, "Aucune analyse disponible. Lancez /api/train d'abord.")
    return {"data": _sarima_last_results}


@app.get("/api/map-data")
def map_data():
    """Données prix par gouvernorat pour la carte choroplèthe."""
    if not _sarima_ready:
        raise HTTPException(503, "Données non chargées")
    try:
        summary = sarima_engine.get_all_gouvernorats_summary()
        return {"data": summary}
    except Exception as e:
        raise HTTPException(500, f"Erreur carte: {e}")


@app.post("/api/train-ml")
def train_ml(background_tasks: BackgroundTasks):
    """Lancer l'entraînement du modèle Random Forest en arrière-plan."""
    global _ml_ready

    def _train():
        global _ml_ready
        try:
            price_estimator.load_and_train()
            _ml_ready = True
            print("✅ Modèle ML prêt")
        except Exception as e:
            print(f"⚠️ ML: {e}")

    if not _ml_ready:
        background_tasks.add_task(_train)
        return {"message": "Entraînement ML démarré en arrière-plan"}
    return {"message": "Modèle déjà entraîné", "metrics": price_estimator.get_metrics()}


@app.post("/api/estimate")
def estimate_price(req: EstimateRequest):
    """Estimer le prix d'un bien immobilier."""
    if not _ml_ready:
        raise HTTPException(503, "Modèle ML non entraîné. Appelez /api/train-ml d'abord.")
    try:
        result = price_estimator.estimate(
            city=req.city,
            surface=req.surface,
            bedrooms=req.bedrooms,
            bathrooms=req.bathrooms,
            budget=req.budget,
            etage=req.etage,
            equipment_score=req.equipment_score,
        )
        dist = price_estimator.get_city_distribution(req.city)
        return {"success": True, "estimation": result, "distribution": dist}
    except Exception as e:
        raise HTTPException(400, f"Erreur estimation: {e}")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chatbot IA — utilise OpenAI pour analyser le marché."""
    if not OPENAI_API_KEY:
        # Mode démo sans clé API
        return {
            "response": _demo_chat_response(req.message, req.context),
            "mode": "demo"
        }

    # Construire le contexte marché
    context_str = ""
    if req.context:
        if "sarima" in req.context:
            s = req.context["sarima"]
            context_str += f"\nDernière analyse SARIMA: {s.get('gouvernorat')} — "
            context_str += f"Prix actuel: {s.get('derniere_valeur')} TND/m² — "
            context_str += f"Prévision +{s.get('horizon', 6)} trim: {s.get('prevision_finale')} TND/m² "
            context_str += f"(hausse prévue: {s.get('hausse_pct')}%)"
        if "estimation" in req.context:
            e = req.context["estimation"]
            context_str += f"\nDernière estimation: {e.get('predicted')} TND pour {e.get('city')}"

    system_prompt = f"""Tu es un expert en immobilier tunisien. Tu analyses les données du marché 
immobilier de Tunisie et tu donnes des conseils personnalisés en français.
Sois concis, factuel et pratique. Utilise les données fournies pour appuyer tes réponses.
{f'Contexte actuel: {context_str}' if context_str else ''}
Réponds toujours en français."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": req.message},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
            )
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"response": reply, "mode": "openai"}
    except Exception as e:
        return {"response": _demo_chat_response(req.message, req.context), "mode": "demo"}


def _demo_chat_response(message: str, context: dict | None) -> str:
    """Réponses démo quand OpenAI n'est pas disponible."""
    msg = message.lower()
    if any(w in msg for w in ["acheter", "investir", "bon moment"]):
        return ("📊 D'après les données actuelles, les zones côtières (Nabeul, Sousse, Monastir) "
                "montrent une croissance soutenue de 8-12% par an. Pour un achat résidentiel, "
                "Grand Tunis reste la zone la plus liquide. La hausse des taux directeurs BCT "
                "presse légèrement sur le pouvoir d'achat — un achat rapide est conseillé.")
    if any(w in msg for w in ["prix", "coût", "cher"]):
        return ("💰 Les prix médians varient de ~400 TND/m² dans les gouvernorats intérieurs "
                "à ~4000+ TND/m² dans les zones premium de Tunis (La Marsa, Carthage). "
                "La moyenne nationale est d'environ 1000 TND/m² pour 2024-2025.")
    if any(w in msg for w in ["sarima", "prévision", "forecast"]):
        return ("📈 Le modèle SARIMA détecte une saisonnalité trimestrielle dans les prix. "
                "Les prévisions sur 6 trimestres indiquent généralement une hausse de 5-15% "
                "selon le gouvernorat. Les zones côtières et Grand Tunis affichent les tendances "
                "les plus marquées.")
    return ("🏠 Je suis votre assistant immobilier Tunisie. Posez-moi des questions sur : "
            "les prix par gouvernorat, les tendances du marché, les prévisions SARIMA, "
            "ou les conseils d'investissement. "
            "⚙️ Configurez votre clé OpenAI dans la variable d'environnement OPENAI_API_KEY "
            "pour activer l'IA complète.")
