"""
Estate Mind — Risk / Trust Detection Tools
Calcule un trust_score [0-1] par annonce immobilière.
Score proche de 1 = annonce fiable, proche de 0 = suspect.
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from loguru import logger


# ─── Features du modèle de scoring ───────────────────────────────────────────

def _score_price_coherence(price: float, surface: float,
                            city: str, df_ref: pd.DataFrame) -> float:
    """
    Compare le prix/m² de l'annonce à la médiane de sa ville.
    Retourne 1.0 si cohérent, < 0.5 si aberrant.
    """
    if pd.isna(price) or pd.isna(surface) or surface <= 0:
        return 0.5  # score neutre si données manquantes

    price_per_m2 = price / surface
    city_lower = str(city).lower()

    ref = df_ref[df_ref["city"].str.lower() == city_lower]
    if len(ref) < 5:
        ref = df_ref  # fallback sur tout le dataset

    if "price_per_m2" in ref.columns:
        median_ppm2 = ref["price_per_m2"].median()
        std_ppm2    = ref["price_per_m2"].std()
    else:
        median_ppm2 = (ref["price"] / ref["surface"]).median()
        std_ppm2    = (ref["price"] / ref["surface"]).std()

    if pd.isna(median_ppm2) or pd.isna(std_ppm2) or std_ppm2 == 0:
        return 0.7

    z_score = abs(price_per_m2 - median_ppm2) / std_ppm2
    # z < 1.5 → très cohérent, z > 4 → très suspect
    score = max(0.0, 1.0 - z_score / 4.0)
    return round(score, 3)


def _score_description_quality(description: str) -> float:
    """
    Évalue la qualité de la description textuelle.
    Critères : longueur, mots-clés suspects, cohérence.
    """
    if not description or len(description.strip()) < 20:
        return 0.3

    desc = description.lower()
    score = 0.7  # base

    # Bonus longueur raisonnable
    word_count = len(desc.split())
    if 30 <= word_count <= 300:
        score += 0.1
    elif word_count > 300:
        score += 0.05

    # Malus mots suspects
    suspect_words = [
        "urgent", "affaire exceptionnelle", "prix cassé", "ne pas rater",
        "contact direct", "sans intermédiaire", "paiement cash uniquement",
        "pas de visite", "à saisir", "offre limitée", "promotion flash",
    ]
    suspect_hits = sum(1 for w in suspect_words if w in desc)
    score -= suspect_hits * 0.15

    # Bonus mots de qualité
    quality_words = [
        "acte notarié", "titre foncier", "permis de construire",
        "vue mer", "résidence sécurisée", "ascenseur", "gardien",
        "parking", "climatisation", "chauffage central",
    ]
    quality_hits = sum(1 for w in quality_words if w in desc)
    score += quality_hits * 0.05

    return round(max(0.0, min(1.0, score)), 3)


def _score_data_completeness(row: pd.Series) -> float:
    """
    Évalue la complétude des champs essentiels d'une annonce.
    """
    key_fields = {
        "price":        0.25,
        "surface":      0.20,
        "property_type": 0.15,
        "city":         0.15,
        "description":  0.15,
        "url":          0.10,
    }

    score = 0.0
    for field, weight in key_fields.items():
        val = row.get(field, np.nan)
        if not pd.isna(val) and str(val).strip() not in ("", "nan", "autre"):
            score += weight

    return round(score, 3)


def _score_source_reliability(source: str) -> float:
    """
    Pondère la fiabilité selon la source de l'annonce.
    Les agences professionnelles sont plus fiables que les particuliers.
    """
    source_scores = {
        "remax":     0.92,
        "tecnocasa": 0.90,
        "century21": 0.92,
        "tps":       0.85,
        "mubawab":   0.78,
        "tayara":    0.65,  # marketplace ouverte → plus de bruit
        "orpi":      0.88,
        "darkom":    0.75,
    }
    if pd.isna(source):
        return 0.60

    s = str(source).lower()
    for key, val in source_scores.items():
        if key in s:
            return val
    return 0.65


def _detect_duplicate_risk(row: pd.Series, df: pd.DataFrame) -> float:
    """
    Détecte si une annonce ressemble à d'autres (quasi-doublons).
    Retourne 0.8 si unique, < 0.5 si très similaire à d'autres.
    """
    similar = df[
        (df["price"] == row.get("price")) &
        (df["surface"] == row.get("surface")) &
        (df["city"] == row.get("city"))
    ]

    n_similar = len(similar) - 1  # -1 pour l'annonce elle-même
    if n_similar == 0:
        return 0.9
    elif n_similar <= 2:
        return 0.7
    else:
        return max(0.3, 0.7 - n_similar * 0.1)


# ─── Pipeline principal ───────────────────────────────────────────────────────

def compute_trust_score(row: pd.Series, df_ref: pd.DataFrame) -> float:
    """
    Calcule le trust_score composite pour une annonce.
    Combine 5 dimensions pondérées → score [0-1].
    """
    weights = {
        "price_coherence":    0.30,
        "description":        0.20,
        "completeness":       0.25,
        "source":             0.15,
        "duplicate_risk":     0.10,
    }

    scores = {
        "price_coherence": _score_price_coherence(
            row.get("price"),
            row.get("surface"),
            row.get("city", ""),
            df_ref,
        ),
        "description":     _score_description_quality(
            str(row.get("description", ""))
        ),
        "completeness":    _score_data_completeness(row),
        "source":          _score_source_reliability(
            str(row.get("source", ""))
        ),
        "duplicate_risk":  _detect_duplicate_risk(row, df_ref),
    }

    trust = sum(s * weights[k] for k, s in scores.items())
    return round(float(trust), 3)


def run_trust_scoring(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique le calcul de trust_score sur tout le dataframe.
    Ajoute la colonne 'trust_score' et 'trust_level'.
    """
    logger.info(f"Trust scoring démarré — {len(df)} annonces")

    trust_scores = []
    for _, row in df.iterrows():
        score = compute_trust_score(row, df)
        trust_scores.append(score)

    df["trust_score"] = trust_scores
    df["trust_level"]  = df["trust_score"].apply(
        lambda s: "Fiable" if s >= 0.75 else ("Moyen" if s >= 0.50 else "Suspect")
    )

    stats = {
        "mean":    round(df["trust_score"].mean(), 3),
        "median":  round(df["trust_score"].median(), 3),
        "fiable":  (df["trust_score"] >= 0.75).sum(),
        "moyen":   ((df["trust_score"] >= 0.50) & (df["trust_score"] < 0.75)).sum(),
        "suspect": (df["trust_score"] < 0.50).sum(),
    }
    logger.info(f"Trust scoring terminé : {stats}")
    return df


