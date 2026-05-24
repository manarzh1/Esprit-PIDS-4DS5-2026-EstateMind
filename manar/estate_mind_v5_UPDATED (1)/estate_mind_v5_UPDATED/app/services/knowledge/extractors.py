"""
app/services/knowledge/extractors.py
======================================
Transforme les réponses brutes BO3 / BO4 en knowledge filtrée.

RÈGLE ABSOLUE :
  - Ne jamais retourner le dataset brut
  - Ne jamais retourner les poids ML / SHAP bruts
  - Toujours tronquer / anonymiser / agréger
  - Max 5 recommandations retournées à BO6
"""
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# UTILITAIRES COMMUNS
# ══════════════════════════════════════════════════════════════

def _bucketize(budget: int) -> str:
    """Anonymise le budget exact en tranche générique."""
    try:
        b = int(budget)
    except (TypeError, ValueError):
        return "unknown"
    if b < 80_000:   return "low"
    if b < 200_000:  return "medium"
    return "high"


def _now() -> str:
    return datetime.utcnow().isoformat()


# ══════════════════════════════════════════════════════════════
# EXTRACTEURS BO3 — Prix / Marché / Recommandations
# ══════════════════════════════════════════════════════════════

def extract_bo3_estimate(raw: dict, params: dict) -> dict:
    """
    Transforme GET /api/estimate de BO3.
    Garde : prix estimé, tendance, confiance, top 3 zones.
    Supprime : annonces complètes, logs internes, credentials.
    """
    return {
        "city":             raw.get("city", params.get("city", "")),
        "property_type":    raw.get("property_type", params.get("property_type", "")),
        "estimated_price":  raw.get("estimated_price"),
        "median_price":     raw.get("median_price"),
        "min_price":        raw.get("min_price"),
        "max_price":        raw.get("max_price"),
        "price_per_sqm":    raw.get("price_per_sqm"),
        "market_trend":     raw.get("market_trend"),        # 'up' / 'down' / 'stable'
        "confidence_level": raw.get("confidence_level"),
        "transaction_type": raw.get("transaction_type", params.get("transaction_type", "")),
        "total_listings_used": raw.get("total_listings_used", raw.get("total_listings", 0)),
        # Max 3 zones — jamais la liste complète
        "top_zones": (raw.get("recommended_areas") or raw.get("top_zones", []))[:3],
        "source":       "BO3",
        "extracted_at": _now(),
        "ttl_minutes":  60,
    }


def extract_bo3_trends(raw: dict, params: dict) -> dict:
    """Transforme GET /api/market-trends de BO3."""
    return {
        "city":          params.get("city", raw.get("city", "")),
        "trend":         raw.get("trend", raw.get("market_trend")),
        "avg_price":     raw.get("avg_price", raw.get("average_price")),
        "demand_level":  raw.get("demand_level"),
        "seasonal_note": raw.get("seasonal_impact", raw.get("seasonal_note")),
        "source":        "BO3",
        "extracted_at":  _now(),
        "ttl_minutes":   1440,   # 24h — les tendances changent lentement
    }


def extract_bo3_recommendations(raw: dict, params: dict) -> dict:
    """Transforme GET /api/recommendations de BO3."""
    alts = raw.get("alternatives", [])
    return {
        "budget_range": _bucketize(params.get("budget", 0)),
        "best_choice":  raw.get("best_choice"),
        # Max 3 alternatives avec champs utiles uniquement
        "alternatives": [
            {
                "area":      a.get("area"),
                "avg_price": a.get("average_price", a.get("avg_price")),
                "advantage": a.get("advantage"),
            }
            for a in alts[:3]
        ],
        "source":       "BO3",
        "extracted_at": _now(),
        "ttl_minutes":  60,
    }


def extract_bo3_opportunities(raw: dict, params: dict) -> dict:
    """Transforme GET /api/opportunities de BO3."""
    items = raw.get("opportunities", raw.get("results", []))
    return {
        "city":  params.get("city", raw.get("city", "")),
        "count": len(items),
        # Max 5 opportunités filtrées
        "top_opportunities": [
            {
                "zone":      o.get("zone", o.get("area")),
                "score":     o.get("score"),
                "avg_price": o.get("avg_price"),
                "trend":     o.get("trend"),
            }
            for o in items[:5]
        ],
        "source":       "BO3",
        "extracted_at": _now(),
        "ttl_minutes":  120,
    }


# ══════════════════════════════════════════════════════════════
# EXTRACTEURS BO4 — Investissement / ROI / Score
# ══════════════════════════════════════════════════════════════

def extract_bo4_analysis(raw: dict, params: dict) -> dict:
    """
    Transforme POST /bo4/analyze de BO4.
    Garde : top 5 recommandations filtrées, tendances marché, confiance.
    Supprime : dataset brut 8500 biens, poids ML, valeurs SHAP brutes.
    """
    recs   = raw.get("recommendations", [])
    market = raw.get("market_summary", {})
    meta   = raw.get("model_metadata", {})

    return {
        # Top 5 uniquement — jamais les 20 bruts
        "top_picks": [
            {
                "city":     r.get("city"),
                "score":    r.get("score"),
                "roi":      r.get("roi"),
                "decision": r.get("decision"),
                # Résumé SHAP tronqué à 200 chars — jamais les valeurs brutes
                "why":      str(r.get("explanation", ""))[:200],
            }
            for r in sorted(recs, key=lambda x: x.get("score", 0), reverse=True)[:5]
        ],
        # Tendances agrégées — pas les données brutes
        "market_insight": {
            "avg_roi":  market.get("avg_roi"),
            "trend":    market.get("trend"),
            "cities":   params.get("cities", []),
            "goal":     params.get("goal"),
        },
        # Métadonnées de confiance — pas les poids du modèle
        "confidence":       meta.get("confidence"),
        "model_type":       meta.get("model_type"),
        # Paramètres anonymisés pour le cache
        "budget_range":     _bucketize(params.get("budget", 0)),
        "goal":             params.get("goal"),
        "risk":             params.get("risk"),
        "investment_score": raw.get("investment_score", raw.get("score", 0)),
        "rental_yield":     raw.get("rental_yield", raw.get("average_yield", 0)),
        "recommendation":   raw.get("recommendation", ""),
        "total_listings":   raw.get("total_listings", 0),
        "city":             params.get("cities", [""])[0] if params.get("cities") else "",
        "source":           "BO4",
        "extracted_at":     _now(),
        "ttl_minutes":      60,
    }


def extract_bo4_score(raw: dict, params: dict) -> dict:
    """
    Transforme POST /score de BO4 (endpoint existant dans le projet).
    Compatible avec l'appel actuel call_bo4 → /score.
    """
    return {
        "city":             raw.get("city", params.get("city", "")),
        "investment_score": raw.get("investment_score", raw.get("score", 0)),
        "rental_yield":     raw.get("rental_yield", raw.get("average_yield", 0)),
        "recommendation":   raw.get("recommendation", ""),
        "total_listings":   raw.get("total_listings", 0),
        "confidence":       raw.get("confidence", "medium"),
        "top_picks": [
            {
                "city":     raw.get("city", ""),
                "score":    raw.get("investment_score", 0),
                "roi":      raw.get("rental_yield", 0),
                "decision": raw.get("recommendation", ""),
                "why":      str(raw.get("explanation", ""))[:200],
            }
        ],
        "market_insight": {
            "avg_roi": raw.get("rental_yield", 0),
            "trend":   raw.get("market_trend", "stable"),
        },
        "source":       "BO4",
        "extracted_at": _now(),
        "ttl_minutes":  60,
    }
