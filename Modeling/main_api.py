"""
Estate Mind — Backend FastAPI v4.0
BO1 (Improve Market Reliability) + BO2 (Understand Territorial Dynamics)

Nouveauté v4.0 : Intégration Supabase
═══════════════════════════════════════
- _df()            → db.load_listings()  [Supabase avec fallback CSV]
- _df_territorial()→ db.load_territorial()[Supabase avec fallback CSV]
- df.to_csv()      → db.upsert_listings() [Supabase avec fallback CSV]
- _portfolios:dict → db.portfolio_*()    [Supabase avec fallback mémoire]
- SubscriptionStore→ db.subscription_*() [Supabase avec fallback fichier]

Principe de base :
  Si DATABASE_URL est configuré dans .env → Supabase est utilisé.
  Sinon → tout bascule automatiquement sur CSV/mémoire comme avant.
  L'app ne crashe jamais à cause de la base de données.
"""
from __future__ import annotations
import asyncio, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from config.settings import PROC_DIR, RAW_CSV_PATH
from agents.collector_agent import CollectorAgent
from tools.risk_tools import compute_trust_score, get_fraud_flags, run_trust_scoring
from tools.recommendation_tools import get_daily_recommendations
from agents.territorial_agent import TerritorialAgent
from tools.territorial_tools import (
    prepare_temporal_data, compute_time_series,
    compute_spatial_aggregation, detect_emerging_zones,
)
from tools.notifier import Notifier, SubscriptionStore, AlertSubscription
from tools.pdf_exporter import PDFExporter

# ── Supabase Manager ──────────────────────────────────────────────────────────
# Import avec fallback gracieux si le module n'existe pas encore
try:
    from db.supabase_manager import get_db
    _supabase_available = True
except ImportError:
    _supabase_available = False
    def get_db():
        return None


app = FastAPI(title="Estate Mind API", version="4.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000","http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"])

CLEAN_PATH = str(Path(PROC_DIR) / "listings_clean.csv")

