"""
Estate Mind — xai_explainer.py
================================
Explainability AI (XAI) pour BO1 et BO2.

BO1 — Explique POURQUOI une annonce est suspecte ou fiable :
  - Quelles features ont le plus influencé le trust score ?
  - Pourquoi le prix est-il anormal ?
  - Comparaison prix/m² vs marché local

BO2 — Explique POURQUOI un prix est prévu / une zone est émergente :
  - Décomposition Prophet (tendance + saisonnalité + résidu)
  - Facteurs qui rendent une zone émergente
  - Comparaison vs médiane nationale

Usage :
    from tools.xai_explainer import explain_trust, explain_price, explain_forecast, explain_emergence
"""

from __future__ import annotations
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

try:
    import shap
    SHAP_OK = True
except ImportError:
    SHAP_OK = False

SAVED_DIR = Path(__file__).parent.parent / "models" / "saved"

# Labels lisibles pour les features M1
FEATURE_LABELS = {
    "price_value":   "Prix total",
    "surface_m2":    "Surface",
    "price_per_m2":  "Prix au m²",
    "bedrooms":      "Chambres",
    "bathrooms":     "Salles de bain",
    "source_enc":    "Réputation source",
    "city_enc":      "Zone géographique",
    "desc_len":      "Longueur description",
    "has_gps":       "Coordonnées GPS",
}

SOURCE_NAMES = {0: "tayara", 1: "mubawab", 2: "tecnocasa", 3: "remax"}
SOURCE_SCORES = {"remax": 1.0, "tecnocasa": 0.85, "mubawab": 0.65, "tayara": 0.45}

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS COMMUNS
# ═══════════════════════════════════════════════════════════════════════════════

def _prepare_x(price_value, surface_m2, city, description,
               source, bedrooms, bathrooms, latitude, encoders) -> pd.DataFrame:
    """Prépare le vecteur de features M1."""
    price_per_m2 = price_value / max(surface_m2, 1)
    desc_len     = len(str(description or ""))
    has_gps      = 1 if latitude else 0

    le_s = encoders["source"]
    src  = source if source in encoders["source_classes"] else encoders["source_classes"][0]
    source_enc = int(le_s.transform([src])[0])

    le_c  = encoders["city"]
    top   = encoders["top_cities"]
    city2 = city if city in top else "other"
    city2 = city2 if city2 in encoders["city_classes"] else encoders["city_classes"][0]
    city_enc = int(le_c.transform([city2])[0])

    return pd.DataFrame([{
        "price_value":  price_value,
        "surface_m2":   surface_m2,
        "price_per_m2": price_per_m2,
        "bedrooms":     bedrooms if bedrooms is not None else -1,
        "bathrooms":    bathrooms if bathrooms is not None else -1,
        "source_enc":   source_enc,
        "city_enc":     city_enc,
        "desc_len":     float(desc_len),
        "has_gps":      float(has_gps),
    }])


