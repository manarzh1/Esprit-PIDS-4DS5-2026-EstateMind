"""
Estate Mind — ml_risk_tools.py
=================================
Wrapper ML pour le trust scoring BO1.
Utilise le modèle XGBoost M1 sauvegardé.
Fallback automatique sur risk_tools.py (heuristiques) si M1 absent.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
warnings.filterwarnings("ignore")

_MODEL_CACHE: dict = {}


def _load_m1():
    if "model" in _MODEL_CACHE:
        return _MODEL_CACHE["model"], _MODEL_CACHE["encoders"]
    from joblib import load
    saved = Path(__file__).parent.parent / "models" / "saved"
    mp = saved / "m1_xgboost.joblib"
    ep = saved / "m1_encoders.joblib"
    if not mp.exists() or not ep.exists():
        return None, None
    _MODEL_CACHE["model"]    = load(mp)
    _MODEL_CACHE["encoders"] = load(ep)
    return _MODEL_CACHE["model"], _MODEL_CACHE["encoders"]


def _get_price(row: pd.Series) -> float:
    return float(row.get("price_value") or row.get("price") or 0)

def _get_surface(row: pd.Series) -> float:
    return float(row.get("surface_m2") or row.get("surface") or 1)


def predict_trust_score(
    price_value: float, surface_m2: float, city: str,
    description: str = "", source: str = "",
    bedrooms=None, bathrooms=None, latitude=None,
) -> dict:
    """Prédit le trust score ML pour une annonce."""
    model, encoders = _load_m1()

    if model is None:
        # Fallback heuristique
        from tools.risk_tools import compute_trust_score
        row = pd.Series({"price_value": price_value, "surface_m2": surface_m2,
                          "city": city, "description": description, "source": source})
        score = compute_trust_score(row, pd.DataFrame([row.to_dict()]))
        return {"trust_score": score, "label": "Fiable" if score >= 0.6 else "Suspect",
                "source": "heuristic_fallback"}

    ppm2     = price_value / max(surface_m2, 1)
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
        "bedrooms":  bedrooms  if bedrooms  is not None else -1,
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
        "source":       "ml_xgboost_m1",
    }


def predict_trust_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Score un DataFrame complet. Ajoute trust_score et trust_label."""
    model, encoders = _load_m1()
    df = df.copy()

    if model is None:
        logger.warning("[ML Risk] M1 absent — fallback heuristique")
        from tools.risk_tools import run_trust_scoring
        df = run_trust_scoring(df)
        return df

    scores, labels = [], []
    for _, row in df.iterrows():
        try:
            r = predict_trust_score(
                _get_price(row), _get_surface(row),
                str(row.get("city","")), str(row.get("description","")),
                str(row.get("source","")),
                row.get("bedrooms"), row.get("bathrooms"), row.get("latitude"),
            )
            scores.append(r["trust_score"])
            labels.append(r["label"])
        except Exception:
            scores.append(0.5); labels.append("Moyen")

    df["trust_score"] = scores
    df["trust_label"] = labels
    df["trust_level"] = labels   # compatibilité
    logger.info(f"[ML Risk] Batch OK — {len(df)} annonces scorées")
    return df


def detect_anomaly(price_value: float, surface_m2: float, bedrooms=None) -> dict:
    """Détecte si un prix est aberrant via Isolation Forest M2."""
    from joblib import load
    saved = Path(__file__).parent.parent / "models" / "saved"
    m2p = saved / "m2_isolation_forest.joblib"
    scp = saved / "m2_scaler.joblib"
    stp = saved / "m2_stats.joblib"

    if not m2p.exists():
        ppm2 = price_value / max(surface_m2, 1)
        return {"is_anomaly": ppm2 < 50 or ppm2 > 20000,
                "anomaly_score": 0.5, "price_per_m2": round(ppm2, 2), "source": "heuristic"}

    model  = load(m2p)
    scaler = load(scp)
    stats  = load(stp)
    ppm2   = price_value / max(surface_m2, 1)
    meds   = stats.get("medians", {})
    X  = pd.DataFrame([{"price_value": price_value, "surface_m2": surface_m2,
                         "price_per_m2": ppm2,
                         "bedrooms": bedrooms if bedrooms is not None else meds.get("bedrooms", 2)}])
    Xs = scaler.transform(X)
    dec = float(model.decision_function(Xs)[0])
    return {
        "is_anomaly":    bool(model.predict(Xs)[0] == -1),
        "anomaly_score": round(max(0, min(1, -dec / 0.5)), 4),
        "price_per_m2":  round(ppm2, 2),
        "source":        "isolation_forest_m2",
    }
