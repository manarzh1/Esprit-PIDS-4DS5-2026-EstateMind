"""
Estate Mind — main_api.py (VERSION 4 — SUPABASE INTÉGRÉ)
==========================================================
Nouveautés vs v3 :
  - Données lues depuis Supabase (via supabase_manager.load_listings())
  - Fallback CSV automatique si Supabase indisponible
  - Trust scores ML réécrits dans Supabase après batch scoring
  - Route /api/data/listings  → données réelles depuis Supabase
  - Route /api/data/stats     → dashboard stats depuis Supabase
  - Route /api/data/price-history/{url} → historique prix réel
  - Route /api/data/portfolio/* → favoris utilisateurs
  - Route /api/pipeline/run   → déclenche inject_csv + ML scoring
  - Agents LangGraph activés si OPENAI_API_KEY présente
"""

from __future__ import annotations
import asyncio
import json
import os
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from joblib import load
from loguru import logger
from pydantic import BaseModel, Field

load_dotenv()

# ── Chemins ───────────────────────────────────────────────────────────────────
SAVED_DIR = Path(__file__).parent / "models" / "saved"
BASE_DIR  = Path(__file__).parent

# ── Thread pool ───────────────────────────────────────────────────────────────
executor = ThreadPoolExecutor(max_workers=6)

# ── Cache global ──────────────────────────────────────────────────────────────
MODELS: dict = {}
DB     = None   # SupabaseManager singleton


# ═══════════════════════════════════════════════════════════════════════════════
# INITIALISATION AU DÉMARRAGE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_db():
    """Initialise la connexion Supabase (ou SQLite fallback)."""
    global DB
    try:
        from db.supabase_manager import get_db
        DB = get_db()
        status = "Supabase ✅" if DB.is_available else "CSV fallback ⚠️"
        print(f"   [DB] {status}")
    except Exception as e:
        print(f"   [DB] ⚠️  supabase_manager indisponible ({e})")
        try:
            from db.db_manager import get_db as get_sqlite
            DB = get_sqlite()
            print("   [DB] SQLite local ✅")
        except Exception as e2:
            print(f"   [DB] ❌ Aucune DB disponible : {e2}")
            DB = None


def _load_all_models():
    """Charge les 6 modèles ML en mémoire."""
    files = {
        "m1_model":    "m1_xgboost.joblib",
        "m1_encoders": "m1_encoders.joblib",
        "m2_model":    "m2_isolation_forest.joblib",
        "m2_scaler":   "m2_scaler.joblib",
        "m2_stats":    "m2_stats.joblib",
        "m3_pipeline": "m3_nlp_pipeline.joblib",
        "m4_index":    "m4_city_index.joblib",
        "m5_model":    "m5_kmeans.joblib",
        "m5_scaler":   "m5_scaler.joblib",
        "m5_stats":    "m5_city_stats.joblib",
        "m6_model":    "m6_xgboost.joblib",
        "m6_encoder":  "m6_city_encoder.joblib",
        "m6_stats":    "m6_city_stats.joblib",
    }
    loaded = 0
    for key, fname in files.items():
        path = SAVED_DIR / fname
        if path.exists():
            try:
                MODELS[key] = load(path)
                loaded += 1
                print(f"   ✅ {fname}")
            except Exception as e:
                print(f"   ❌ {fname} : {e}")
                MODELS[key] = None
        else:
            print(f"   ⚠️  Manquant : {fname}")
            MODELS[key] = None

    # Prophet pre-computed JSON
    fc_path = SAVED_DIR / "m4_forecasts.json"
    if fc_path.exists():
        with open(fc_path, encoding="utf-8") as f:
            MODELS["m4_forecasts"] = json.load(f)
        print(f"   ✅ Prophet → {len(MODELS['m4_forecasts'].get('cities', []))} villes")
    else:
        MODELS["m4_forecasts"] = {}
        print("   ⚠️  m4_forecasts.json manquant → python models/fix_prophet.py")

    print(f"\n   🏁 {loaded}/{len(files)} modèles ML chargés")
    return loaded


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n🚀 Estate Mind API v4 — Démarrage")
    loop = asyncio.get_event_loop()
    # 1. DB
    await loop.run_in_executor(executor, _load_db)
    # 2. Modèles ML
    if SAVED_DIR.exists():
        await loop.run_in_executor(executor, _load_all_models)
    else:
        print(f"   ❌ {SAVED_DIR} introuvable")
    print("   ✅ API prête\n")
    yield
    print("🛑 Estate Mind API — Arrêt")
    executor.shutdown(wait=False)


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Estate Mind API",
    description="API PropTech Tunisie — Supabase + 6 modèles ML",
    version="4.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER ASYNC