def _market_context(price_per_m2: float, city: str,
                    m5_stats: dict) -> dict:
    """Calcule le contexte marché pour une ville."""
    national_median = m5_stats.get("national_median", 2500.0)
    city_stats_list = m5_stats.get("city_stats", [])
    city_map        = m5_stats.get("city_cluster_map", {})

    city_median = None
    for cs in city_stats_list:
        if cs.get("city", "").lower() == city.lower():
            city_median = cs.get("median_price_m2")
            break

    if city_median is None:
        city_median = national_median

    vs_city     = round((price_per_m2 - city_median) / (city_median + 1e-9) * 100, 1)
    vs_national = round((price_per_m2 - national_median) / (national_median + 1e-9) * 100, 1)
    cluster_id  = city_map.get(city)

    profiles = m5_stats.get("cluster_profiles", [])
    cluster_name = None
    if cluster_id is not None:
        for p in profiles:
            if p["cluster_id"] == cluster_id:
                cluster_name = f"Segment {cluster_id} — {p.get('n_cities',0)} villes"
                break

    return {
        "price_per_m2":    round(price_per_m2, 0),
        "city_median":     round(city_median, 0),
        "national_median": round(national_median, 0),
        "vs_city_pct":     vs_city,
        "vs_national_pct": vs_national,
        "position":        (
            "au-dessus du marché local"  if vs_city > 10  else
            "en-dessous du marché local" if vs_city < -10 else
            "dans la norme locale"
        ),
        "cluster_id":   cluster_id,
        "cluster_name": cluster_name,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BO1 — XAI TRUST SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def explain_trust(
    price_value: float,
    surface_m2:  float,
    city:        str,
    description: str,
    source:      str,
    bedrooms:    Optional[float],
    bathrooms:   Optional[float],
    latitude:    Optional[float],
    models:      dict,
) -> dict:
    """
    Explique le trust score d'une annonce.
    Retourne : score, verdict, contributions SHAP, contexte marché, résumé texte.
    """
    m1_model  = models.get("m1_model")
    encoders  = models.get("m1_encoders")
    m5_stats  = models.get("m5_stats") or {}

    if not m1_model or not encoders:
        return {"error": "Modèle M1 non disponible"}

    X = _prepare_x(price_value, surface_m2, city, description,
                   source, bedrooms, bathrooms, latitude, encoders)
    price_per_m2 = float(X["price_per_m2"].iloc[0])
    proba = float(m1_model.predict_proba(X)[0][1])
    label = "Fiable" if proba >= 0.6 else "Suspect"

    # ── Contributions SHAP ────────────────────────────────────────────────────
    contributions = []
    method = "feature_importance"

    if SHAP_OK:
        try:
            explainer   = shap.TreeExplainer(m1_model)
            shap_values = explainer.shap_values(X)
            sv = shap_values[1][0] if isinstance(shap_values, list) else shap_values[0]
            method = "shap"

            feats = list(X.columns)
            for i, feat in enumerate(feats):
                val      = float(X[feat].iloc[0])
                sv_val   = float(sv[i])
                magnitude = abs(sv_val)
                direction = "hausse_fiabilite" if sv_val > 0 else "baisse_fiabilite"

                # Valeur lisible selon la feature
                readable = _readable_value(feat, val, encoders, source)

                contributions.append({
                    "feature":    feat,
                    "label":      FEATURE_LABELS.get(feat, feat),
                    "value":      round(val, 2),
                    "readable":   readable,
                    "shap_value": round(sv_val, 4),
                    "magnitude":  round(magnitude, 4),
                    "direction":  direction,
                    "impact":     "positive" if sv_val > 0 else "negative",
                })
            contributions.sort(key=lambda x: -x["magnitude"])

        except Exception:
            # Fallback feature importance
            fi = m1_model.feature_importances_
            for i, feat in enumerate(X.columns):
                val = float(X[feat].iloc[0])
                contributions.append({
                    "feature":   feat,
                    "label":     FEATURE_LABELS.get(feat, feat),
                    "value":     round(val, 2),
                    "readable":  _readable_value(feat, val, encoders, source),
                    "magnitude": round(float(fi[i]), 4),
                    "direction": "hausse_fiabilite",
                    "impact":    "neutral",
                })
            contributions.sort(key=lambda x: -x["magnitude"])
    else:
        fi = m1_model.feature_importances_
        for i, feat in enumerate(X.columns):
            val = float(X[feat].iloc[0])
            contributions.append({
                "feature":   feat,
                "label":     FEATURE_LABELS.get(feat, feat),
                "value":     round(val, 2),
                "readable":  _readable_value(feat, val, encoders, source),
                "magnitude": round(float(fi[i]), 4),
                "impact":    "neutral",
            })
        contributions.sort(key=lambda x: -x["magnitude"])

    # ── Contexte marché ───────────────────────────────────────────────────────
    market = _market_context(price_per_m2, city, m5_stats)

    # ── Résumé textuel ────────────────────────────────────────────────────────
    top3    = contributions[:3]
    summary = _build_summary_trust(label, proba, top3, market, source,
                                   len(str(description or "")))

    # ── Flags de risque ───────────────────────────────────────────────────────
    risk_flags = _compute_risk_flags(price_per_m2, market, description,
                                      source, latitude, bedrooms)

    return {
        "trust_score":    round(proba, 4),
        "label":          label,
        "confidence_pct": round(max(proba, 1 - proba) * 100, 1),
        "method":         method,
        "contributions":  contributions[:6],
        "market_context": market,
        "risk_flags":     risk_flags,
        "summary":        summary,
    }


def _readable_value(feat: str, val: float, encoders: dict, source: str) -> str:
    if feat == "price_value":
        return f"{val:,.0f} TND"
    if feat == "surface_m2":
        return f"{val:.0f} m²"
    if feat == "price_per_m2":
        return f"{val:,.0f} TND/m²"
    if feat == "bedrooms":
        return f"{val:.0f} chambre(s)" if val > 0 else "Non renseigné"
    if feat == "bathrooms":
        return f"{val:.0f} salle(s) de bain" if val > 0 else "Non renseigné"
    if feat == "source_enc":
        score = SOURCE_SCORES.get(source, 0.5)
        return f"{source} (score réputation: {score})"
    if feat == "city_enc":
        return "Ville encodée"
    if feat == "desc_len":
        return f"{int(val)} caractères"
    if feat == "has_gps":
        return "Présent" if val == 1 else "Absent"
    return str(val)


def _compute_risk_flags(price_per_m2, market, description, source,
                         latitude, bedrooms) -> list[dict]:
    flags = []
    desc = str(description or "").lower()

    if price_per_m2 < 50:
        flags.append({"code": "prix_trop_bas", "severity": "high",
                       "message": f"Prix/m² de {price_per_m2:.0f} TND — probable location déguisée en vente"})
    elif market["vs_city_pct"] < -30:
        flags.append({"code": "prix_anormalement_bas", "severity": "medium",
                       "message": f"Prix {abs(market['vs_city_pct']):.0f}% sous la médiane de {market['city_median']:.0f} TND/m²"})
    elif market["vs_city_pct"] > 50:
        flags.append({"code": "prix_anormalement_haut", "severity": "low",
                       "message": f"Prix {market['vs_city_pct']:.0f}% au-dessus de la médiane locale"})

    if not latitude:
        flags.append({"code": "pas_gps", "severity": "low",
                       "message": "Aucune coordonnée GPS — localisation non vérifiable"})

    if len(desc) < 30:
        flags.append({"code": "description_vide", "severity": "medium",
                       "message": "Description très courte — informations insuffisantes"})

    suspect_words = ["urgent", "cash uniquement", "sans intermédiaire", "affaire"]
    found = [w for w in suspect_words if w in desc]
    if found:
        flags.append({"code": "langage_suspect", "severity": "medium",
                       "message": f"Mots suspects : {', '.join(found)}"})

    if source == "tayara":
        flags.append({"code": "source_faible", "severity": "low",
                       "message": "Tayara : source avec le plus faible score de réputation (0.45)"})
    return flags


def _build_summary_trust(label, proba, top3, market, source, desc_len) -> str:
    pct = round(proba * 100, 0) if label == "Fiable" else round((1-proba)*100, 0)

    top_feat  = top3[0]["label"] if top3 else "les données"
    top2_feat = top3[1]["label"] if len(top3) > 1 else None

    reason = top_feat
    if top2_feat:
        reason += f" et {top2_feat.lower()}"

    pos = market["position"]
    med = market["city_median"]
    ppm2 = market["price_per_m2"]

    return (
        f"Cette annonce est classée **{label}** avec une certitude de {pct:.0f}%. "
        f"Les facteurs déterminants sont {reason}. "
        f"Le prix au m² est de {ppm2:,.0f} TND — {pos} "
        f"(médiane locale : {med:,.0f} TND/m²)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BO1 — XAI ANOMALIE DE PRIX
# ═══════════════════════════════════════════════════════════════════════════════

def explain_anomaly(
    price_value: float,
    surface_m2:  float,
    city:        str,
    models:      dict,
) -> dict:
    """Explique pourquoi un prix est anormal."""
    m2_model = models.get("m2_model")
    m2_scaler = models.get("m2_scaler")
    m5_stats  = models.get("m5_stats") or {}

    if not m2_model or not m2_scaler:
        return {"error": "Modèle M2 non disponible"}

    price_per_m2 = price_value / max(surface_m2, 1)
    market = _market_context(price_per_m2, city, m5_stats)
    national_median = market["national_median"]
    city_median     = market["city_median"]

    X = pd.DataFrame([{
        "price_value":  price_value,
        "surface_m2":   surface_m2,
        "price_per_m2": price_per_m2,
        "bedrooms":     2.0,
    }])
    Xs = m2_scaler.transform(X)
    decision   = float(m2_model.decision_function(Xs)[0])
    is_anomaly = bool(m2_model.predict(Xs)[0] == -1)
    score      = round(max(0, min(1, -decision / 0.5)), 4)

    # Calcul du prix "attendu" pour cette surface
    expected_price = city_median * surface_m2
    gap_tnd        = price_value - expected_price
    gap_pct        = round(gap_tnd / (expected_price + 1e-9) * 100, 1)

    # Diagnostics
    diagnostics = []
    if price_per_m2 < 100:
        diagnostics.append({"type": "très_bas", "message":
            f"Prix au m² de {price_per_m2:.0f} TND — typiquement un loyer mensuel, pas un prix de vente"})
    elif price_per_m2 < city_median * 0.5:
        diagnostics.append({"type": "bas", "message":
            f"Prix {abs(gap_pct):.0f}% sous la médiane locale ({city_median:.0f} TND/m²)"})
    elif price_per_m2 > city_median * 2:
        diagnostics.append({"type": "haut", "message":
            f"Prix {gap_pct:.0f}% au-dessus de la médiane locale"})
    else:
        diagnostics.append({"type": "normal", "message":
            f"Prix dans la fourchette normale pour {city}"})

    if surface_m2 < 15:
        diagnostics.append({"type": "surface", "message":
            f"Surface de {surface_m2:.0f} m² — très petite, vérifier l'unité"})

    summary = (
        f"Prix **anormal** (score={score:.2f}) — {diagnostics[0]['message']}"
        if is_anomaly else
        f"Prix **normal** pour {city} — {diagnostics[0]['message']}"
    )

    return {
        "is_anomaly":      is_anomaly,
        "anomaly_score":   score,
        "decision_score":  round(decision, 4),
        "price_per_m2":    round(price_per_m2, 0),
        "expected_price":  round(expected_price, 0),
        "gap_tnd":         round(gap_tnd, 0),
        "gap_pct":         gap_pct,
        "market_context":  market,
        "diagnostics":     diagnostics,
        "summary":         summary,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BO2 — XAI FORECAST
# ═══════════════════════════════════════════════════════════════════════════════

def explain_forecast(city: str, models: dict) -> dict:
    """
    Explique la prévision de prix Prophet pour une ville.
    Décompose en tendance, variation, intervalles.
    """
    all_fc = models.get("m4_forecasts") or {}
    forecasts = all_fc.get("forecasts", {})

    city_match = None
    for c in forecasts:
        if c.lower() == city.lower():
            city_match = c
            break

    if city_match is None:
        return {"error": f"Pas de prévision pour '{city}'",
                "available": list(forecasts.keys())}

    data = forecasts[city_match]
    rows = data.get("forecast", [])
    if not rows:
        return {"error": "Données de prévision vides"}

    prices      = [r["predicted"] for r in rows]
    lowers      = [r["lower_80"]  for r in rows]
    uppers      = [r["upper_80"]  for r in rows]

    first_price = prices[0]
    last_price  = prices[-1]
    trend_pct   = round((last_price - first_price) / (first_price + 1e-9) * 100, 2)
    avg_price   = round(sum(prices) / len(prices), 0)
    max_price   = max(prices)
    min_price   = min(prices)

    # Incertitude : largeur moyenne de l'intervalle
    avg_interval_width = round(
        sum(u - l for u, l in zip(uppers, lowers)) / len(rows), 0
    )
    avg_interval_pct = round(avg_interval_width / (avg_price + 1e-9) * 100, 1)

    # Tendance
    if trend_pct > 3:
        trend_label = "hausse"
        trend_color = "green"
    elif trend_pct < -3:
        trend_label = "baisse"
        trend_color = "red"
    else:
        trend_label = "stable"
        trend_color = "gray"

    # Jalons 30 / 60 / 90j
    milestones = {}
    for d in [30, 60, 90]:
        idx = min(d - 1, len(rows) - 1)
        milestones[f"j{d}"] = {
            "date":      rows[idx]["date"],
            "predicted": rows[idx]["predicted"],
            "lower_80":  rows[idx]["lower_80"],
            "upper_80":  rows[idx]["upper_80"],
        }

    # Comparaison avec la médiane nationale
    m5_stats = models.get("m5_stats") or {}
    national_median = m5_stats.get("national_median", 2500)
    vs_national_pct = round(
        (avg_price - national_median) / (national_median + 1e-9) * 100, 1
    )

    # Facteurs explicatifs
    factors = []
    if data.get("synthetic_dates"):
        factors.append({
            "factor": "Données limitées",
            "detail": "Prévision basée sur 7 semaines de données — résultats illustratifs. "
                      "La précision augmentera avec plus d'historique.",
            "impact": "neutral",
        })
    if trend_pct > 5:
        factors.append({
            "factor": "Tendance haussière détectée",
            "detail": f"Le modèle Prophet détecte une hausse de {trend_pct:.1f}% "
                      f"sur l'horizon de {len(rows)} jours.",
            "impact": "positive",
        })
    elif trend_pct < -5:
        factors.append({
            "factor": "Tendance baissière détectée",
            "detail": f"Le modèle Prophet détecte une baisse de {abs(trend_pct):.1f}% "
                      f"sur l'horizon de {len(rows)} jours.",
            "impact": "negative",
        })
    else:
        factors.append({
            "factor": "Marché stable",
            "detail": f"Les prix prévus restent stables autour de {avg_price:,.0f} TND/m².",
            "impact": "neutral",
        })

    factors.append({
        "factor": "Incertitude du modèle",
        "detail": f"L'intervalle de confiance à 80% représente ±{avg_interval_pct:.0f}% "
                  f"du prix prédit — soit ±{avg_interval_width:,.0f} TND/m² en moyenne.",
        "impact": "neutral",
    })

    summary = (
        f"Pour **{city_match}**, le modèle Prophet prédit un prix moyen de "
        f"**{avg_price:,.0f} TND/m²** sur les {len(rows)} prochains jours, "
        f"avec une tendance à la **{trend_label}** de {abs(trend_pct):.1f}%. "
        f"L'incertitude est de ±{avg_interval_pct:.0f}%."
    )

    return {
        "city":              city_match,
        "trend_label":       trend_label,
        "trend_color":       trend_color,
        "trend_pct":         trend_pct,
        "avg_predicted":     avg_price,
        "min_predicted":     round(min_price, 0),
        "max_predicted":     round(max_price, 0),
        "last_known_price":  data.get("last_known_price"),
        "avg_interval_width": avg_interval_width,
        "avg_interval_pct":  avg_interval_pct,
        "mape":              data.get("mape_pct"),
        "vs_national_pct":   vs_national_pct,
        "national_median":   round(national_median, 0),
        "milestones":        milestones,
        "factors":           factors,
        "forecast_preview":  rows[:7],
        "summary":           summary,
        "n_days":            len(rows),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BO2 — XAI ÉMERGENCE
# ═══════════════════════════════════════════════════════════════════════════════

def explain_emergence(
    city:         str,
    median_price: float,
    volume:       int,
    models:       dict,
) -> dict:
    """Explique pourquoi une zone est (ou n'est pas) émergente."""
    m6_model  = models.get("m6_model")
    m6_encoder = models.get("m6_encoder")
    m6_stats  = models.get("m6_stats") or {}
    m5_stats  = models.get("m5_stats") or {}

    if not m6_model or not m6_encoder:
        return {"error": "Modèle M6 non disponible"}

    nat_med  = m6_stats.get("national_median", 2500)
    avg_vol  = m6_stats.get("avg_vol_per_city", 50)
    classes  = m6_stats.get("city_encoder_classes", [])

    city2    = city if city in classes else (classes[0] if classes else "other")
    city_enc = int(m6_encoder.transform([city2])[0])

    price_vs_national = median_price / nat_med
    vol_vs_national   = volume / (avg_vol + 1)

    X = pd.DataFrame([{
        "median_price":      median_price,
        "mean_price":        median_price,
        "volume":            volume,
        "std_price":         0.0,
        "city_median":       median_price,
        "city_volume":       volume,
        "price_vs_national": price_vs_national,
        "vol_vs_national":   vol_vs_national,
        "city_enc":          city_enc,
    }])

    proba   = float(m6_model.predict_proba(X)[0][1])
    is_em   = bool(m6_model.predict(X)[0] == 1)

    # Contributions des features
    FEAT_LABELS_M6 = {
        "price_vs_national": "Prix vs médiane nationale",
        "vol_vs_national":   "Volume vs moyenne nationale",
        "median_price":      "Prix médian local",
        "mean_price":        "Prix moyen local",
        "volume":            "Volume d'annonces",
        "std_price":         "Volatilité des prix",
        "city_median":       "Médiane historique ville",
        "city_volume":       "Volume historique ville",
        "city_enc":          "Identité géographique",
    }

    shap_contribs = []
    if SHAP_OK:
        try:
            explainer = shap.TreeExplainer(m6_model)
            sv        = explainer.shap_values(X)
            sv_arr    = sv[1][0] if isinstance(sv, list) else sv[0]
            for i, feat in enumerate(X.columns):
                shap_contribs.append({
                    "feature":   feat,
                    "label":     FEAT_LABELS_M6.get(feat, feat),
                    "value":     round(float(X[feat].iloc[0]), 3),
                    "shap":      round(float(sv_arr[i]), 4),
                    "magnitude": abs(float(sv_arr[i])),
                    "impact":    "positive" if sv_arr[i] > 0 else "negative",
                })
            shap_contribs.sort(key=lambda x: -x["magnitude"])
        except Exception:
            pass

    # Facteurs lisibles
    factors = []

    if price_vs_national > 1.05:
        factors.append({
            "factor": "Prix au-dessus de la médiane nationale",
            "detail": f"{median_price:,.0f} TND/m² (+{(price_vs_national-1)*100:.1f}% vs {nat_med:,.0f} national)",
            "impact": "positive",
        })
    elif price_vs_national < 0.95:
        factors.append({
            "factor": "Prix en-dessous de la médiane nationale",
            "detail": f"{median_price:,.0f} TND/m² ({(price_vs_national-1)*100:.1f}% vs {nat_med:,.0f} national)",
            "impact": "negative",
        })
    else:
        factors.append({
            "factor": "Prix proche de la médiane nationale",
            "detail": f"{median_price:,.0f} TND/m² ≈ {nat_med:,.0f} TND/m² national",
            "impact": "neutral",
        })

    if vol_vs_national > 1.2:
        factors.append({
            "factor": "Volume d'annonces élevé",
            "detail": f"{volume} annonces — {(vol_vs_national-1)*100:.0f}% au-dessus de la moyenne nationale ({avg_vol:.0f})",
            "impact": "positive",
        })
    elif vol_vs_national < 0.5:
        factors.append({
            "factor": "Volume d'annonces faible",
            "detail": f"{volume} annonces — marché peu liquide",
            "impact": "negative",
        })
    else:
        factors.append({
            "factor": "Volume d'annonces normal",
            "detail": f"{volume} annonces — activité dans la moyenne",
            "impact": "neutral",
        })

    # Cluster
    market = _market_context(median_price, city, m5_stats)
    if market.get("cluster_name"):
        factors.append({
            "factor": "Positionnement marché",
            "detail": market["cluster_name"],
            "impact": "neutral",
        })

    # Verdict
    if proba >= 0.75:
        verdict = "Fort signal d'émergence"
        recommendation = "Surveiller activement — opportunité d'investissement à court terme"
        color = "green"
    elif proba >= 0.50:
        verdict = "Signal modéré"
        recommendation = "Zone à surveiller — confirmer avec les données des prochaines semaines"
        color = "orange"
    else:
        verdict = "Pas d'émergence détectée"
        recommendation = "Zone stable — monitoring standard suffisant"
        color = "gray"

    summary = (
        f"**{city}** présente une probabilité d'émergence de **{proba*100:.1f}%** "
        f"({verdict}). "
        f"Le prix de {median_price:,.0f} TND/m² est "
        f"{market['position']} ({market['vs_city_pct']:+.0f}% vs médiane locale). "
        f"Recommandation : {recommendation}."
    )

    return {
        "city":                city,
        "is_emerging":         is_em,
        "emergence_proba":     round(proba, 4),
        "emergence_proba_pct": round(proba * 100, 1),
        "verdict":             verdict,
        "verdict_color":       color,
        "recommendation":      recommendation,
        "price_vs_national":   round(price_vs_national, 3),
        "vol_vs_national":     round(vol_vs_national, 3),
        "national_median":     round(nat_med, 0),
        "market_context":      market,
        "factors":             factors,
        "shap_contributions":  shap_contribs[:5],
        "summary":             summary,
    }
