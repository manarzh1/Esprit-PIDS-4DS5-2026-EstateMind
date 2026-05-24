"""
Estate Mind — Fuzzy Deduplication
════════════════════════════════════
Détecte les quasi-doublons inter-sources que la déduplication exacte rate.

Exemple :
  Tayara  : "Appartement S+2 La Marsa 120m² 310 000 TND"
  Mubawab : "Appt 3 pièces Marsa bord mer 310000dt"
  → Même annonce, URLs différentes → détectée et fusionnée

Algorithme en 2 passes :
  1. Filtrage rapide : regroupement par (price_bucket, city_normalized)
     → Réduit les comparaisons de O(n²) à O(k²) par groupe
  2. Score de similarité composite sur 4 dimensions :
     - Prix     : |p1-p2| / max(p1,p2)             (30%)
     - Surface  : |s1-s2| / max(s1,s2)             (25%)
     - Titre    : similarité Jaccard des n-grammes  (25%)
     - Localisation : match exact city_normalized   (20%)

Seuil par défaut : 0.85 → deux annonces à ≥85% de similarité = doublon.
La source avec la meilleure priorité est conservée.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


# ── Hyperparamètre central ────────────────────────────────────────────────────

DEFAULT_SIMILARITY_THRESHOLD = 0.85   # [0-1] — plus bas = plus agressif

# Priorité de source (source gardée en cas de doublon)
SOURCE_PRIORITY = {
    "remax":     1,
    "tecnocasa": 2,
    "mubawab":   3,
    "tayara":    4,
    "csv":       5,
}


# ── Helpers de normalisation ──────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """Normalise un texte pour la comparaison : minuscules, sans accents, sans ponctuation."""
    if not text or pd.isna(text):
        return ""
    t = str(text).lower().strip()
    # Supprime les accents
    t = "".join(
        c for c in unicodedata.normalize("NFD", t)
        if unicodedata.category(c) != "Mn"
    )
    # Supprime la ponctuation et les caractères spéciaux
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _price_bucket(price: float, bucket_size: int = 15_000) -> int:
    """Arrondit un prix au bucket le plus proche pour le filtrage rapide."""
    if pd.isna(price) or price <= 0:
        return -1
    return int(price // bucket_size) * bucket_size


def _city_normalized(city: str) -> str:
    """Normalise une ville pour regroupement."""
    return _normalize_text(city)[:20]


def _ngrams(text: str, n: int = 3) -> set:
    """Génère les n-grammes de caractères d'un texte."""
    t = _normalize_text(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i+n] for i in range(len(t) - n + 1)}


def _jaccard_similarity(text1: str, text2: str, n: int = 3) -> float:
    """Similarité de Jaccard sur les trigrammes de deux textes."""
    set1 = _ngrams(text1, n)
    set2 = _ngrams(text2, n)
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    inter = len(set1 & set2)
    union = len(set1 | set2)
    return inter / union


# ── Score de similarité composite ────────────────────────────────────────────

def _compute_similarity(row1: pd.Series, row2: pd.Series) -> float:
    """
    Score composite de similarité entre deux annonces [0-1].

    Dimensions :
      - Prix     (30%) : ratio de différence de prix
      - Surface  (25%) : ratio de différence de surface
      - Titre    (25%) : similarité Jaccard des trigrammes
      - Ville    (20%) : match exact après normalisation
    """
    weights = {"price": 0.30, "surface": 0.25, "title": 0.25, "city": 0.20}
    scores  = {}

    # Prix
    p1 = float(row1.get("price") or 0)
    p2 = float(row2.get("price") or 0)
    if p1 > 0 and p2 > 0:
        scores["price"] = 1.0 - abs(p1 - p2) / max(p1, p2)
    else:
        scores["price"] = 0.5   # neutre si prix manquant

    # Surface
    s1 = float(row1.get("surface") or 0)
    s2 = float(row2.get("surface") or 0)
    if s1 > 0 and s2 > 0:
        scores["surface"] = 1.0 - abs(s1 - s2) / max(s1, s2)
    else:
        scores["surface"] = 0.5

    # Titre
    t1 = str(row1.get("title") or "")
    t2 = str(row2.get("title") or "")
    scores["title"] = _jaccard_similarity(t1, t2)

    # Ville
    c1 = _city_normalized(str(row1.get("city") or ""))
    c2 = _city_normalized(str(row2.get("city") or ""))
    scores["city"] = 1.0 if (c1 and c1 == c2) else 0.0

    return sum(scores[k] * weights[k] for k in weights)


