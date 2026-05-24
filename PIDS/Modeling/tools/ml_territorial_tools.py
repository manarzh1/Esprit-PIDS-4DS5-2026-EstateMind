"""
Estate Mind — ml_territorial_tools.py
=======================================
Wrappers ML pour l'analyse territoriale BO2.
Utilise M4 Prophet (JSON), M5 K-Means, M6 XGBoost.
"""
from __future__ import annotations
import json, warnings
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
warnings.filterwarnings("ignore")

SAVED_DIR = Path(__file__).parent.parent / "models" / "saved"


def compute_price_forecast(city: str, days_ahead: int = 30) -> dict:
    """Prévision de prix Prophet M4 pour une ville."""
    fc_path = SAVED_DIR / "m4_forecasts.json"
    if not fc_path.exists():
        return {"error": "m4_forecasts.json introuvable — lancez fix_prophet.py"}
    with open(fc_path, encoding="utf-8") as f:
        all_fc = json.load(f)
    forecasts = all_fc.get("forecasts", {})
    city_match = next((c for c in forecasts if c.lower() == city.lower()), None)
    if not city_match:
        return {"error": f"Ville '{city}' non disponible",
                "available": list(forecasts.keys())}
    data = forecasts[city_match]
    rows = data.get("forecast", [])[:days_ahead]
    predicted = [r["predicted"] for r in rows]
    return {
        "city":             city_match,
        "days_ahead":       len(rows),
        "mean_predicted":   round(sum(predicted) / max(len(predicted), 1), 0),
        "last_known_price": data.get("last_known_price"),
        "model_mape":       data.get("mape_pct"),
        "synthetic_dates":  data.get("synthetic_dates", True),
        "forecast":         rows,
    }


def compute_multi_city_forecast(cities: list, days_ahead: int = 30) -> dict:
    """Forecast pour plusieurs villes en une fois."""
    results = {}
    for city in cities:
        r = compute_price_forecast(city, days_ahead)
        if "error" not in r:
            results[city] = r
    return results


def compute_market_segments() -> dict:
    """Segmentation K-Means M5 — tous les segments."""
    from joblib import load
    stats_path = SAVED_DIR / "m5_city_stats.joblib"
    if not stats_path.exists():
        return {"error": "M5 non disponible — lancez train_and_save.py"}
    stats = load(stats_path)
    return {
        "n_clusters":       len(stats.get("cluster_profiles", [])),
        "cluster_profiles": stats.get("cluster_profiles", []),
        "n_cities":         len(stats.get("city_cluster_map", {})),
        "national_median":  round(stats.get("national_median", 0), 0),
        "source":           "kmeans_m5",
    }


def get_city_market_segment(city: str) -> dict:
    """Segment de marché d'une ville spécifique."""
    from joblib import load
    stats_path = SAVED_DIR / "m5_city_stats.joblib"
    if not stats_path.exists():
        return {"error": "M5 non disponible"}
    stats    = load(stats_path)
    cmap     = stats.get("city_cluster_map", {})
    profiles = stats.get("cluster_profiles", [])
    cid = cmap.get(city) or next(
        (v for c, v in cmap.items() if c.lower() == city.lower()), None
    )
    if cid is None:
        return {"error": f"Ville '{city}' non trouvée", "available": list(cmap.keys())}
    profile = next((p for p in profiles if p["cluster_id"] == cid), {})
    return {"city": city, "cluster_id": int(cid), "profile": profile}


def detect_emerging_zones_ml(df: pd.DataFrame) -> list:
    """Détecte les zones émergentes avec XGBoost M6."""
    from joblib import load
    m6p  = SAVED_DIR / "m6_xgboost.joblib"
    lep  = SAVED_DIR / "m6_city_encoder.joblib"
    stp  = SAVED_DIR / "m6_city_stats.joblib"
    if not m6p.exists():
        return []

    model  = load(m6p)
    le     = load(lep)
    stats  = load(stp)
    nat_med = stats["national_median"]
    avg_vol = stats["avg_vol_per_city"]
    classes = stats["city_encoder_classes"]

    pv = "price_value" if "price_value" in df.columns else "price"
    sv = "surface_m2"  if "surface_m2"  in df.columns else "surface"
    df = df.dropna(subset=[pv, sv])
    df["_ppm2"] = df[pv] / df[sv].replace(0, np.nan)

    city_stats = df.groupby("city").agg(
        median_price=("_ppm2", "median"),
        mean_price  =("_ppm2", "mean"),
        volume      =(pv,      "count"),
        std_price   =("_ppm2", "std"),
    ).reset_index().dropna(subset=["median_price"])

    results = []
    for _, row in city_stats.iterrows():
        city     = str(row["city"])
        city2    = city if city in classes else classes[0]
        city_enc = int(le.transform([city2])[0])
        mp = float(row["median_price"])
        X  = pd.DataFrame([{
            "median_price":      mp,
            "mean_price":        float(row.get("mean_price", mp)),
            "volume":            int(row["volume"]),
            "std_price":         float(row.get("std_price", 0) or 0),
            "city_median":       mp,
            "city_volume":       int(row["volume"]),
            "price_vs_national": mp / nat_med,
            "vol_vs_national":   int(row["volume"]) / (avg_vol + 1),
            "city_enc":          city_enc,
        }])
        proba = float(model.predict_proba(X)[0][1])
        if model.predict(X)[0] == 1:
            results.append({
                "city":              city,
                "is_emerging":       True,
                "emergence_proba":   round(proba, 4),
                "price_vs_national": round(mp / nat_med, 3),
                "national_median":   round(nat_med, 0),
            })

    return sorted(results, key=lambda x: -x["emergence_proba"])


def predict_zone_emergence(city: str, median_price: float, volume: int) -> dict:
    """Prédit si une zone spécifique est émergente."""
    from joblib import load
    m6p = SAVED_DIR / "m6_xgboost.joblib"
    lep = SAVED_DIR / "m6_city_encoder.joblib"
    stp = SAVED_DIR / "m6_city_stats.joblib"
    if not m6p.exists():
        return {"error": "M6 non disponible"}

    model   = load(m6p)
    le      = load(lep)
    stats   = load(stp)
    nat_med = stats["national_median"]
    avg_vol = stats["avg_vol_per_city"]
    classes = stats["city_encoder_classes"]

    city2    = city if city in classes else classes[0]
    city_enc = int(le.transform([city2])[0])

    X = pd.DataFrame([{
        "median_price": median_price, "mean_price": median_price,
        "volume": volume, "std_price": 0.0,
        "city_median": median_price, "city_volume": volume,
        "price_vs_national": median_price / nat_med,
        "vol_vs_national":   volume / (avg_vol + 1),
        "city_enc": city_enc,
    }])
    proba = float(model.predict_proba(X)[0][1])
    return {
        "city":              city,
        "is_emerging":       bool(model.predict(X)[0] == 1),
        "emergence_proba":   round(proba, 4),
        "price_vs_national": round(median_price / nat_med, 3),
        "national_median":   round(nat_med, 0),
    }


def generate_territorial_report(df: pd.DataFrame, cities: list) -> dict:
    """Rapport territorial complet : forecast + clusters + emerging."""
    report = {
        "cities": cities,
        "forecasts": compute_multi_city_forecast(cities, days_ahead=30),
        "market_segments": compute_market_segments(),
        "emerging_zones": detect_emerging_zones_ml(df),
    }
    return report