def get_suspicious_listings(df: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Retourne les annonces suspectes (trust_score < threshold)."""
    if "trust_score" not in df.columns:
        df = run_trust_scoring(df)
    return df[df["trust_score"] < threshold].sort_values("trust_score")


def get_fraud_flags(row: pd.Series, df_ref: pd.DataFrame) -> list[str]:
    """Retourne la liste des signaux suspects pour une annonce."""
    flags = []
    price    = row.get("price")
    surface  = row.get("surface")
    city     = row.get("city", "")
    desc     = str(row.get("description", "")).lower()

    # Prix trop bas
    if not pd.isna(price) and not pd.isna(surface) and surface > 0:
        ppm2 = price / surface
        ref_ppm2 = (df_ref["price"] / df_ref["surface"]).median()
        if ppm2 < ref_ppm2 * 0.3:
            flags.append("Prix/m² anormalement bas (< 30% de la médiane)")
        if ppm2 > ref_ppm2 * 4:
            flags.append("Prix/m² anormalement élevé (> 400% de la médiane)")

    # Description suspecte
    suspect_phrases = [
        ("paiement cash uniquement", "Paiement cash exigé"),
        ("pas de visite", "Visite refusée"),
        ("urgent", "Vente urgente"),
        ("sans intermédiaire", "Contact direct suspect"),
    ]
    for phrase, flag in suspect_phrases:
        if phrase in desc:
            flags.append(flag)

    # Données manquantes critiques
    if pd.isna(price):
        flags.append("Prix non renseigné")
    if pd.isna(surface) or surface <= 0:
        flags.append("Surface non renseignée ou invalide")

    return flags