# ── Pipeline de déduplication ────────────────────────────────────────────────

def run_fuzzy_dedup(
    df: pd.DataFrame,
    threshold:     float = DEFAULT_SIMILARITY_THRESHOLD,
    price_bucket:  int   = 15_000,
    max_group_size: int  = 50,     # limite anti-explosion O(n²)
) -> pd.DataFrame:
    """
    Déduplique le DataFrame en deux passes :
      1. Regroupement par (price_bucket, city_normalized)
      2. Comparaison par paires dans chaque groupe

    Args:
        df             : DataFrame avec colonnes price, surface, title, city, source
        threshold      : seuil de similarité [0-1]
        price_bucket   : taille des buckets de prix pour le filtrage
        max_group_size : taille max d'un groupe (évite O(n²) explosif)

    Returns:
        DataFrame dédupliqué avec colonne 'fuzzy_dup_of' (index du doublon maître)
    """
    if df.empty:
        return df

    logger.info(f"[FuzzyDedup] Démarrage sur {len(df)} annonces (threshold={threshold})")
    t0 = __import__("time").time()

    df = df.copy().reset_index(drop=True)
    df["_price_bucket"] = df["price"].apply(lambda p: _price_bucket(float(p) if pd.notna(p) else 0, price_bucket))
    df["_city_norm"]    = df["city"].apply(lambda c: _city_normalized(str(c) if pd.notna(c) else ""))
    df["_priority"]     = df["source"].map(SOURCE_PRIORITY).fillna(99)
    df["fuzzy_dup_of"]  = -1   # -1 = pas un doublon

    # Trie par priorité de source → la meilleure source est traitée en premier
    df = df.sort_values("_priority").reset_index(drop=True)

    # Index des annonces confirmées comme doublons
    dup_indices: set = set()

    # Regroupement par (price_bucket, city_norm)
    groups: dict = defaultdict(list)
    for idx, row in df.iterrows():
        key = (row["_price_bucket"], row["_city_norm"])
        groups[key].append(idx)

    n_pairs_checked = 0
    n_dups_found    = 0

    for key, indices in groups.items():
        if len(indices) < 2:
            continue
        if len(indices) > max_group_size:
            # Groupe trop grand → sous-échantillonnage pour éviter O(n²)
            indices = indices[:max_group_size]

        for i in range(len(indices)):
            idx_i = indices[i]
            if idx_i in dup_indices:
                continue   # déjà identifié comme doublon

            for j in range(i + 1, len(indices)):
                idx_j = indices[j]
                if idx_j in dup_indices:
                    continue

                n_pairs_checked += 1
                sim = _compute_similarity(df.loc[idx_i], df.loc[idx_j])

                if sim >= threshold:
                    # idx_j est un doublon de idx_i (idx_i a meilleure priorité car trié)
                    df.loc[idx_j, "fuzzy_dup_of"] = idx_i
                    dup_indices.add(idx_j)
                    n_dups_found += 1

    # Suppression des doublons
    df_clean = df[df["fuzzy_dup_of"] == -1].copy()
    df_clean = df_clean.drop(columns=["_price_bucket", "_city_norm", "_priority", "fuzzy_dup_of"])

    elapsed = round(__import__("time").time() - t0, 2)
    logger.info(
        f"[FuzzyDedup] ✅ {n_dups_found} quasi-doublons supprimés "
        f"({n_pairs_checked} paires comparées) en {elapsed}s"
        f" → {len(df_clean)} annonces uniques"
    )
    return df_clean.reset_index(drop=True)


def find_similar_to(
    listing: pd.Series,
    df:      pd.DataFrame,
    threshold: float = 0.75,
    top_k:     int   = 5,
) -> pd.DataFrame:
    """
    Trouve les annonces les plus similaires à une annonce de référence.
    Utile pour la page "Annonces similaires" du frontend.
    """
    if df.empty:
        return pd.DataFrame()

    sims = []
    for idx, row in df.iterrows():
        sim = _compute_similarity(listing, row)
        if sim >= threshold:
            sims.append((idx, sim))

    sims.sort(key=lambda x: x[1], reverse=True)
    top_indices = [i for i, _ in sims[:top_k]]

    result = df.loc[top_indices].copy()
    result["similarity_score"] = [s for _, s in sims[:top_k]]
    return result