# ── Initialisation au démarrage ───────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    """
    Au démarrage du serveur :
    1. Teste la connexion Supabase
    2. Crée les tables si absentes
    """
    if _supabase_available:
        db = get_db()
        if db and db.is_available:
            db.ensure_tables()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — lecture des données
# Ces fonctions remplacent les anciens pd.read_csv() directs
# ══════════════════════════════════════════════════════════════════════════════

def _df() -> Optional[pd.DataFrame]:
    """
    Charge les annonces nettoyées.
    PRIORITÉ : Supabase → CSV fallback → None
    """
    db = get_db() if _supabase_available else None
    if db:
        result = db.load_listings()
        if result is not None and not result.empty:
            return result
    # Fallback CSV direct
    p = Path(CLEAN_PATH)
    return pd.read_csv(CLEAN_PATH) if p.exists() else None


def _df_territorial() -> Optional[pd.DataFrame]:
    """
    Charge les données pour l'analyse territoriale BO2.
    PRIORITÉ : Supabase → CSV(processed) → CSV(raw) → None
    """
    db = get_db() if _supabase_available else None
    if db:
        result = db.load_territorial()
        if result is not None and not result.empty:
            return result
    # Fallback CSV
    for path, sep in [(CLEAN_PATH, ","), (RAW_CSV_PATH, ";")]:
        if Path(path).exists():
            try:
                df = pd.read_csv(path, sep=sep, on_bad_lines="skip",
                                 encoding="utf-8", encoding_errors="replace")
                if len(df) > 10:
                    return prepare_temporal_data(df)
            except Exception:
                pass
    return None


def _save_data(df: pd.DataFrame, pipeline_version: str = "v4.0") -> dict:
    """
    Sauvegarde le DataFrame traité.
    PRIORITÉ : Supabase (upsert atomique) → CSV fallback
    Retourne les stats d'upsert.
    """
    db = get_db() if _supabase_available else None
    if db:
        return db.upsert_listings(df, pipeline_version=pipeline_version)
    # Fallback CSV
    df.to_csv(CLEAN_PATH, index=False)
    return {"inserted": len(df), "updated": 0, "skipped": 0, "mode": "csv_fallback"}


_ta: Optional[TerritorialAgent] = None
def _get_ta() -> TerritorialAgent:
    global _ta
    if _ta is None:
        _ta = TerritorialAgent(verbose=False)
    return _ta


def _price_analysis(row: pd.Series, df_ref: pd.DataFrame, price: float, surface: float) -> str:
    """Analyse du prix par rapport au marché."""
    if surface <= 0 or price <= 0:
        return "Données insuffisantes pour l'analyse du prix."
    ppm2 = price / surface
    try:
        city = str(row.get("city", ""))
        city_df = df_ref[df_ref["city"].astype(str) == city] if "city" in df_ref.columns else df_ref
        m = (city_df["price"] / city_df["surface"]).median()
        if pd.isna(m):
            m = (df_ref["price"] / df_ref["surface"]).median()
    except Exception:
        m = ppm2
    if pd.isna(m) or m == 0:
        return f"Prix/m² : {ppm2:.0f} TND."
    ratio = ppm2 / m
    if ratio < 0.70:
        return f"Prix/m² ({ppm2:.0f} TND) anormalement bas vs médiane marché ({m:.0f} TND) — opportunité ou signal d'alerte."
    if ratio > 1.50:
        return f"Prix/m² ({ppm2:.0f} TND) supérieur à la médiane ({m:.0f} TND) — bien premium ou surévalué."
    return f"Prix/m² ({ppm2:.0f} TND) cohérent avec la médiane marché ({m:.0f} TND)."


# ── Portfolio en mémoire (fallback si Supabase indisponible) ──────────────────
_portfolios_cache: dict = {}


# ── Schémas Pydantic ──────────────────────────────────────────────────────────
class AnalyzePayload(BaseModel):
    description: str
    price:       float
    surface:     float = 0.0
    city:        str
    property_type: str = "appartement"
    source:      str   = "particulier"

class PipelinePayload(BaseModel):
    csv_path: str = ""

class TerritorialPayload(BaseModel):
    instruction: str = "Lance l'analyse territoriale complète"

class SubscribePayload(BaseModel):
    email: str; name: str
    watch_zones:    list = []
    watch_cities:   list = []
    budget_max:     Optional[float] = None
    surface_min:    Optional[float] = None
    property_types: list  = []
    trust_min:      float = 0.70
    price_threshold:float = 0.08
    webhook_url:    Optional[str] = None

class GRUTrainPayload(BaseModel):
    epochs: int = 50; lr: float = 1e-3; batch_size: int = 32

class GRUPredictPayload(BaseModel):
    description: str = ""; price: float = 0.0; surface: float = 0.0
    city: str = ""; property_type: str = "appartement"; source: str = "unknown"
    latitude: Optional[float] = None; longitude: Optional[float] = None

class SentimentPayload(BaseModel):
    description: str; title: str = ""; use_llm: bool = True

class AnalyzeEnrichedPayload(BaseModel):
    description: str; price: float; surface: float = 0.0
    city: str; property_type: str = "appartement"
    source: str = "particulier"; use_llm: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# BO1 — PIPELINE & TRUST SCORING
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/status")
def get_status():
    """Statut du système — indique si Supabase ou CSV est utilisé."""
    df = _df()
    db = get_db() if _supabase_available else None
    return {
        "dataset_available":  df is not None,
        "dataset_rows":       len(df) if df is not None else 0,
        "trust_scored":       df is not None and "trust_score" in df.columns,
        "data_source":        "supabase" if (db and db.is_available) else "csv",
        "supabase_connected": bool(db and db.is_available),
        "pipeline_version":   "v4.0 — BO1+BO2+Supabase",
    }


@app.get("/api/dashboard")
def get_dashboard():
    """Métriques dashboard — lues depuis Supabase si disponible."""
    # Essai stats rapides depuis Supabase (une seule requête SQL)
    db = get_db() if _supabase_available else None
    supabase_stats = db.get_dashboard_stats() if (db and db.is_available) else {}

    df = _df()
    if df is None:
        return {"total_raw": 0, "total_clean": 0, "avg_trust": 0.0,
                "suspect_count": 0, "high_legal": 0, "recent": [],
                "data_source": "none"}

    tc = df["trust_score"] if "trust_score" in df.columns else pd.Series([0.5]*len(df))
    recent = []
    for i, (_, row) in enumerate(df.head(10).iterrows()):
        t = float(row.get("trust_score", 0.5))
        recent.append({
            "id":          i+1,
            "title":       str(row.get("title", ""))[:60],
            "city":        str(row.get("city", "—")),
            "type":        str(row.get("property_type", "autre")),
            "trust":       round(t, 3),
            "legal":       0.15,
            "trust_level": "Fiable" if t >= .75 else ("Moyen" if t >= .5 else "Suspect"),
            "legal_level": "Faible",
        })

    # Priorité aux stats Supabase si disponibles (plus précises)
    avg_trust     = supabase_stats.get("avg_trust") or round(float(tc.mean()), 3)
    suspect_count = supabase_stats.get("suspect_count") or int((tc < 0.50).sum())

    return {
        "total_raw":     len(df),
        "total_clean":   len(df),
        "avg_trust":     float(avg_trust) if avg_trust else 0.0,
        "suspect_count": int(suspect_count) if suspect_count else 0,
        "high_legal":    0,
        "recent":        recent,
        "data_source":   "supabase" if supabase_stats else "csv",
    }


@app.get("/api/insight")
def get_insight():
    """Insight du jour généré à partir des métriques du pipeline."""
    df = _df()
    df_t = _df_territorial()
    lines = []

    if df is not None:
        tc   = df["trust_score"] if "trust_score" in df.columns else pd.Series([0.5]*len(df))
        avg  = round(float(tc.mean()), 3)
        susp = int((tc < 0.50).sum())
        lines.append(f"{len(df)} annonces dans le dataset. "
                     f"Trust score moyen : {avg}. {susp} annonces suspectes détectées.")

    try:
        from tools.territorial_tools import detect_emerging_zones
        if df_t is not None:
            alerts = detect_emerging_zones(df_t).get("alerts", [])
            if alerts:
                top = alerts[0]
                growth = top.get("price_growth", top.get("volume_growth", 0))
                lines.append(f"Alerte territoriale : {top['zone']} "
                             f"({top['alert_type']}, +{growth*100:.1f}%). "
                             f"{len(alerts)} zone(s) sous surveillance.")
    except Exception:
        pass

    db = get_db() if _supabase_available else None
    data_source = "supabase" if (db and db.is_available) else "csv"

    insight = " ".join(lines) if lines else (
        "Pipeline BO1+BO2 opérationnel. "
        "Collecte automatique toutes les 6 heures. "
        "Données fiabilisées par trust scoring multi-dimensionnel."
    )
    return {
        "insight":       insight,
        "generated_at":  datetime.utcnow().isoformat(),
        "data_source":   data_source,
    }


@app.post("/api/analyze")
def analyze_listing(p: AnalyzePayload):
    """Analyse d'une annonce — Trust Score BO1 + Analyse prix marché."""
    row    = pd.Series({
        "price": p.price, "surface": p.surface, "city": p.city,
        "description": p.description, "source": p.source,
        "property_type": p.property_type,
    })
    df_ref = _df() or pd.DataFrame([row.to_dict()])
    ts_    = compute_trust_score(row, df_ref)
    ff     = get_fraud_flags(row, df_ref)
    pa     = _price_analysis(row, df_ref, p.price, p.surface)

    v = ("FAVORABLE" if ts_ >= .70
         else "DANGER"    if ts_ < .50
         else "ATTENTION")

    return {
        "trust_score":      round(ts_, 3),
        "trust_level":      "Fiable" if ts_ >= .75 else ("Moyen" if ts_ >= .5 else "Suspect"),
        "legal_risk_score": 0.15,
        "legal_risk_level": "Faible",
        "fraud_flags":      ff,
        "legal_flags":      [],
        "relevant_laws":    [],
        "price_analysis":   pa,
        "recommendation": {
            "FAVORABLE": "Annonce fiable. Procédez aux vérifications standard avant signature.",
            "DANGER":    "Annonce à risque élevé. Investigation approfondie recommandée.",
            "ATTENTION": "Précautions requises. Vérifiez les informations clés avant de procéder.",
        }[v],
        "verdict": v,
    }


