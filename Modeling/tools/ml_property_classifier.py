"""
Estate Mind — ml_property_classifier.py
=========================================
Wrapper ML pour la classification NLP du type de bien (M3).
Utilise TF-IDF + LinearSVC sauvegardé.
Fallback sur règles par mots-clés si M3 absent.
"""
from __future__ import annotations
import warnings
import pandas as pd
from pathlib import Path
from loguru import logger
warnings.filterwarnings("ignore")

_PIPELINE_CACHE: dict = {}

KEYWORD_RULES = [
    ("studio",       ["studio", "garçonnière"]),
    ("villa",        ["villa", "duplex", "triplex"]),
    ("terrain",      ["terrain", "parcelle", "hectare"]),
    ("maison",       ["maison", " dar ", "bungalow"]),
    ("bureau_local", ["bureau", "local commercial", "boutique", "magasin"]),
    ("appartement",  ["appartement", "appart", "s+1","s+2","s+3","s+4","s+5","s+0"]),
]


def _load_m3():
    if "pipeline" in _PIPELINE_CACHE:
        return _PIPELINE_CACHE["pipeline"]
    from joblib import load
    p = Path(__file__).parent.parent / "models" / "saved" / "m3_nlp_pipeline.joblib"
    if not p.exists():
        return None
    _PIPELINE_CACHE["pipeline"] = load(p)
    return _PIPELINE_CACHE["pipeline"]


def _keyword_classify(title: str) -> str:
    t = str(title).lower()
    for label, kws in KEYWORD_RULES:
        if any(k in t for k in kws):
            return label
    return "appartement"


def classify_property_type(title: str, description: str = "") -> dict:
    """Classifie le type de bien depuis le texte."""
    pipeline = _load_m3()
    text = (str(title) + " " + str(description)).lower().strip()

    if not pipeline:
        label = _keyword_classify(title)
        return {"property_type": label, "confidence": 0.7, "source": "keyword_fallback"}

    pred = pipeline.predict([text])[0]
    clf  = pipeline.named_steps.get("clf")
    conf = 0.8
    if clf and hasattr(clf, "decision_function"):
        import numpy as np
        scores = pipeline.decision_function([text])[0]
        if hasattr(scores, "__len__"):
            conf = round(float(abs(scores).max() / (abs(scores).sum() + 1e-9)), 4)
    return {"property_type": pred, "confidence": min(1.0, conf), "source": "tfidf_linearsvc_m3"}


def classify_property_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Classifie le type de bien pour tout un DataFrame."""
    pipeline = _load_m3()
    df = df.copy()

    if pipeline is None:
        logger.warning("[ML Classifier] M3 absent — fallback mots-clés")
        df["property_type_ml"] = df["title"].fillna("").apply(_keyword_classify)
    else:
        texts = (df.get("title", pd.Series("")).fillna("") + " " +
                 df.get("description", pd.Series("")).fillna("")).str.lower()
        df["property_type_ml"] = pipeline.predict(texts)

    # Corriger les types génériques dans property_type
    if "property_type" in df.columns:
        generic = {"immobilier","autre","194","231","211","20","22","","nan"}
        mask = df["property_type"].fillna("").str.lower().isin(generic)
        df.loc[mask, "property_type"] = df.loc[mask, "property_type_ml"]

    logger.info(f"[ML Classifier] Batch OK — {len(df)} annonces classifiées")
    return df
