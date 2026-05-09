"""
AI-Powered Real Estate Platform — FastAPI Backend
Endpoints: /train, /analysis, /estimate, /status
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

# Import modules internes
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from core import sarima_engine, price_estimator

# ── État global ─────────────────────────────────────────────────────────────
_sarima_ready = False
_ml_ready = False
_sarima_last_results: dict | None = None
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


class RecommendRequest(BaseModel):
    budget: float
    ville: str = "Tunis"
    type_bien: str = "appartement"
    priorities: list[str] = []


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


@app.post("/api/recommend")
def recommend_zones(req: RecommendRequest):
    """Recommandations de zones selon budget, type de bien et priorités."""

    _ZONES: dict = {
        "Tunis": [
            {"zone": "La Marsa", "base_ppm2": 2900, "base_score": 82, "avantages": ["Bord de mer", "Bien cotée", "Investissement"], "base_trend": 5.2},
            {"zone": "El Menzah", "base_ppm2": 2600, "base_score": 78, "avantages": ["Centre accessible", "Calme", "Écoles"], "base_trend": 4.1},
            {"zone": "Ariana Ville", "base_ppm2": 2200, "base_score": 74, "avantages": ["Bon rapport qualité/prix", "Transport"], "base_trend": 3.8},
            {"zone": "Manouba", "base_ppm2": 1750, "base_score": 68, "avantages": ["Prix attractif", "Spacieux"], "base_trend": 2.9},
        ],
        "Sousse": [
            {"zone": "Sousse Centre", "base_ppm2": 2700, "base_score": 80, "avantages": ["Hyper centre", "Forte demande"], "base_trend": 6.1},
            {"zone": "Khzema Est", "base_ppm2": 2100, "base_score": 85, "avantages": ["Proche centre", "Évolution forte", "Locatif"], "base_trend": 7.2},
            {"zone": "Hammam Sousse", "base_ppm2": 1900, "base_score": 76, "avantages": ["Bon investissement", "Calme"], "base_trend": 4.5},
            {"zone": "Akouda", "base_ppm2": 1650, "base_score": 70, "avantages": ["Plus spacieux", "Prix doux"], "base_trend": 3.1},
        ],
        "Sfax": [
            {"zone": "Sfax Centre", "base_ppm2": 1900, "base_score": 79, "avantages": ["Économique", "Locatif fort"], "base_trend": 5.8},
            {"zone": "Route Teniour", "base_ppm2": 1600, "base_score": 83, "avantages": ["Meilleur rapport qualité/prix", "Calme"], "base_trend": 6.2},
            {"zone": "Chihia", "base_ppm2": 1380, "base_score": 72, "avantages": ["Très abordable", "Spacieux"], "base_trend": 3.4},
        ],
        "Nabeul": [
            {"zone": "Nabeul Centre", "base_ppm2": 2000, "base_score": 77, "avantages": ["Bord de mer proche", "Tourisme"], "base_trend": 4.9},
            {"zone": "Hammamet", "base_ppm2": 2550, "base_score": 81, "avantages": ["Touristique", "Forte demande", "Été"], "base_trend": 5.5},
            {"zone": "Hammamet Nord", "base_ppm2": 2200, "base_score": 79, "avantages": ["Résidentiel", "Calme"], "base_trend": 4.2},
        ],
        "Monastir": [
            {"zone": "Monastir Centre", "base_ppm2": 2100, "base_score": 80, "avantages": ["Bord de mer", "Aéroport proche"], "base_trend": 5.1},
            {"zone": "Ksar Hellal", "base_ppm2": 1600, "base_score": 74, "avantages": ["Abordable", "En croissance"], "base_trend": 4.3},
        ],
        "Bizerte": [
            {"zone": "Bizerte Centre", "base_ppm2": 1780, "base_score": 76, "avantages": ["Bord de mer", "Calme"], "base_trend": 3.8},
            {"zone": "Menzel Bourguiba", "base_ppm2": 1420, "base_score": 71, "avantages": ["Très abordable", "Spacieux"], "base_trend": 2.9},
        ],
        "Ariana": [
            {"zone": "Ariana Soghra", "base_ppm2": 2380, "base_score": 78, "avantages": ["Proche Tunis", "Transport"], "base_trend": 4.6},
            {"zone": "Riadh Andalous", "base_ppm2": 2150, "base_score": 82, "avantages": ["Résidentiel calme", "Bon investissement"], "base_trend": 5.3},
            {"zone": "Ettadhamen", "base_ppm2": 1700, "base_score": 69, "avantages": ["Prix accessibles"], "base_trend": 2.8},
        ],
        "Manouba": [
            {"zone": "Manouba Centre", "base_ppm2": 1750, "base_score": 72, "avantages": ["Abordable", "Spacieux"], "base_trend": 3.1},
            {"zone": "Oued Ellil", "base_ppm2": 1520, "base_score": 74, "avantages": ["Très abordable", "Calme", "En développement"], "base_trend": 4.2},
        ],
    }

    zones = _ZONES.get(req.ville, _ZONES["Tunis"])

    real_trend_gov: float | None = None
    real_ppm2_gov: float | None = None
    if _sarima_ready:
        try:
            summary = sarima_engine.get_all_gouvernorats_summary()
            gov_data = next((x for x in summary if x["gouvernorat"] == req.ville), None)
            if gov_data:
                real_trend_gov = gov_data["croissance_yoy"]
                real_ppm2_gov = gov_data["prix_median"]
        except Exception:
            pass

    type_mults = {"appartement": 1.0, "maison": 1.3, "villa": 1.8, "terrain": 0.45}
    surf_typical = {"appartement": 100, "maison": 130, "villa": 200, "terrain": 300}
    mult = type_mults.get(req.type_bien, 1.0)
    surface = surf_typical.get(req.type_bien, 100)
    base_ref = zones[0]["base_ppm2"]

    result_zones = []
    for z in zones:
        if real_ppm2_gov:
            ppm2 = round(real_ppm2_gov * (z["base_ppm2"] / base_ref) * mult)
        else:
            ppm2 = round(z["base_ppm2"] * mult)
        price = round(ppm2 * surface)

        if real_trend_gov is not None:
            delta = z["base_trend"] - zones[0]["base_trend"]
            trend = round(real_trend_gov + delta * 0.5, 1)
        else:
            trend = z["base_trend"]

        score = z["base_score"]
        if "prix" in req.priorities and price <= req.budget:
            score += 10
        if "investissement" in req.priorities and trend > 4:
            score += 8
        if "centre" in req.priorities and any("centre" in a.lower() for a in z["avantages"]):
            score += 5
        if "securite" in req.priorities and any("calme" in a.lower() or "résidentiel" in a.lower() for a in z["avantages"]):
            score += 6
        if "transport" in req.priorities and any("transport" in a.lower() or "aéroport" in a.lower() for a in z["avantages"]):
            score += 6

        result_zones.append({
            "zone": z["zone"],
            "price": price,
            "ppm2": ppm2,
            "score": min(score, 99),
            "avantages": z["avantages"],
            "trend": trend,
        })

    result_zones.sort(key=lambda x: x["score"], reverse=True)
    return {
        "zones": result_zones,
        "ville": req.ville,
        "type_bien": req.type_bien,
        "data_source": "sarima" if real_ppm2_gov else "modele",
    }


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