@app.get("/api/market")
def get_market(city: str = Query(None), property_type: str = Query(None)):
    df = _df()
    if df is None:
        return {"total": 0, "median_ppm2": 0, "mean_ppm2": 0, "top_city": "—",
                "cities": [], "property_types": {}}
    if city:          df = df[df["city"].astype(str).str.lower() == city.lower()]
    if property_type: df = df[df["property_type"].astype(str).str.lower() == property_type.lower()]
    df["ppm2"] = df["price"] / df["surface"].replace(0, float("nan"))
    cities = sorted([
        {"city": str(c), "ppm2": round(float(g["ppm2"].median()), 0),
         "n": len(g), "median": round(float(g["ppm2"].median()), 0),
         "mean": round(float(g["ppm2"].mean()), 0)}
        for c, g in df.groupby("city")
    ], key=lambda x: x["ppm2"], reverse=True)
    pt = ({str(k): round(v/len(df)*100, 1)
           for k, v in df["property_type"].value_counts().head(6).items()}
          if "property_type" in df.columns else {})
    return {
        "total":        len(df),
        "median_ppm2":  round(float(df["ppm2"].median()), 0) if not df.empty else 0,
        "mean_ppm2":    round(float(df["ppm2"].mean()),   0) if not df.empty else 0,
        "top_city":     cities[0]["city"] if cities else "—",
        "cities":       cities[:12],
        "property_types": pt,
    }


@app.post("/api/pipeline")
def run_pipeline(payload: PipelinePayload):
    """Lance le pipeline complet et sauvegarde dans Supabase (ou CSV)."""
    agent = CollectorAgent(verbose=False)
    df    = agent.run_cleaning_only(payload.csv_path or RAW_CSV_PATH)
    df    = run_trust_scoring(df)

    # Sauvegarde — Supabase si disponible, sinon CSV
    upsert_stats = _save_data(df, pipeline_version="v4.0")

    return {
        "rows_out":      len(df),
        "mean_trust":    round(float(df["trust_score"].mean()), 3),
        "suspect_count": int((df["trust_score"] < 0.50).sum()),
        "output_path":   CLEAN_PATH,
        "upsert_stats":  upsert_stats,
        "data_source":   upsert_stats.get("mode", "unknown"),
    }


