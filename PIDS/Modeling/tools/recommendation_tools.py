"""
Estate Mind — Recommendation Engine
═════════════════════════════════════
3 algorithmes de recommandation :

① MATCHING      : score de compatibilité acheteur ↔ annonces (filtrage collaboratif léger)
② SIMILAIRES    : k-NN heuristique sur prix/m², surface, localisation (sans GPU)
③ INVESTISSEMENT: scoring des gouvernorats par potentiel de valorisation

Chaque fonction retourne une liste de dicts prêts pour l'API.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_df(csv_path: str) -> Optional[pd.DataFrame]:
    p = Path(csv_path)
    if not p.exists():
        return None
    df = pd.read_csv(csv_path)
    # price_per_m2 si absente
    if "price_per_m2" not in df.columns and "price" in df.columns and "surface" in df.columns:
        df["price_per_m2"] = df["price"] / df["surface"].replace(0, np.nan)
    return df


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ══════════════════════════════════════════════════════════════════════════════
# ① MATCHING — acheteur → meilleures annonces
# ══════════════════════════════════════════════════════════════════════════════

def match_listings(
    csv_path: str,
    budget_max: float,
    surface_min: float,
    city: str = "",
    property_type: str = "",
    rooms_min: int = 0,
    top_k: int = 5,
) -> list[dict]:
    """
    Score chaque annonce selon sa compatibilité avec le profil acheteur.
    Score final [0-1] = moyenne pondérée de 5 critères.
    """
    df = _load_df(csv_path)
    if df is None or df.empty:
        return []

    df = df.copy()

    # ── Filtres durs ──────────────────────────────────────────────────────────
    if "price" in df.columns:
        df = df[df["price"].notna() & (df["price"] <= budget_max)]
    if "surface" in df.columns:
        df = df[df["surface"].notna() & (df["surface"] >= surface_min)]
    if city and "city" in df.columns:
        df = df[df["city"].astype(str).str.lower() == city.lower()]
    if property_type and "property_type" in df.columns:
        df = df[df["property_type"].astype(str).str.lower() == property_type.lower()]
    if rooms_min > 0 and "rooms" in df.columns:
        df = df[df["rooms"].notna() & (df["rooms"] >= rooms_min)]

    if df.empty:
        return []

    scores = []
    ppm2_median = df["price_per_m2"].median() if "price_per_m2" in df.columns else None

    for _, row in df.iterrows():
        price   = _safe_float(row.get("price"))
        surface = _safe_float(row.get("surface"))
        trust   = _safe_float(row.get("trust_score", 0.65))
        legal   = _safe_float(row.get("legal_risk_score", 0.2))

        # 1. Budget fit : plus c'est proche du max sans dépasser, mieux c'est
        budget_ratio = price / budget_max if budget_max > 0 else 0.5
        budget_score = 1.0 - abs(budget_ratio - 0.85)   # idéal = 85% du budget
        budget_score = max(0.0, min(1.0, budget_score))

        # 2. Surface fit : bonus si dépasse le minimum
        surface_score = min(1.0, surface / max(surface_min, 1) * 0.8) if surface_min > 0 else 0.7

        # 3. Prix/m² vs médiane du marché
        ppm2 = _safe_float(row.get("price_per_m2"))
        if ppm2_median and ppm2_median > 0 and ppm2 > 0:
            ratio = ppm2 / ppm2_median
            ppm2_score = max(0.0, 1.0 - abs(ratio - 1.0) * 0.7)
        else:
            ppm2_score = 0.6

        # 4. Trust score (fiabilité annonce)
        trust_score_val = trust

        # 5. Risque légal inversé
        legal_score = 1.0 - legal

        # Score composite pondéré
        composite = (
            budget_score  * 0.30 +
            surface_score * 0.20 +
            ppm2_score    * 0.20 +
            trust_score_val * 0.20 +
            legal_score   * 0.10
        )

        scores.append({
            "title":           str(row.get("title", "Annonce sans titre"))[:70],
            "city":            str(row.get("city", "—")),
            "property_type":   str(row.get("property_type", "autre")),
            "price":           int(price),
            "surface":         round(surface, 1),
            "price_per_m2":    round(ppm2, 0) if ppm2 else None,
            "rooms":           int(_safe_float(row.get("rooms", 0))) or None,
            "trust_score":     round(trust, 3),
            "legal_risk_score":round(legal, 3),
            "match_score":     round(composite, 3),
            "url":             str(row.get("url", "")),
            "match_reasons":   _match_reasons(budget_score, surface_score, ppm2_score, trust_score_val),
        })

    scores.sort(key=lambda x: x["match_score"], reverse=True)
    return scores[:top_k]


def _match_reasons(budget: float, surface: float, ppm2: float, trust: float) -> list[str]:
    reasons = []
    if budget > 0.75:  reasons.append("Dans votre budget idéal")
    if surface > 0.80: reasons.append("Surface suffisante")
    if ppm2 > 0.75:    reasons.append("Prix/m² compétitif")
    if trust > 0.75:   reasons.append("Annonce fiable")
    if not reasons:    reasons.append("Correspond à vos critères")
    return reasons[:3]


# ══════════════════════════════════════════════════════════════════════════════
# ② SIMILAIRES — k-NN heuristique (sans embeddings GPU)
# ══════════════════════════════════════════════════════════════════════════════

def find_similar_listings(
    csv_path: str,
    ref_price: float,
    ref_surface: float,
    ref_city: str,
    ref_type: str = "",
    top_k: int = 5,
) -> list[dict]:
    """
    Trouve les annonces les plus similaires via distance euclidienne normalisée
    sur (price_per_m2, surface, même_ville, même_type).
    Pas besoin de GPU ni d'embeddings.
    """
    df = _load_df(csv_path)
    if df is None or df.empty:
        return []

    df = df.copy()
    df = df[df["price"].notna() & df["surface"].notna() & (df["surface"] > 0)]
    if df.empty:
        return []

    ref_ppm2 = ref_price / max(ref_surface, 1)

    # Normalisation sur l'ensemble du dataset
    ppm2_std    = df["price_per_m2"].std() or 1.0
    surface_std = df["surface"].std() or 1.0

    distances = []
    for _, row in df.iterrows():
        ppm2    = _safe_float(row.get("price_per_m2"))
        surface = _safe_float(row.get("surface"))
        city    = str(row.get("city", "")).lower()
        rtype   = str(row.get("property_type", "")).lower()

        if ppm2 == 0 or surface == 0:
            continue

        # Distance euclidienne normalisée sur 2 axes numériques
        d_ppm2    = ((ppm2 - ref_ppm2) / ppm2_std) ** 2
        d_surface = ((surface - ref_surface) / surface_std) ** 2
        dist      = math.sqrt(d_ppm2 + d_surface)

        # Bonus si même ville / même type
        city_bonus = 0.0 if city == ref_city.lower() else 0.4
        type_bonus = 0.0 if (ref_type and rtype == ref_type.lower()) else 0.2

        final_dist = dist + city_bonus + type_bonus

        # Score similarité [0-1]
        similarity = max(0.0, 1.0 - min(final_dist / 5.0, 1.0))

        trust = _safe_float(row.get("trust_score", 0.65))
        legal = _safe_float(row.get("legal_risk_score", 0.2))
        price = _safe_float(row.get("price"))

        distances.append({
            "title":           str(row.get("title", "Annonce sans titre"))[:70],
            "city":            str(row.get("city", "—")),
            "property_type":   str(row.get("property_type", "autre")),
            "price":           int(price),
            "surface":         round(surface, 1),
            "price_per_m2":    round(ppm2, 0),
            "trust_score":     round(trust, 3),
            "legal_risk_score":round(legal, 3),
            "similarity_score":round(similarity, 3),
            "price_diff_pct":  round((price - ref_price) / max(ref_price, 1) * 100, 1),
            "url":             str(row.get("url", "")),
        })

    distances.sort(key=lambda x: x["similarity_score"], reverse=True)
    return distances[:top_k]


# ══════════════════════════════════════════════════════════════════════════════
# ③ INVESTISSEMENT — zones à fort potentiel de valorisation
# ══════════════════════════════════════════════════════════════════════════════

# Données macro fixées (évoluent lentement) — enrichissables via API externe
MACRO_DATA = {
  "Tunis":       {"growth_rate":0.062, "demand_pressure":0.85, "infra_score":0.90, "risk":0.20},
  "Ariana":      {"growth_rate":0.058, "demand_pressure":0.80, "infra_score":0.82, "risk":0.22},
  "Ben Arous":   {"growth_rate":0.051, "demand_pressure":0.72, "infra_score":0.75, "risk":0.25},
  "Manouba":     {"growth_rate":0.044, "demand_pressure":0.62, "infra_score":0.68, "risk":0.28},
  "Nabeul":      {"growth_rate":0.071, "demand_pressure":0.88, "infra_score":0.78, "risk":0.18},
  "Hammamet":    {"growth_rate":0.075, "demand_pressure":0.90, "infra_score":0.80, "risk":0.20},
  "Sousse":      {"growth_rate":0.068, "demand_pressure":0.83, "infra_score":0.82, "risk":0.19},
  "Monastir":    {"growth_rate":0.064, "demand_pressure":0.79, "infra_score":0.79, "risk":0.21},
  "Mahdia":      {"growth_rate":0.059, "demand_pressure":0.70, "infra_score":0.65, "risk":0.24},
  "Sfax":        {"growth_rate":0.055, "demand_pressure":0.74, "infra_score":0.80, "risk":0.22},
  "Bizerte":     {"growth_rate":0.048, "demand_pressure":0.65, "infra_score":0.72, "risk":0.26},
  "Zaghouan":    {"growth_rate":0.042, "demand_pressure":0.50, "infra_score":0.58, "risk":0.32},
  "Béja":        {"growth_rate":0.035, "demand_pressure":0.42, "infra_score":0.52, "risk":0.36},
  "Jendouba":    {"growth_rate":0.030, "demand_pressure":0.38, "infra_score":0.48, "risk":0.40},
  "Le Kef":      {"growth_rate":0.028, "demand_pressure":0.36, "infra_score":0.46, "risk":0.42},
  "Siliana":     {"growth_rate":0.025, "demand_pressure":0.32, "infra_score":0.44, "risk":0.44},
  "Kairouan":    {"growth_rate":0.038, "demand_pressure":0.45, "infra_score":0.55, "risk":0.35},
  "Kasserine":   {"growth_rate":0.022, "demand_pressure":0.28, "infra_score":0.40, "risk":0.48},
  "Sidi Bouzid": {"growth_rate":0.020, "demand_pressure":0.26, "infra_score":0.38, "risk":0.50},
  "Gabès":       {"growth_rate":0.040, "demand_pressure":0.52, "infra_score":0.60, "risk":0.30},
  "Médenine":    {"growth_rate":0.055, "demand_pressure":0.68, "infra_score":0.62, "risk":0.25},
  "Tataouine":   {"growth_rate":0.018, "demand_pressure":0.22, "infra_score":0.35, "risk":0.55},
  "Gafsa":       {"growth_rate":0.030, "demand_pressure":0.38, "infra_score":0.48, "risk":0.38},
  "Tozeur":      {"growth_rate":0.048, "demand_pressure":0.60, "infra_score":0.55, "risk":0.28},
  "Kébili":      {"growth_rate":0.022, "demand_pressure":0.28, "infra_score":0.38, "risk":0.50},
}

INVESTMENT_RATIONALE = {
  "Nabeul":   "Demande touristique + résidentielle en forte hausse. Proximité avec Hammamet.",
  "Hammamet": "Zone côtière premium. Valorisation soutenue par le tourisme international.",
  "Sousse":   "2ème pôle économique. Infrastructure solide, marché locatif actif.",
  "Monastir": "Aéroport international + expansion résidentielle. Bon rendement locatif.",
  "Tozeur":   "Tourisme saharien en croissance. Niche haut de gamme peu concurrencée.",
  "Tunis":    "Capitale, demande structurelle stable. Idéal pour le buy-to-let.",
  "Mahdia":   "Sous-évalué vs Sousse. Fort potentiel de rattrapage en 3-5 ans.",
  "Sfax":     "2ème ville du pays, dynamisme économique, prix encore accessibles.",
  "Médenine": "Porte du Sud + Djerba. Croissance portée par l'immobilier touristique.",
}


def rank_investment_zones(
    csv_path: str,
    budget_max: float = 0,
    risk_tolerance: str = "medium",   # "low" | "medium" | "high"
    top_k: int = 5,
) -> list[dict]:
    """
    Classe les gouvernorats par potentiel d'investissement.
    Score composite = croissance * demande * infra - risque, pondéré par tolerance.
    """
    df = _load_df(csv_path)

    risk_weights = {"low": 0.5, "medium": 1.0, "high": 1.5}
    risk_w = risk_weights.get(risk_tolerance, 1.0)

    results = []
    for city, macro in MACRO_DATA.items():
        g = macro["growth_rate"]
        d = macro["demand_pressure"]
        i = macro["infra_score"]
        r = macro["risk"]

        # Score brut
        roi_score    = g * 10            # annualisé en %
        demand_score = d
        infra_score  = i
        risk_penalty = r * risk_w

        composite = (
            roi_score    * 0.35 +
            demand_score * 0.30 +
            infra_score  * 0.20 -
            risk_penalty * 0.15
        )
        composite = max(0.0, min(1.0, composite))

        # Données marché depuis le CSV
        avg_ppm2   = None
        n_listings = 0
        if df is not None and "city" in df.columns:
            sub = df[df["city"].astype(str).str.lower() == city.lower()]
            if not sub.empty and "price_per_m2" in sub.columns:
                avg_ppm2   = round(float(sub["price_per_m2"].median()), 0)
                n_listings = len(sub)

        # Filtre budget (optionnel)
        if budget_max > 0 and avg_ppm2 and avg_ppm2 * 80 > budget_max:
            continue   # même un petit studio dépasse le budget

        level = (
            "Excellent" if composite >= 0.65 else
            "Bon"       if composite >= 0.50 else
            "Moyen"     if composite >= 0.35 else
            "Faible"
        )

        results.append({
            "city":             city,
            "investment_score": round(composite, 3),
            "level":            level,
            "growth_rate_pct":  round(g * 100, 1),
            "demand_pressure":  round(d, 2),
            "infra_score":      round(i, 2),
            "risk_score":       round(r, 2),
            "avg_ppm2":         avg_ppm2,
            "n_listings":       n_listings,
            "rationale":        INVESTMENT_RATIONALE.get(city, f"Potentiel de valorisation de {round(g*100,1)}%/an."),
            "recommended_type": _recommend_type(g, d, avg_ppm2 or 0),
            "horizon_years":    _investment_horizon(composite),
        })

    results.sort(key=lambda x: x["investment_score"], reverse=True)
    return results[:top_k]


def _recommend_type(growth: float, demand: float, ppm2: float) -> str:
    if demand > 0.80 and ppm2 > 2500:
        return "appartement (rendement locatif)"
    if growth > 0.06 and ppm2 < 2000:
        return "terrain (plus-value à terme)"
    if demand > 0.70:
        return "villa (clientèle touristique)"
    return "maison (résidentiel stable)"


def _investment_horizon(score: float) -> str:
    if score >= 0.65: return "Court terme (1–3 ans)"
    if score >= 0.50: return "Moyen terme (3–5 ans)"
    return "Long terme (5+ ans)"


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE UNIFIÉ — appelé par l'API
# ══════════════════════════════════════════════════════════════════════════════

def get_daily_recommendations(
    csv_path: str,
    budget: float         = 350_000,
    surface_min: float    = 80,
    city: str             = "",
    property_type: str    = "",
    risk_tolerance: str   = "medium",
) -> dict:
    """
    Retourne les 3 types de recommandations en un seul appel.
    Utilisé par GET /api/recommendations.
    """
    logger.info(f"[Recommandations] budget={budget} surface_min={surface_min} risk={risk_tolerance}")

    matching     = match_listings(csv_path, budget, surface_min, city, property_type, top_k=5)
    investment   = rank_investment_zones(csv_path, budget, risk_tolerance, top_k=5)

    # Similaires : basé sur l'annonce #1 du matching si dispo, sinon médiane du marché
    if matching:
        ref = matching[0]
        similaires = find_similar_listings(
            csv_path,
            ref_price   = ref["price"],
            ref_surface = ref["surface"],
            ref_city    = ref["city"],
            ref_type    = ref["property_type"],
            top_k       = 5,
        )
        # Exclure la ref elle-même
        similaires = [s for s in similaires if s["title"] != ref["title"]][:4]
    else:
        similaires = find_similar_listings(csv_path, budget * 0.8, surface_min, city, top_k=5)

    return {
        "matching":    matching,
        "similaires":  similaires,
        "investissement": investment,
        "params": {
            "budget":        budget,
            "surface_min":   surface_min,
            "city":          city or "Toutes",
            "property_type": property_type or "Tous",
            "risk_tolerance":risk_tolerance,
        },
    }