# ═══════════════════════════════════════════════════════════════════════════════

async def run_sync(fn, *args, timeout: float = 30.0):
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(executor, fn, *args),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, f"Timeout ({timeout}s dépassé)")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHÉMAS PYDANTIC
# ═══════════════════════════════════════════════════════════════════════════════

class ListingInput(BaseModel):
    price_value:  float = Field(..., example=350_000)
    surface_m2:   float = Field(..., example=120)
    city:         str   = Field(..., example="Tunis")
    description:  str   = Field("", example="Appartement S+3 vue mer")
    source:       str   = Field("mubawab", example="mubawab")
    title:        str   = Field("", example="")
    bedrooms:     Optional[float] = None
    bathrooms:    Optional[float] = None
    latitude:     Optional[float] = None

class AnomalyInput(BaseModel):
    price_value: float = Field(..., example=1500)
    surface_m2:  float = Field(..., example=120)
    bedrooms:    Optional[float] = None
    city:        str   = Field("", example="Tunis")

class ClassifyInput(BaseModel):
    title:       str = Field(..., example="Villa piscine 4 chambres Ain Zaghouan")
    description: str = Field("", example="")

class EmergenceInput(BaseModel):
    city:         str   = Field(..., example="Nabeul")
    median_price: float = Field(..., example=3200)
    volume:       int   = Field(..., example=45)
    mean_price:   Optional[float] = None
    std_price:    float = 0.0

class PortfolioAddInput(BaseModel):
    user_id:      str
    url:          str
    source:       str
    price:        Optional[float] = None
    title:        Optional[str]   = None
    city:         Optional[str]   = None
    property_type: Optional[str] = None
    surface:      Optional[float] = None
    trust_score:  Optional[float] = None

class ListingsQuery(BaseModel):
    city:          Optional[str]   = None
    property_type: Optional[str]   = None
    min_trust:     float           = 0.0
    limit:         int             = 100


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS D'INFÉRENCE ML (synchrones — thread pool)
# ═══════════════════════════════════════════════════════════════════════════════

def _check(key: str):
    if not MODELS.get(key):
        raise ValueError(f"Modèle '{key}' non disponible. Lancez train_and_save.py")

def _trust_score_sync(price_value, surface_m2, city, description,
                       source, bedrooms, bathrooms, latitude):
    _check("m1_model")
    model, encoders = MODELS["m1_model"], MODELS["m1_encoders"]
    ppm2    = price_value / max(surface_m2, 1)
    desc_len = len(str(description or ""))
    has_gps  = 1 if latitude else 0
    le_s = encoders["source"]
    src  = source if source in encoders["source_classes"] else encoders["source_classes"][0]
    source_enc = int(le_s.transform([src])[0])
    le_c  = encoders["city"]
    top   = encoders["top_cities"]
    city2 = city if city in top else "other"
    city2 = city2 if city2 in encoders["city_classes"] else encoders["city_classes"][0]
    city_enc = int(le_c.transform([city2])[0])
    X = pd.DataFrame([{
        "price_value": price_value, "surface_m2": surface_m2,
        "price_per_m2": ppm2,
        "bedrooms": bedrooms if bedrooms is not None else -1,
        "bathrooms": bathrooms if bathrooms is not None else -1,
        "source_enc": source_enc, "city_enc": city_enc,
        "desc_len": float(desc_len), "has_gps": float(has_gps),
    }])
    proba = float(model.predict_proba(X)[0][1])
    return {
        "trust_score":  round(proba, 4),
        "label":        "Fiable" if proba >= 0.6 else "Suspect",
        "confidence":   round(max(proba, 1 - proba), 4),
        "price_per_m2": round(ppm2, 2),
        "source":       "ml_xgboost",
    }