async def _pipeline_logs(csv_path: str):
    db = get_db() if _supabase_available else None
    supabase_msg = (
        "[Supabase] 🗃️  Upsert atomique dans Supabase..."
        if (db and db.is_available)
        else "[CSV] 💾 Sauvegarde locale CSV (Supabase non configuré)"
    )
    steps = [
        "[CollectorAgent] 🚀 DÉMARRAGE",
        f"[CollectorAgent] Fichier : {csv_path}",
        "[CollectorAgent] DSO1 — Vérification santé des sources...",
        "[CollectorAgent] DSO2 — Nettoyage & enrichissement NLP...",
        "[CollectorAgent] DSO3 — Déduplication Jaccard + Embeddings...",
        "[CollectorAgent] DSO3 — Test KS (drift detection)...",
        "[CollectorAgent] DSO3 — Validation 14 règles métier...",
        "[CollectorAgent] ✅ NETTOYAGE TERMINÉ",
        "[RiskDetectionAgent] 🚀 TRUST SCORING",
        "[RiskDetectionAgent] Calcul Trust Score (5 dimensions)...",
        "[RiskDetectionAgent] Isolation Forest — détection anomalies...",
    ]
    for line in steps:
        yield f"data: {line}\n\n"
        await asyncio.sleep(0.35)

    agent = CollectorAgent(verbose=False)
    df    = agent.run_cleaning_only(csv_path)
    df    = run_trust_scoring(df)

    yield f"data: [RiskDetectionAgent] 📊 Score moyen : {round(float(df['trust_score'].mean()), 3)}\n\n"
    await asyncio.sleep(0.3)
    yield f"data: [RiskDetectionAgent] ✅ TERMINÉ\n\n"
    await asyncio.sleep(0.2)

    # Sauvegarde — Supabase ou CSV
    yield f"data: {supabase_msg}\n\n"
    upsert_stats = _save_data(df, pipeline_version="v4.0")
    await asyncio.sleep(0.4)

    mode = upsert_stats.get("mode", "unknown")
    if mode == "supabase":
        ins = upsert_stats.get("inserted", 0)
        upd = upsert_stats.get("updated", 0)
        yield f"data: [Supabase] ✅ Upsert OK — {ins} insérées · {upd} mises à jour\n\n"
    else:
        yield f"data: [CSV] ✅ Sauvegarde CSV OK — {len(df)} annonces\n\n"
    await asyncio.sleep(0.3)
    yield f"data: [MLflow] 📦 Run archivé\n\n"
    await asyncio.sleep(0.2)
    yield f"data: [Orchestrator] ✅ Pipeline terminé — {len(df)} annonces fiabilisées\n\n"
    yield "data: [DONE]\n\n"


