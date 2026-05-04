"""
Estate Mind — agents_direct.py
================================
Mode direct sans clé OpenAI.
Appelle les modèles ML directement sans passer par LangChain.
"""
from __future__ import annotations
import json, os, sys, warnings
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger
warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_csv(csv_path: str) -> pd.DataFrame:
    for enc in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            df = pd.read_csv(csv_path, sep=";", encoding=enc, on_bad_lines="skip", low_memory=False)
            df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
            if df.shape[1] > 3:
                return df
        except Exception:
            continue
    raise ValueError(f"Impossible de lire {csv_path}")


def run_bo1_pipeline(csv_path: str, save_to_db: bool = True) -> dict:
    """Pipeline BO1 complet sans LLM : trust score + anomaly + NLP + sentiment."""
    logger.info(f"[BO1 Direct] Démarrage — {csv_path}")
    result = {"timestamp": datetime.now().isoformat(), "steps_completed": [], "stats": {}, "errors": []}

    # Chargement
    try:
        df = _read_csv(csv_path)
        for col in ["price_value", "surface_m2", "latitude", "bedrooms", "bathrooms"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "price_per_m2" not in df.columns:
            df["price_per_m2"] = df["price_value"] / df["surface_m2"].replace(0, np.nan)
        logger.info(f"[BO1] {len(df):,} annonces chargées")
        result["steps_completed"].append("loading")
        result["stats"]["n_initial"] = len(df)
    except Exception as e:
        result["errors"].append(f"Chargement: {e}")
        return result

    # Trust Score M1
    try:
        from models.inference_engine import predict_trust_batch
        df = predict_trust_batch(df)
        n_f = int((df.get("trust_label", pd.Series()) == "Fiable").sum())
        n_s = int((df.get("trust_label", pd.Series()) == "Suspect").sum())
        result["steps_completed"].append("trust_score_m1")
        result["stats"]["trust"] = {"n_fiable": n_f, "n_suspect": n_s,
                                     "avg": round(float(df["trust_score"].mean()), 4)}
        logger.info(f"[BO1] Trust OK — Fiable={n_f} Suspect={n_s}")
    except Exception as e:
        result["errors"].append(f"Trust: {e}")

    # Anomaly M2
    try:
        from models.inference_engine import detect_anomaly_batch
        df = detect_anomaly_batch(df)
        n_a = int(df["is_anomaly"].sum())
        result["steps_completed"].append("anomaly_m2")
        result["stats"]["anomalies"] = {"n_detected": n_a}
        logger.info(f"[BO1] Anomaly OK — {n_a} détectées")
    except Exception as e:
        result["errors"].append(f"Anomaly: {e}")

    # NLP M3
    try:
        from models.inference_engine import classify_property_batch
        df = classify_property_batch(df)
        result["steps_completed"].append("nlp_m3")
        logger.info("[BO1] NLP OK")
    except Exception as e:
        result["errors"].append(f"NLP: {e}")

    # Sentiment
    try:
        from tools.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer(use_llm=False)
        df = analyzer.analyze_batch(df, use_llm=False)
        result["steps_completed"].append("sentiment")
        logger.info("[BO1] Sentiment OK")
    except Exception as e:
        result["errors"].append(f"Sentiment: {e}")

    # DB
    if save_to_db:
        try:
            from db.db_manager import get_db
            db = get_db()
            db.insert_annonces(df)
            result["steps_completed"].append("db_write")
        except Exception as e:
            result["errors"].append(f"DB: {e}")

    result["stats"]["n_steps_ok"] = len(result["steps_completed"])
    result["stats"]["n_errors"]   = len(result["errors"])
    logger.info(f"[BO1 Direct] Terminé — {len(result['steps_completed'])} étapes OK")
    return result


def run_bo2_analysis(csv_path: str, cities: list = None) -> dict:
    """Analyse BO2 complète sans LLM : forecast + clusters + emerging."""
    if cities is None:
        cities = ["Tunis", "Sousse", "Ariana", "Nabeul", "Ben Arous"]
    logger.info("[BO2 Direct] Démarrage")
    result = {"timestamp": datetime.now().isoformat(), "cities_analyzed": cities,
              "steps_completed": [], "forecast": {}, "clusters": {}, "emerging": [], "errors": []}

    try:
        df = _read_csv(csv_path)
        for col in ["price_value", "surface_m2", "latitude", "longitude"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["price_per_m2"] = df["price_value"] / df["surface_m2"].replace(0, np.nan)
        df = df[df["price_per_m2"].between(100, 15_000)]
    except Exception as e:
        result["errors"].append(f"Chargement: {e}")
        return result

    # M4 Forecast
    try:
        from models.inference_engine import forecast_price
        for city in cities:
            fc = forecast_price(city, days_ahead=30)
            if "error" not in fc:
                result["forecast"][city] = {"mean_predicted": fc.get("mean_predicted"), "mape": fc.get("model_mape")}
        result["steps_completed"].append("forecast_m4")
        logger.info(f"[BO2] Forecast OK — {len(result['forecast'])} villes")
    except Exception as e:
        result["errors"].append(f"Forecast: {e}")

    # M5 Clusters
    try:
        from models.inference_engine import get_all_clusters
        result["clusters"] = get_all_clusters()
        result["steps_completed"].append("clustering_m5")
        logger.info("[BO2] Clusters OK")
    except Exception as e:
        result["errors"].append(f"Clustering: {e}")

    # M6 Emerging
    try:
        from tools.ml_territorial_tools import detect_emerging_zones_ml
        result["emerging"] = detect_emerging_zones_ml(df)
        result["steps_completed"].append("emerging_m6")
        logger.info(f"[BO2] Emerging OK — {len(result['emerging'])} zones")
    except Exception as e:
        result["errors"].append(f"Emerging: {e}")

    result["stats"] = {"n_steps_ok": len(result["steps_completed"]),
                       "n_errors": len(result["errors"]),
                       "n_emerging": len(result["emerging"])}
    logger.info(f"[BO2 Direct] Terminé — {len(result['steps_completed'])} étapes OK")
    return result


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/listings_clean_phase3.csv"
    print("\n[BO1] Pipeline direct...")
    r1 = run_bo1_pipeline(csv_path, save_to_db=False)
    print(f"  Étapes : {r1['steps_completed']}")
    print(f"  Stats  : {r1['stats']}")
    print("\n[BO2] Analyse directe...")
    r2 = run_bo2_analysis(csv_path, cities=["Tunis", "Sousse"])
    print(f"  Étapes : {r2['steps_completed']}")