def _anomaly_sync(price_value, surface_m2, bedrooms):
    _check("m2_model")
    model, scaler, stats = MODELS["m2_model"], MODELS["m2_scaler"], MODELS["m2_stats"]
    ppm2 = price_value / max(surface_m2, 1)
    medians = stats.get("medians", {})
    X  = pd.DataFrame([{
        "price_value": price_value, "surface_m2": surface_m2,
        "price_per_m2": ppm2,
        "bedrooms": bedrooms if bedrooms is not None else medians.get("bedrooms", 2),
    }])
    Xs = scaler.transform(X)
    decision = float(model.decision_function(Xs)[0])
    is_anom  = bool(model.predict(Xs)[0] == -1)
    return {
        "is_anomaly":     is_anom,
        "anomaly_score":  round(max(0, min(1, -decision / 0.5)), 4),
        "decision_score": round(decision, 4),
        "price_per_m2":   round(ppm2, 2),
        "source":         "isolation_forest",
    }

def _classify_sync(title, description):
    _check("m3_pipeline")
    pipeline = MODELS["m3_pipeline"]
    text = (str(title) + " " + str(description)).lower().strip()
    pred = pipeline.predict([text])[0]
    clf  = pipeline.named_steps["clf"]
    conf = 0.8
    if hasattr(clf, "decision_function"):
        scores = pipeline.decision_function([text])[0]
        if hasattr(scores, "__len__"):
            conf = round(float(np.max(scores) / (np.sum(np.abs(scores)) + 1e-9)), 4)
    return {"property_type": pred, "confidence": min(1.0, conf), "source": "tfidf_linearsvc"}

def _forecast_sync(city, days_ahead):
    all_fc    = MODELS.get("m4_forecasts") or {}
    forecasts = all_fc.get("forecasts", {})
    city_match = next((c for c in forecasts if c.lower() == city.lower()), None)
    if not city_match:
        return {"error": f"Ville '{city}' non disponible",
                "available_cities": list(forecasts.keys())}
    city_data = forecasts[city_match]
    rows      = city_data.get("forecast", [])[:days_ahead]
    if not rows:
        return {"error": f"Pas de prévision pour {city_match}"}
    predicted = [r["predicted"] for r in rows]
    return {
        "city":             city_match,
        "days_ahead":       len(rows),
        "mean_predicted":   round(sum(predicted) / len(predicted), 0),
        "last_known_price": city_data.get("last_known_price"),
        "model_mape":       city_data.get("mape_pct"),
        "synthetic_dates":  city_data.get("synthetic_dates", True),
        "source":           "prophet_precomputed",
        "forecast":         rows,
    }

def _clusters_all_sync():
    stats = MODELS.get("m5_stats")
    if not stats:
        return {"error": "M5 non disponible"}
    return {
        "n_clusters":       len(stats.get("cluster_profiles", [])),
        "cluster_profiles": stats.get("cluster_profiles", []),
        "n_cities":         len(stats.get("city_cluster_map", {})),
        "national_median":  round(stats.get("national_median", 0), 0),
        "source":           "kmeans",
    }

def _cluster_city_sync(city):
    stats = MODELS.get("m5_stats")
    if not stats:
        return {"error": "M5 non disponible"}
    cmap = stats.get("city_cluster_map", {})
    cid  = cmap.get(city) or next(
        (v for c, v in cmap.items() if c.lower() == city.lower()), None
    )
    if cid is None:
        return {"error": f"Ville '{city}' non trouvée", "available": list(cmap.keys())}
    profiles = stats.get("cluster_profiles", [])
    profile  = next((p for p in profiles if p["cluster_id"] == cid), {})
    return {"city": city, "cluster_id": int(cid), "profile": profile, "source": "kmeans"}