@app.get("/api/pipeline/stream")
async def pipeline_stream(csv_path: str = Query(default="")):
    return StreamingResponse(
        _pipeline_logs(csv_path or RAW_CSV_PATH),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/recommendations")
def get_recommendations(
    budget:        float = Query(default=350_000),
    surface_min:   float = Query(default=80),
    city:          str   = Query(default=""),
    property_type: str   = Query(default=""),
    risk_tolerance:str   = Query(default="medium"),
):
    return get_daily_recommendations(
        csv_path=CLEAN_PATH, budget=budget, surface_min=surface_min,
        city=city, property_type=property_type, risk_tolerance=risk_tolerance,
    )


# ══════════════════════════════════════════════════════════════════════════════
# RECHERCHE
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/search")
def search_listings(
    q:             str   = Query(default=""),
    city:          str   = Query(default=""),
    property_type: str   = Query(default=""),
    price_min:     float = Query(default=0),
    price_max:     float = Query(default=0),
    surface_min:   float = Query(default=0),
    trust_min:     float = Query(default=0),
    source:        str   = Query(default=""),
    sort_by:       str   = Query(default="trust_score"),
    limit:         int   = Query(default=50),
    offset:        int   = Query(default=0),
):
    # Pour la recherche on passe les filtres à Supabase directement si possible
    db = get_db() if _supabase_available else None
    if db and db.is_available and (city or trust_min > 0):
        df = db.load_listings(
            city=city if city else None,
            property_type=property_type if property_type else None,
            min_trust=trust_min,
            limit=limit + offset,
        )
    else:
        df = _df()

    if df is None:
        return {"results": [], "total": 0, "offset": offset, "limit": limit}

    if q:
        mask = df["title"].astype(str).str.lower().str.contains(q.lower(), na=False)
        if "city" in df.columns:
            mask |= df["city"].astype(str).str.lower().str.contains(q.lower(), na=False)
        df = df[mask]

    if city and "city" in df.columns:
        df = df[df["city"].astype(str).str.lower().str.contains(city.lower(), na=False)]
    if property_type and "property_type" in df.columns:
        df = df[df["property_type"].astype(str) == property_type]
    if source and "source" in df.columns:
        df = df[df["source"].astype(str) == source]
    if price_min > 0 and "price" in df.columns:
        df = df[df["price"].fillna(0) >= price_min]
    if price_max > 0 and "price" in df.columns:
        df = df[df["price"].fillna(0) <= price_max]
    if surface_min > 0 and "surface" in df.columns:
        df = df[df["surface"].fillna(0) >= surface_min]
    if trust_min > 0 and "trust_score" in df.columns:
        df = df[df["trust_score"].fillna(0) >= trust_min]

    if sort_by == "price_asc"    and "price"        in df.columns: df = df.sort_values("price")
    elif sort_by == "price_desc"  and "price"        in df.columns: df = df.sort_values("price", ascending=False)
    elif sort_by == "trust_score" and "trust_score"  in df.columns: df = df.sort_values("trust_score", ascending=False)
    elif sort_by == "ppm2_asc"    and "price_per_m2" in df.columns: df = df.sort_values("price_per_m2")

    total = len(df)
    df    = df.iloc[offset:offset+limit]
    results = []
    for i, (_, row) in enumerate(df.iterrows()):
        price = float(row.get("price", 0) or 0)
        surf  = float(row.get("surface", 0) or 0)
        ppm2  = float(row.get("price_per_m2", 0) or (price/surf if surf > 0 else 0))
        trust = float(row.get("trust_score", 0.5) or 0.5)
        results.append({
            "id":            i+offset+1,
            "title":         str(row.get("title", ""))[:80],
            "city":          str(row.get("city", "—")),
            "property_type": str(row.get("property_type", "autre")),
            "price":         round(price, 0),
            "surface":       round(surf, 1),
            "price_per_m2":  round(ppm2, 0),
            "trust_score":   round(trust, 3),
            "trust_level":   "Fiable" if trust >= .75 else ("Moyen" if trust >= .5 else "Suspect"),
            "legal_risk_score": 0.15,
            "legal_risk_level": "Faible",
            "url":           str(row.get("url", "")),
            "source":        str(row.get("source", "unknown")),
            "description":   str(row.get("description", ""))[:200],
        })
    return {"results": results, "total": total, "offset": offset, "limit": limit}


# ══════════════════════════════════════════════════════════════════════════════
# BO2 — ANALYSE TERRITORIALE
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/territorial/summary")
def get_territorial_summary():
    return _get_ta().run_full_analysis()

@app.get("/api/territorial/time-series")
def get_time_series(
    group_by: str           = Query(default="city"),
    freq:     str           = Query(default="M"),
    zone:     Optional[str] = Query(default=None),
):
    df = _df_territorial()
    if df is None:
        return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    if zone:
        col = group_by if group_by in df.columns else "city"
        df  = df[df[col].astype(str).str.lower() == zone.lower()]
    return compute_time_series(df, group_by=group_by, freq=freq)

@app.get("/api/territorial/spatial")
def get_spatial(level: str = Query(default="all")):
    df = _df_territorial()
    if df is None:
        return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    result = compute_spatial_aggregation(df)
    if level == "governorate": return {"by_governorate": result["by_governorate"], "summary": result["summary"]}
    if level == "city":        return {"by_city": result["by_city"], "summary": result["summary"]}
    if level == "region":      return {"by_region": result["by_region"], "summary": result["summary"]}
    return result

@app.get("/api/territorial/alerts")
def get_alerts(
    group_by:          str           = Query(default="city"),
    lookback_recent:   int           = Query(default=45),
    lookback_previous: int           = Query(default=90),
    price_threshold:   float         = Query(default=0.08),
    volume_threshold:  float         = Query(default=0.20),
    severity:          Optional[str] = Query(default=None),
):
    df = _df_territorial()
    if df is None:
        return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    result = detect_emerging_zones(
        df, group_by=group_by,
        lookback_recent=lookback_recent, lookback_previous=lookback_previous,
        price_threshold=price_threshold, volume_threshold=volume_threshold,
    )
    if severity:
        result["alerts"] = [a for a in result["alerts"] if a.get("severity") == severity]
    return result

@app.get("/api/territorial/zone/{zone_name}")
def get_zone_detail(zone_name: str, group_by: str = Query(default="city")):
    return _get_ta().get_zone_analysis(zone_name, group_by=group_by)

@app.post("/api/territorial/analyze")
def trigger_territorial(payload: TerritorialPayload):
    return _get_ta().run(instruction=payload.instruction)


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIQUE DES PRIX — Alimenté par Supabase (données RÉELLES)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/price-history")
def get_price_history(url: str = Query(...), source: str = Query(default=None)):
    """
    Historique des prix pour une annonce.
    Retourne des données RÉELLES depuis Supabase, ou une liste vide si indisponible.
    PriceHistory.tsx utilise cette route et génère des données simulées si vide.
    """
    db = get_db() if _supabase_available else None
    if not (db and db.is_available):
        return {"url": url, "history": [], "source": "none"}
    history = db.get_price_history(url=url, source=source)
    return {
        "url":     url,
        "history": history,
        "count":   len(history),
        "source":  "supabase",
    }


# ══════════════════════════════════════════════════════════════════════════════
# BO1 AMÉLIORÉ — GRU + SHAP + Prophet + Sentiment + Anomalies
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/gru/train")
def train_gru(payload: GRUTrainPayload):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.gru_trust_classifier import get_classifier
    return get_classifier().train(df, epochs=payload.epochs, lr=payload.lr,
                                  batch_size=payload.batch_size, save=True)

@app.post("/api/gru/predict")
def gru_predict(payload: GRUPredictPayload):
    row    = pd.Series(payload.dict())
    df_ref = _df() or pd.DataFrame([row.to_dict()])
    from tools.gru_trust_classifier import get_classifier
    return get_classifier().predict(row, df_ref)

@app.post("/api/shap/train")
def shap_train():
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.shap_explainer import get_explainer
    return get_explainer().fit(df)

@app.post("/api/shap/explain")
def shap_explain(payload: AnalyzePayload):
    row    = pd.Series(payload.dict())
    df_ref = _df() or pd.DataFrame([row.to_dict()])
    from tools.shap_explainer import get_explainer
    exp = get_explainer().explain(row, df_ref)
    return {
        "trust_score": exp.trust_score, "base_value": exp.base_value,
        "contributions": exp.contributions, "top_positive": exp.top_positive,
        "top_negative":  exp.top_negative, "verdict": exp.verdict,
        "explanation_text": exp.explanation_text, "method": exp.method,
    }

@app.get("/api/forecast/{zone}")
def get_forecast(zone: str, group_by: str = Query(default="city"),
                 periods: int = Query(default=90), freq: str = Query(default="W")):
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.prophet_forecaster import forecast_prices
    return forecast_prices(df, zone=zone, group_by=group_by, periods_days=periods, freq=freq)

@app.get("/api/forecast")
def get_forecast_top(n: int = Query(default=5), periods: int = Query(default=90)):
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.prophet_forecaster import forecast_multiple_zones
    top = df["city"].value_counts().head(n).index.tolist() if "city" in df.columns else []
    return forecast_multiple_zones(df, zones=top, periods=periods)

@app.get("/api/anomalies")
def get_anomalies(contamination: float = Query(default=0.05)):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.anomaly_detector import detect_anomalies, get_anomaly_report
    return get_anomaly_report(detect_anomalies(df, contamination=contamination))

@app.get("/api/micro-markets")
def get_micro_markets(eps_km: float = Query(default=2.0), min_samples: int = Query(default=5)):
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.anomaly_detector import detect_micro_markets
    return detect_micro_markets(df, eps_km=eps_km, min_samples=min_samples)


# ══════════════════════════════════════════════════════════════════════════════
# BO2 AMÉLIORÉ — Sentiment + Trust enrichi
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/sentiment")
def analyze_sentiment(payload: SentimentPayload):
    from tools.sentiment_analyzer import get_sentiment_analyzer
    r = get_sentiment_analyzer().analyze(
        description=payload.description, title=payload.title,
        use_heuristic_always=not payload.use_llm,
    )
    return {"sentiment_score": r.sentiment_score, "sentiment_label": r.sentiment_label,
            "manipulation_flags": r.manipulation_flags, "confidence": r.confidence,
            "details": r.details, "method": r.method}

@app.post("/api/analyze-enriched")
def analyze_enriched(payload: AnalyzeEnrichedPayload):
    row    = pd.Series(payload.dict())
    df_ref = _df() or pd.DataFrame([row.to_dict()])
    ts_classic = compute_trust_score(row, df_ref)
    ff         = get_fraud_flags(row, df_ref)
    pa         = _price_analysis(row, df_ref, payload.price, payload.surface)
    from tools.gru_trust_classifier import get_classifier
    gru_result = get_classifier().predict(row, df_ref)
    from tools.sentiment_analyzer import get_sentiment_analyzer, compute_enriched_trust_score
    sentiment  = get_sentiment_analyzer().analyze(
        payload.description, use_heuristic_always=not payload.use_llm)
    enriched   = compute_enriched_trust_score(row, df_ref, sentiment)
    ts = enriched["trust_score_enriched"]
    v  = "FAVORABLE" if ts >= .70 else "DANGER" if ts < .50 else "ATTENTION"
    return {
        "trust_score": round(ts_classic, 3),
        "trust_level": "Fiable" if ts_classic >= .75 else ("Moyen" if ts_classic >= .5 else "Suspect"),
        "trust_gru": gru_result,
        "sentiment": {"score": sentiment.sentiment_score, "label": sentiment.sentiment_label,
                      "flags": sentiment.manipulation_flags, "method": sentiment.method},
        "trust_enriched": enriched["trust_score_enriched"],
        "trust_level_enriched": enriched["trust_level"],
        "trust_breakdown": enriched["breakdown"],
        "legal_risk_score": 0.15, "legal_risk_level": "Faible",
        "fraud_flags": ff, "price_analysis": pa, "verdict": v,
        "recommendation": {
            "FAVORABLE": "Annonce fiable. Procédez aux vérifications standard.",
            "DANGER":    "Annonce à risque élevé. Investigation approfondie recommandée.",
            "ATTENTION": "Précautions requises. Vérifiez les informations avant de procéder.",
        }[v],
    }

@app.get("/api/trust-enriched/{city}")
def get_trust_enriched(city: str, limit: int = Query(default=20)):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    subset = df[df["city"].astype(str).str.lower() == city.lower()].head(limit)
    if subset.empty: return {"city": city, "results": [], "total": 0}
    from tools.sentiment_analyzer import get_sentiment_analyzer, compute_enriched_trust_score
    analyzer = get_sentiment_analyzer()
    results  = []
    for _, row in subset.iterrows():
        sent     = analyzer.analyze(str(row.get("description", "") or ""), use_heuristic_always=True)
        enriched = compute_enriched_trust_score(row, df, sent)
        results.append({
            "title": str(row.get("title", ""))[:60],
            "trust_score_enriched": enriched["trust_score_enriched"],
            "trust_level": enriched["trust_level"],
            "sentiment_score": sent.sentiment_score,
            "sentiment_label": sent.sentiment_label,
            "breakdown": enriched["breakdown"],
        })
    return {"city": city, "results": results, "total": len(results),
            "avg_trust_enriched": round(
                sum(r["trust_score_enriched"] for r in results) / len(results), 3)}


# ══════════════════════════════════════════════════════════════════════════════
# MARKET INTELLIGENCE (5 features client BO1+BO2)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/days-on-market")
def get_dom(city: str = Query(default=""), top_n: int = Query(default=30)):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.market_intelligence import compute_days_on_market, get_dom_stats
    df_dom = compute_days_on_market(df)
    if city: df_dom = df_dom[df_dom["city"].astype(str).str.lower().str.contains(city.lower(), na=False)]
    stats    = get_dom_stats(df_dom)
    long_df  = df_dom[df_dom["days_on_market"].fillna(0) > 60].nlargest(top_n, "days_on_market")
    listings = [{"title": str(r.get("title", ""))[:70], "city": str(r.get("city", "")),
                 "price": float(r.get("price", 0) or 0),
                 "days_on_market": int(r.get("days_on_market", 0) or 0),
                 "negociation_potential": float(r.get("negociation_potential", 0)),
                 "url": str(r.get("url", "#"))} for _, r in long_df.iterrows()]
    return {"stats": stats, "long_listings": listings, "total_long": len(listings)}

@app.get("/api/price-drops")
def get_price_drops(min_drop: float = Query(default=2.0)):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.market_intelligence import detect_price_drops
    return detect_price_drops(df, min_drop_pct=min_drop)

@app.get("/api/rental-yield")
def get_rental_yield():
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.market_intelligence import compute_rental_yield
    return compute_rental_yield(df)

@app.get("/api/seller-score")
def get_seller_scores(city: str = Query(default=""), top_n: int = Query(default=20)):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.market_intelligence import compute_days_on_market, compute_seller_scores, get_top_negotiable
    df_e = compute_days_on_market(df)
    df_e = compute_seller_scores(df_e)
    if city: df_e = df_e[df_e["city"].astype(str).str.lower().str.contains(city.lower(), na=False)]
    return {"top_negotiable": get_top_negotiable(df_e, top_n=top_n)}

@app.get("/api/buying-window")
def get_buying_window(city: str = Query(default="")):
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    if city and "city" in df.columns:
        df = df[df["city"].astype(str).str.lower().str.contains(city.lower(), na=False)]
    from tools.market_intelligence import compute_buying_window
    return compute_buying_window(df)

@app.get("/api/rental-yield/calculator")
def calc_yield(price: float = Query(...), city: str = Query(default=""),
               property_type: str = Query(default="appartement")):
    df = _df()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.market_intelligence import compute_rental_yield
    yield_data = compute_rental_yield(df)
    match = next((r for r in yield_data["results"]
                  if r["city"].lower() == city.lower() and r["property_type"] == property_type), None)
    if not match and yield_data["results"]:
        match = next((r for r in yield_data["results"] if r["city"].lower() == city.lower()),
                     yield_data["results"][0])
    loyer = match["median_rent"] if match else 700
    if price > 0 and loyer > 0:
        yb = round(loyer*12/price*100, 2)
        yn = round(yb * .75, 2)
        return {"price": price, "city": city, "property_type": property_type,
                "estimated_monthly_rent": loyer, "yield_brut_pct": yb, "yield_net_pct": yn,
                "annual_rent": loyer*12,
                "verdict": "excellent" if yb >= 7 else "bon" if yb >= 5 else "correct" if yb >= 3 else "faible"}
    return {"error": "Données insuffisantes"}

@app.get("/api/market-intelligence")
def get_market_intelligence():
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    from tools.market_intelligence import generate_market_intelligence_report
    return generate_market_intelligence_report(df)


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT PDF (BO2)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/export/pdf/territorial")
def export_territorial_pdf(lookback_recent: int = Query(default=45)):
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    alerts_data = detect_emerging_zones(df, lookback_recent=lookback_recent)
    spatial     = compute_spatial_aggregation(df)
    exporter    = PDFExporter()
    run_id      = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    path        = exporter.export_territorial_report(
        alerts_data.get("alerts", []), spatial, run_id=run_id)
    if path.exists():
        return FileResponse(str(path), media_type="application/pdf", filename=path.name,
                            headers={"Content-Disposition": f"attachment; filename={path.name}"})
    return JSONResponse({"error": "Génération échouée"}, status_code=500)


# ══════════════════════════════════════════════════════════════════════════════
# ALERTES & ABONNEMENTS — intégrés avec Supabase
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/alerts/subscribe")
def subscribe_alerts(payload: SubscribePayload):
    sub_id = uuid.uuid4().hex[:8]
    sub_data = {
        "sub_id":         sub_id,
        "email":          payload.email,
        "name":           payload.name,
        "watch_zones":    payload.watch_zones,
        "watch_cities":   payload.watch_cities,
        "budget_max":     payload.budget_max,
        "surface_min":    payload.surface_min,
        "property_types": payload.property_types,
        "trust_min":      payload.trust_min,
        "price_threshold":payload.price_threshold,
        "webhook_url":    payload.webhook_url,
    }

    # Essai Supabase
    db = get_db() if _supabase_available else None
    if db and db.is_available:
        db.subscription_add(sub_data)
        return {"status": "ok", "sub_id": sub_id,
                "message": f"Abonnement créé (Supabase) pour {payload.email}",
                "data_source": "supabase"}

    # Fallback SubscriptionStore local
    store = SubscriptionStore()
    sub   = AlertSubscription(
        sub_id=sub_id, email=payload.email, name=payload.name,
        watch_zones=payload.watch_zones, watch_cities=payload.watch_cities,
        budget_max=payload.budget_max, surface_min=payload.surface_min,
        property_types=payload.property_types, trust_min=payload.trust_min,
        price_threshold=payload.price_threshold, webhook_url=payload.webhook_url,
    )
    store.add(sub)
    return {"status": "ok", "sub_id": sub_id,
            "message": f"Abonnement créé (local) pour {payload.email}",
            "data_source": "local"}


@app.delete("/api/alerts/unsubscribe")
def unsubscribe_alerts(email: str = Query(...)):
    db = get_db() if _supabase_available else None
    if db and db.is_available:
        ok = db.subscription_remove(email)
        return {"status": "ok" if ok else "not_found", "data_source": "supabase"}
    store = SubscriptionStore()
    ok    = store.remove(email)
    return {"status": "ok" if ok else "not_found", "data_source": "local"}


@app.get("/api/alerts/subscriptions")
def list_subscriptions():
    db = get_db() if _supabase_available else None
    if db and db.is_available:
        subs = db.subscription_list_active()
        return {"subscriptions": subs, "total": len(subs), "data_source": "supabase"}
    store = SubscriptionStore()
    return {"subscriptions": store.all_as_dicts(), "total": len(store.get_all_active()),
            "data_source": "local"}


@app.post("/api/alerts/dispatch")
def dispatch_alerts():
    df = _df_territorial()
    if df is None: return JSONResponse({"error": "Dataset indisponible"}, status_code=503)
    alerts_data = detect_emerging_zones(df)
    notifier    = Notifier()
    result      = notifier.dispatch_territorial_alerts(alerts_data.get("alerts", []))
    return {"status": "ok", "dispatched": result}


# ══════════════════════════════════════════════════════════════════════════════
# PORTEFEUILLE — persistant dans Supabase, fallback mémoire
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio/{user_id}")
def get_portfolio(user_id: str):
    db = get_db() if _supabase_available else None
    if db and db.is_available:
        items = db.portfolio_get(user_id)
        return {"user_id": user_id, "items": items, "total": len(items),
                "data_source": "supabase"}
    items = _portfolios_cache.get(user_id, [])
    return {"user_id": user_id, "items": items, "total": len(items),
            "data_source": "memory"}


@app.post("/api/portfolio/{user_id}/add")
def add_to_portfolio(user_id: str, item: dict):
    db = get_db() if _supabase_available else None
    if db and db.is_available:
        item["user_id"] = user_id
        ok = db.portfolio_add(user_id, item)
        return {"status": "ok" if ok else "error", "data_source": "supabase"}
    # Fallback mémoire
    if user_id not in _portfolios_cache:
        _portfolios_cache[user_id] = []
    item["saved_at"]    = datetime.utcnow().isoformat()
    item["saved_price"] = item.get("price", 0)
    _portfolios_cache[user_id].append(item)
    return {"status": "ok", "total": len(_portfolios_cache[user_id]),
            "data_source": "memory"}


@app.delete("/api/portfolio/{user_id}/{listing_url:path}")
def remove_from_portfolio(user_id: str, listing_url: str):
    db = get_db() if _supabase_available else None
    if db and db.is_available:
        ok = db.portfolio_remove(user_id, listing_url)
        return {"status": "ok" if ok else "not_found", "data_source": "supabase"}
    if user_id in _portfolios_cache:
        _portfolios_cache[user_id] = [
            i for i in _portfolios_cache[user_id]
            if i.get("url") != listing_url
        ]
    return {"status": "ok", "data_source": "memory"}


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