def _emerging_sync(city, median_price, volume, mean_price, std_price):
    model, le, stats = MODELS.get("m6_model"), MODELS.get("m6_encoder"), MODELS.get("m6_stats")
    if not model or not stats:
        return {"error": "M6 non disponible"}
    nat_med = stats["national_median"]
    avg_vol = stats["avg_vol_per_city"]
    classes = stats["city_encoder_classes"]
    city2   = city if city in classes else classes[0]
    city_enc = int(le.transform([city2])[0])
    mp = mean_price if mean_price else median_price
    X = pd.DataFrame([{
        "median_price": median_price, "mean_price": mp, "volume": volume,
        "std_price": std_price, "city_median": median_price, "city_volume": volume,
        "price_vs_national": median_price / nat_med,
        "vol_vs_national":   volume / (avg_vol + 1),
        "city_enc": city_enc,
    }])
    proba = float(model.predict_proba(X)[0][1])
    is_em = bool(model.predict(X)[0] == 1)
    return {
        "city":              city,
        "is_emerging":       is_em,
        "emergence_proba":   round(proba, 4),
        "price_vs_national": round(median_price / nat_med, 3),
        "national_median":   round(nat_med, 0),
        "recommandation": (
            "Zone à surveiller activement — investissement potentiel"
            if proba > 0.7 else "Zone stable — monitoring standard"
        ),
        "source": "xgboost",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH ML + ÉCRITURE DANS SUPABASE
# ═══════════════════════════════════════════════════════════════════════════════

def _score_df_and_push(df: pd.DataFrame) -> dict:
    """
    Score un DataFrame avec M1+M2+M3, puis pousse les résultats dans Supabase.
    Appelé après chaque batch CSV ou run pipeline.
    """
    for col in ["price_value", "price", "surface_m2", "surface",
                "latitude", "bedrooms", "bathrooms"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normaliser les colonnes (compatibilité tayara/mubawab)
    if "price" in df.columns and "price_value" not in df.columns:
        df["price_value"] = df["price"]
    if "surface" in df.columns and "surface_m2" not in df.columns:
        df["surface_m2"] = df["surface"]

    if "price_per_m2" not in df.columns:
        df["price_per_m2"] = df["price_value"] / df["surface_m2"].replace(0, np.nan)

    # M1 — Trust Score
    if MODELS.get("m1_model") and MODELS.get("m1_encoders"):
        scores, labels = [], []
        for _, row in df.iterrows():
            try:
                r = _trust_score_sync(
                    float(row.get("price_value") or row.get("price") or 0),
                    float(row.get("surface_m2") or row.get("surface") or 1),
                    str(row.get("city", "")),
                    str(row.get("description", "")),
                    str(row.get("source", "")),
                    row.get("bedrooms"), row.get("bathrooms"), row.get("latitude"),
                )
                scores.append(r["trust_score"])
                labels.append(r["label"])
            except Exception:
                scores.append(0.5)
                labels.append("Moyen")
        df["trust_score"] = scores
        df["trust_level"]  = labels

    # M2 — Anomaly
    if MODELS.get("m2_model"):
        FEAT = ["price_value", "surface_m2", "price_per_m2", "bedrooms"]
        for c in FEAT:
            if c not in df.columns:
                df[c] = np.nan
        X  = df[FEAT].fillna(df[FEAT].median())
        Xs = MODELS["m2_scaler"].transform(X)
        df["is_anomaly"]    = (MODELS["m2_model"].predict(Xs) == -1)
        df["anomaly_score"] = np.clip(
            -MODELS["m2_model"].decision_function(Xs) / 0.5, 0, 1
        ).round(4)

    # M3 — Property Type NLP
    if MODELS.get("m3_pipeline"):
        texts = (df.get("title", pd.Series("")).fillna("") + " " +
                 df.get("description", pd.Series("")).fillna("")).str.lower()
        df["property_type_ml"] = MODELS["m3_pipeline"].predict(texts)
        # Corriger les types génériques
        generic = {"immobilier", "autre", "194", "231", "211", "20", "22", "", "nan"}
        mask = df["property_type"].fillna("").str.lower().isin(generic)
        df.loc[mask, "property_type"] = df.loc[mask, "property_type_ml"]

    # Pousser dans Supabase si disponible
    n_pushed = 0
    if DB is not None:
        try:
            if hasattr(DB, "upsert_listings"):
                stats = DB.upsert_listings(df, pipeline_version="v4_ml")
                n_pushed = stats.get("inserted", 0) + stats.get("updated", 0)
                logger.info(f"[API] Supabase upsert : {stats}")
            elif hasattr(DB, "insert_annonces"):
                n_pushed = DB.insert_annonces(df)
                if "trust_score" in df.columns:
                    DB.insert_trust_scores(df)
        except Exception as e:
            logger.warning(f"[API] Supabase push échoué : {e}")

    n_fiable  = int((df.get("trust_label", df.get("trust_level", pd.Series())) == "Fiable").sum())
    n_suspect = int((df.get("trust_label", df.get("trust_level", pd.Series())) == "Suspect").sum())
    n_anom    = int(df.get("is_anomaly", pd.Series(dtype=bool)).sum())

    return {
        "total":             len(df),
        "n_fiable":          n_fiable,
        "n_suspect":         n_suspect,
        "n_anomalies":       n_anom,
        "mean_trust_score":  round(float(df["trust_score"].mean()), 4) if "trust_score" in df.columns else None,
        "n_pushed_to_db":    n_pushed,
        "property_type_dist": df["property_type"].value_counts().head(8).to_dict() if "property_type" in df.columns else {},
    }


def _read_csv_upload(contents: bytes) -> pd.DataFrame:
    for enc in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            df = pd.read_csv(io.BytesIO(contents), sep=";",
                              encoding=enc, on_bad_lines="skip")
            df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
            if df.shape[1] > 3:
                return df
        except Exception:
            continue
    raise ValueError("Impossible de lire le CSV")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — SANTÉ
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Santé"])
async def root():
    db_status = "non connectée"
    if DB is not None:
        db_status = "Supabase ✅" if getattr(DB, "is_available", False) else "SQLite local ✅"
    return {
        "app":           "Estate Mind API",
        "version":       "4.0.0",
        "db":            db_status,
        "models_loaded": len([v for v in MODELS.values() if v is not None]),
        "docs":          "/docs",
    }

@app.get("/api/ml/health", tags=["Utilitaires"])
@app.get("/api/health", tags=["Santé"])
async def health():
    keys = ["m1_model","m2_model","m3_pipeline","m4_forecasts","m5_model","m6_model"]
    db_ok = DB is not None and getattr(DB, "is_available", True)
    return {
        "status":      "ok" if all(MODELS.get(k) for k in keys) and db_ok else "partial",
        "database":    "supabase" if db_ok and getattr(DB, "is_available", False) else "sqlite_or_none",
        "models":      {k: ("✅" if MODELS.get(k) is not None else "❌") for k in keys},
        "prophet_cities": len(MODELS.get("m4_forecasts", {}).get("forecasts", {})),
    }

@app.get("/api/ml/training-report", tags=["Utilitaires"])
async def training_report():
    path = SAVED_DIR / "training_report.json"
    if not path.exists():
        raise HTTPException(404, "Lancez d'abord train_and_save.py")
    return json.loads(path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — DONNÉES SUPABASE (nouvelles routes v4)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/data/listings", tags=["Données Supabase"])
async def get_listings(
    city:          Optional[str] = None,
    property_type: Optional[str] = None,
    min_trust:     float         = Query(0.0, ge=0.0, le=1.0),
    limit:         int           = Query(100, ge=1, le=1000),
):
    """
    Charge les annonces directement depuis Supabase.
    Fallback automatique sur le CSV local si Supabase indisponible.
    """
    def _run():
        if DB is None:
            return {"error": "Aucune base de données disponible"}
        try:
            if hasattr(DB, "load_listings"):
                df = DB.load_listings(city=city, property_type=property_type,
                                      min_trust=min_trust, limit=limit)
            else:
                df = DB.get_annonces(city=city, limit=limit)

            if df is None or df.empty:
                return {"listings": [], "total": 0, "source": "empty"}

            # Nettoyer NaN pour JSON
            
            df = df.where(pd.notna(df), None)
            return {
                "listings": df.to_dict(orient="records"),
                "total":    len(df),
                "source":   "supabase" if getattr(DB, "is_available", False) else "csv_fallback",
            }
        except Exception as e:
            logger.error(f"[API] get_listings : {e}")
            raise ValueError(str(e))

    return await run_sync(_run, timeout=60.0)


@app.get("/api/data/stats", tags=["Données Supabase"])
async def get_dashboard_stats():
    """
    Stats globales du dashboard depuis Supabase.
    Utilisé par les KPI cards du Dashboard.
    """
    def _run():
        if DB is None:
            return {}
        try:
            if hasattr(DB, "get_dashboard_stats"):
                stats = DB.get_dashboard_stats()
                if stats:
                    return stats

            # Fallback : calculer depuis les données chargées
            if hasattr(DB, "load_listings"):
                df = DB.load_listings(limit=10000)
            else:
                df = DB.get_annonces(limit=10000)

            if df is None or df.empty:
                return {}

            trust_col = "trust_score" if "trust_score" in df.columns else None
            return {
                "total":        len(df),
                "avg_trust":    round(float(df[trust_col].mean()), 3) if trust_col else None,
                "suspect_count": int((df[trust_col] < 0.5).sum()) if trust_col else None,
                "sources":      df["source"].value_counts().to_dict() if "source" in df.columns else {},
                "cities_count": df["city"].nunique() if "city" in df.columns else None,
            }
        except Exception as e:
            logger.warning(f"[API] get_dashboard_stats : {e}")
            return {}

    return await run_sync(_run, timeout=30.0)


@app.get("/api/data/price-history/{listing_url:path}", tags=["Données Supabase"])
async def get_price_history(listing_url: str, source: Optional[str] = None):
    """
    Historique des changements de prix d'une annonce.
    Alimente PriceHistory.tsx avec des données réelles depuis Supabase.
    """
    def _run():
        if DB is None or not hasattr(DB, "get_price_history"):
            return []
        return DB.get_price_history(listing_url, source)

    history = await run_sync(_run)
    return {"url": listing_url, "history": history, "n_changes": len(history)}


@app.get("/api/data/portfolio/{user_id}", tags=["Données Supabase"])
async def get_portfolio(user_id: str):
    """Récupère les favoris d'un utilisateur."""
    def _run():
        if DB is None or not hasattr(DB, "portfolio_get"):
            return []
        return DB.portfolio_get(user_id)
    items = await run_sync(_run)
    return {"user_id": user_id, "items": items, "total": len(items)}


@app.post("/api/data/portfolio/add", tags=["Données Supabase"])
async def add_to_portfolio(item: PortfolioAddInput):
    """Ajoute un bien aux favoris."""
    def _run():
        if DB is None or not hasattr(DB, "portfolio_add"):
            return False
        return DB.portfolio_add(item.user_id, item.model_dump())
    ok = await run_sync(_run)
    return {"success": ok}


@app.delete("/api/data/portfolio/{user_id}/{listing_url:path}", tags=["Données Supabase"])
async def remove_from_portfolio(user_id: str, listing_url: str):
    """Retire un bien des favoris."""
    def _run():
        if DB is None or not hasattr(DB, "portfolio_remove"):
            return False
        return DB.portfolio_remove(user_id, listing_url)
    ok = await run_sync(_run)
    return {"success": ok}


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — ML BO1
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/ml/trust-score", tags=["BO1 — Market Reliability"])
async def trust_score_single(listing: ListingInput):
    """Trust Score XGBoost pour une annonce. Score de 0 à 1."""
    return await run_sync(_trust_score_sync,
        listing.price_value, listing.surface_m2, listing.city,
        listing.description, listing.source,
        listing.bedrooms, listing.bathrooms, listing.latitude)


@app.post("/api/ml/trust-score/batch", tags=["BO1 — Market Reliability"])
async def trust_score_batch(file: UploadFile = File(...)):
    """
    Score toutes les annonces d'un CSV uploadé.
    Les résultats sont automatiquement réécrits dans Supabase.
    """
    contents = await file.read()
    def _run(c):
        df = _read_csv_upload(c)
        return _score_df_and_push(df)
    return await run_sync(_run, contents, timeout=300.0)


@app.post("/api/ml/anomaly", tags=["BO1 — Market Reliability"])
async def anomaly_detect(data: AnomalyInput):
    """Détecte si un prix est aberrant (Isolation Forest M2)."""
    return await run_sync(_anomaly_sync,
        data.price_value, data.surface_m2, data.bedrooms)


@app.post("/api/ml/classify-type", tags=["BO1 — Market Reliability"])
async def classify_type(data: ClassifyInput):
    """Prédit le type de bien depuis le texte (TF-IDF + LinearSVC M3)."""
    return await run_sync(_classify_sync, data.title, data.description)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — ML BO2
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/ml/forecast/{city}", tags=["BO2 — Territorial Dynamics"])
async def price_forecast(city: str,
                          days_ahead: int = Query(30, ge=7, le=90)):
    """Prévision Prophet du prix/m² pour une ville."""
    result = await run_sync(_forecast_sync, city, days_ahead, timeout=10.0)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/ml/clusters", tags=["BO2 — Territorial Dynamics"])
async def market_clusters():
    """Segmentation K-Means de tous les marchés tunisiens."""
    return await run_sync(_clusters_all_sync)


@app.get("/api/ml/clusters/{city}", tags=["BO2 — Territorial Dynamics"])
async def city_cluster(city: str):
    """Segment de marché d'une ville spécifique."""
    result = await run_sync(_cluster_city_sync, city)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/ml/emerging", tags=["BO2 — Territorial Dynamics"])
async def emerging_zones_batch(file: UploadFile = File(...)):
    """Détecte les zones émergentes depuis un CSV (XGBoost M6)."""
    contents = await file.read()
    def _run(c):
        df = _read_csv_upload(c)
        for col in ["price_value", "surface_m2", "price"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        pv = "price_value" if "price_value" in df.columns else "price"
        sv = "surface_m2"  if "surface_m2"  in df.columns else "surface"
        df = df.dropna(subset=[pv, sv])
        df["price_per_m2"] = df[pv] / df[sv]
        city_stats = df.groupby("city").agg(
            median_price=("price_per_m2", "median"),
            volume=(pv, "count"),
        ).reset_index()
        results = []
        for _, row in city_stats.iterrows():
            r = _emerging_sync(row["city"], row["median_price"],
                                int(row["volume"]), None, 0.0)
            if r.get("is_emerging"):
                results.append(r)
        return {
            "n_emerging":    len(results),
            "emerging_zones": sorted(results, key=lambda x: -x.get("emergence_proba", 0)),
        }
    return await run_sync(_run, contents, timeout=120.0)


@app.post("/api/ml/emerging/predict", tags=["BO2 — Territorial Dynamics"])
async def emerging_predict(data: EmergenceInput):
    """Probabilité d'émergence pour une ville spécifique."""
    return await run_sync(_emerging_sync,
        data.city, data.median_price, data.volume,
        data.mean_price, data.std_price)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/pipeline/run", tags=["Pipeline"])
async def run_pipeline(
    csv_path: str = Body(
        default="data/processed/listings_clean_phase3.csv",
        embed=True,
        example="data/processed/listings_clean_phase3.csv"
    )
):
    """
    Déclenche le pipeline complet :
    1. Charge le CSV (ou Supabase si disponible)
    2. Score avec M1 + M2 + M3
    3. Pousse les résultats dans Supabase
    4. Retourne les statistiques du run
    """
    def _run():
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        t0 = datetime.utcnow()

        # Charger les données
        try:
            if DB and hasattr(DB, "load_listings"):
                df = DB.load_listings(limit=20000)
                if df is None or df.empty:
                    df = pd.read_csv(csv_path, on_bad_lines="skip", low_memory=False)
                    # Détection encodage/séparateur
                    if df.shape[1] <= 3:
                        df = pd.read_csv(csv_path, sep=";", on_bad_lines="skip")
                source = "supabase"
            else:
                df = pd.read_csv(csv_path, sep=";", on_bad_lines="skip",
                                  encoding="utf-8", low_memory=False)
                df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
                source = "csv"
        except Exception as e:
            return {"error": f"Chargement données : {e}"}

        n_in = len(df)
        stats = _score_df_and_push(df)
        elapsed = round((datetime.utcnow() - t0).total_seconds(), 1)

        # Logger le run dans Supabase
        if DB and hasattr(DB, "log_pipeline_run"):
            try:
                DB.log_pipeline_run(
                    run_id=run_id,
                    rows_in=n_in,
                    rows_out=stats["total"],
                    upsert_stats={"inserted": stats.get("n_pushed_to_db", 0)},
                    avg_trust=stats.get("mean_trust_score") or 0.0,
                    suspect_count=stats.get("n_suspect", 0),
                    sources=[source],
                    config={"csv_path": csv_path, "ml_version": "v4"},
                    status="success",
                )
            except Exception as e:
                logger.warning(f"[Pipeline] log_pipeline_run : {e}")

        return {
            "run_id":    run_id,
            "status":    "success",
            "duration_s": elapsed,
            "data_source": source,
            **stats,
        }

    return await run_sync(_run, timeout=600.0)


@app.get("/api/pipeline/status", tags=["Pipeline"])
async def pipeline_status():
    """Statut du dernier run de pipeline."""
    def _run():
        if DB is None:
            return {"status": "no_db"}
        db_stats = {}
        try:
            if hasattr(DB, "get_stats"):
                db_stats = DB.get_stats()
            elif hasattr(DB, "get_dashboard_stats"):
                db_stats = DB.get_dashboard_stats()
        except Exception:
            pass
        return {
            "db_connected":   DB is not None,
            "db_type":        "supabase" if getattr(DB, "is_available", False) else "sqlite",
            "db_stats":       db_stats,
            "ml_models_ready": all(MODELS.get(k) for k in ["m1_model","m2_model","m3_pipeline"]),
        }
    return await run_sync(_run)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — AGENTS (LangChain si OpenAI dispo, sinon direct)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/agents/bo1", tags=["Agents"])
async def run_bo1_agent(
    csv_path: str = Body(
        default="data/processed/listings_clean_phase3.csv",
        embed=True
    )
):
    """Pipeline BO1 complet. Utilise LangChain si OPENAI_API_KEY présente."""
    def _run():
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key and openai_key.startswith("sk-"):
            try:
                from agents.collector_agent import run_collector_pipeline
                return run_collector_pipeline(csv_path)
            except Exception as e:
                logger.warning(f"[Agent BO1] LangChain échoué ({e}) → mode direct")

        # Mode direct sans LLM
        try:
            df = pd.read_csv(csv_path, sep=";", on_bad_lines="skip",
                              encoding="utf-8", low_memory=False)
            df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
            return _score_df_and_push(df)
        except Exception as e:
            return {"error": str(e)}

    return await run_sync(_run, timeout=600.0)


@app.post("/api/agents/bo2", tags=["Agents"])
async def run_bo2_agent(
    csv_path: str = Body(
        default="data/processed/listings_clean_phase3.csv",
        embed=True
    )
):
    """Analyse territoriale BO2. Utilise LangChain si OPENAI_API_KEY présente."""
    def _run():
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key and openai_key.startswith("sk-"):
            try:
                from agents.territorial_agent import run_territorial_analysis
                return run_territorial_analysis(
                    "Analyse le marché immobilier tunisien — prévisions, clusters, zones émergentes"
                )
            except Exception as e:
                logger.warning(f"[Agent BO2] LangChain échoué ({e}) → mode direct")

        # Mode direct
        cities = ["Tunis", "Sousse", "Ariana", "Nabeul", "Ben Arous"]
        forecasts = {c: _forecast_sync(c, 30) for c in cities}
        clusters  = _clusters_all_sync()
        return {
            "status":    "success",
            "mode":      "direct",
            "forecasts": forecasts,
            "clusters":  clusters,
        }

    return await run_sync(_run, timeout=300.0)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES LIVE — données réelles depuis Supabase (colonnes : price, surface, rooms)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/live-stats", tags=["Live Data"])
async def live_stats_route():
    def _run():
        import os
        pg_url = os.getenv("DATABASE_URL", "")
        if not pg_url:
            return {"status":"error","error":"DATABASE_URL manquant"}
        try:
            from live_stats import get_live_stats
            return get_live_stats(pg_url)
        except Exception as e:
            return {"status":"error","error":str(e)}
    return await run_sync(_run, timeout=15.0)


@app.get("/api/live-listings", tags=["Live Data"])
async def live_listings_route(
    city:          str   = Query(None),
    property_type: str   = Query(None),
    source:        str   = Query(None),
    min_price:     float = Query(None),
    max_price:     float = Query(None),
    min_trust:     float = Query(None, ge=0.0, le=1.0),
    limit:         int   = Query(20, ge=1, le=200),
    offset:        int   = Query(0, ge=0),
):
    def _run():
        import os, psycopg2, decimal
        pg_url = os.getenv("DATABASE_URL", "")
        if not pg_url:
            return {"listings":[],"total":0}
        try:
            conn = psycopg2.connect(pg_url)
            cur  = conn.cursor()
            where = ["1=1"]; params = []
            if city:          where.append("LOWER(city) LIKE %s");   params.append(f"%{city.lower()}%")
            if property_type: where.append("property_type = %s");    params.append(property_type)
            if source:        where.append("source = %s");           params.append(source)
            if min_price:     where.append("price >= %s");           params.append(min_price)
            if max_price:     where.append("price <= %s");           params.append(max_price)
            if min_trust:     where.append("trust_score >= %s");     params.append(min_trust)
            ws = " AND ".join(where)
            cur.execute(f"SELECT COUNT(*) FROM listings WHERE {ws}", params)
            total = cur.fetchone()[0]
            cur.execute(f"""
                SELECT url,source,title,price,surface,rooms,property_type,
                       city,governorate,trust_score,trust_level,
                       latitude,longitude,price_per_m2
                FROM listings WHERE {ws} ORDER BY id DESC LIMIT %s OFFSET %s
            """, params + [limit, offset])
            cols = ["url","source","title","price","surface","rooms","property_type",
                    "city","governorate","trust_score","trust_level","latitude","longitude","price_per_m2"]
            listings = []
            for r in cur.fetchall():
                row = {}
                for k, v in zip(cols, r):
                    row[k] = float(v) if isinstance(v, decimal.Decimal) else v
                listings.append(row)
            cur.close(); conn.close()
            return {"listings":listings,"total":total,"source":"supabase_live"}
        except Exception as e:
            return {"listings":[],"total":0,"error":str(e)}
    return await run_sync(_run, timeout=15.0)
