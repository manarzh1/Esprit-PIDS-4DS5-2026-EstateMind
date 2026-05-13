"""
app/services/knowledge/extractors.py
======================================
Transforme les reponses brutes BO1/BO2/BO3/BO4 en knowledge filtree.

REGLE ABSOLUE :
  - Ne jamais retourner le dataset brut
  - Ne jamais retourner les poids ML / SHAP bruts
  - Toujours tronquer / anonymiser / agreger
  - Max 5 recommandations retournees a BO6
"""
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# UTILITAIRES COMMUNS
# ══════════════════════════════════════════════════════════════

def _bucketize(budget: int) -> str:
    try:
        b = int(budget)
    except (TypeError, ValueError):
        return "unknown"
    if b < 80_000:  return "low"
    if b < 200_000: return "medium"
    return "high"


def _now() -> str:
    return datetime.utcnow().isoformat()


# ══════════════════════════════════════════════════════════════
# EXTRACTEURS BO1 - Fiabilite du marche
# ══════════════════════════════════════════════════════════════

def extract_bo1_reliability(raw: dict, params: dict) -> dict:
    """
    Transforme la reponse POST /collect de BO1.
    Garde : metriques agregees, taux anomalie, score confiance moyen.
    Supprime : annonces completes (listings), logs internes, donnees GPS brutes.
    """
    return {
        "city":             params.get("city", params.get("ville", "")),
        "total_listings":   raw.get("total_listings", 0),
        "trusted_listings": raw.get("trusted_listings", 0),
        "anomaly_count":    raw.get("anomaly_count", 0),
        "anomaly_rate":     raw.get("anomaly_rate", 0.0),
        "avg_trust_score":  raw.get("avg_trust_score", 0.0),
        # Repartition sources - agregee, pas les annonces individuelles
        "source_breakdown": raw.get("source_breakdown", {}),
        # Sante sources KS - statut uniquement
        "ks_health":        raw.get("ks_health", {}),
        # Top 3 anomalies signalees - titre + raison uniquement, pas le contenu
        "top_anomalies": [
            {
                "title":            l.get("title", "")[:80],
                "source":           l.get("source"),
                "trust_score":      l.get("trust_score"),
                "shap_top_feature": l.get("shap_top_feature"),
            }
            for l in (raw.get("listings") or [])
            if l.get("is_anomaly")
        ][:3],
        "source":       "BO1",
        "extracted_at": _now(),
        "ttl_minutes":  30,
    }


# ══════════════════════════════════════════════════════════════
# EXTRACTEURS BO2 - Dynamiques territoriales
# ══════════════════════════════════════════════════════════════

def extract_bo2_territorial(raw: dict, params: dict) -> dict:
    """
    Transforme la reponse POST /analyse de BO2.
    Garde : cluster, tendance, jalons Prophet, top zones emergentes.
    Supprime : donnees brutes K-Means, valeurs SHAP brutes, series temporelles completes.
    """
    prophet = raw.get("prophet_forecast", {})
    return {
        "city":           raw.get("city", params.get("city", params.get("ville", ""))),
        "cluster_label":  raw.get("cluster_label"),
        "avg_price_m2":   raw.get("avg_price_m2"),
        "trend_direction": raw.get("trend_direction", "stable"),
        "trend_pct_90d":  raw.get("trend_pct_90d", 0.0),
        "market_action":  raw.get("market_action", "monitoring standard"),
        # Jalons Prophet J+30/J+60/J+90 - valeur centrale uniquement
        "forecast_j30":   (prophet.get("j30") or {}).get("value"),
        "forecast_j60":   (prophet.get("j60") or {}).get("value"),
        "forecast_j90":   (prophet.get("j90") or {}).get("value"),
        # Max 3 zones emergentes - score + action uniquement
        "top_emerging": [
            {
                "zone":            z.get("zone"),
                "emergence_score": z.get("emergence_score"),
                "action":          z.get("action"),
            }
            for z in (raw.get("emerging_zones") or [])[:3]
        ],
        "source":       "BO2",
        "extracted_at": _now(),
        "ttl_minutes":  120,
    }


# ══════════════════════════════════════════════════════════════
# EXTRACTEURS BO3 - Prix / Marche / Recommandations
# ══════════════════════════════════════════════════════════════

def extract_bo3_estimate(raw: dict, params: dict) -> dict:
    """
    Transforme GET /api/estimate de BO3.
    Garde : prix estime, tendance, confiance, top 3 zones.
    Supprime : annonces completes, logs internes, credentials.
    """
    return {
        "city":               raw.get("city", params.get("city", "")),
        "property_type":      raw.get("property_type", params.get("property_type", "")),
        "estimated_price":    raw.get("estimated_price"),
        "city_median":        raw.get("city_median"),
        "city_min":           raw.get("city_min"),
        "city_max":           raw.get("city_max"),
        "price_per_m2":       raw.get("price_per_m2") or raw.get("city_ppm2"),
        "confidence_score":   raw.get("confidence_score"),
        "market_delta_pct":   raw.get("market_delta_pct"),
        "transaction_type":   raw.get("transaction_type", params.get("transaction_type", "")),
        "total_listings_used": (raw.get("distribution") or {}).get("count", 0),
        "top_zones": (raw.get("recommended_zones") or raw.get("top_zones", []))[:3],
        "source":       "BO3",
        "extracted_at": _now(),
        "ttl_minutes":  60,
    }


def extract_bo3_trends(raw: dict, params: dict) -> dict:
    """Transforme GET /api/market-trends de BO3 (SARIMA investment_analysis)."""
    return {
        "city":              params.get("city", raw.get("gouvernorat", "")),
        "current_price_m2":  raw.get("current_price_m2"),
        "forecast_price_m2": raw.get("forecast_price_m2"),
        "expected_growth_pct": raw.get("expected_growth_pct"),
        "aic":               (raw.get("model_quality") or {}).get("aic"),
        "source":            "BO3",
        "extracted_at":      _now(),
        "ttl_minutes":       1440,
    }


def extract_bo3_recommendations(raw: dict, params: dict) -> dict:
    """Transforme GET /api/recommendations de BO3."""
    zones = raw.get("recommended_zones", [])
    return {
        "budget_range": _bucketize(params.get("budget", 0)),
        "ville":        raw.get("ville"),
        "type_bien":    raw.get("type_bien"),
        "data_source":  raw.get("data_source"),
        "top_zones": [
            {
                "zone":       z.get("zone"),
                "price":      z.get("price"),
                "ppm2":       z.get("ppm2"),
                "score":      z.get("score"),
                "trend_pct":  z.get("trend_pct"),
            }
            for z in zones[:3]
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
        "top_opportunities": [
            {"zone": o.get("zone", o.get("area")), "score": o.get("score"),
             "avg_price": o.get("avg_price"), "trend": o.get("trend")}
            for o in items[:5]
        ],
        "source":       "BO3",
        "extracted_at": _now(),
        "ttl_minutes":  120,
    }


# ══════════════════════════════════════════════════════════════
# EXTRACTEURS BO4 - Investissement / ROI / Score
# ══════════════════════════════════════════════════════════════

def extract_bo4_analysis(raw: dict, params: dict) -> dict:
    """
    Transforme POST /bo4/analyze de BO4.
    Garde : top 5 recommandations filtrees, tendances marche, confiance.
    Supprime : dataset brut 8500 biens, poids ML, valeurs SHAP brutes.
    """
    recs   = raw.get("recommendations", [])
    market = raw.get("market_summary", {})
    meta   = raw.get("model_metadata", {})
    return {
        "top_picks": [
            {
                "city":     r.get("city"),
                "score":    r.get("score"),
                "roi":      r.get("roi"),
                "decision": r.get("decision"),
                "why":      str(r.get("explanation", ""))[:200],
            }
            for r in sorted(recs, key=lambda x: x.get("score", 0), reverse=True)[:5]
        ],
        "market_insight": {
            "avg_roi": market.get("avg_roi"),
            "trend":   market.get("trend"),
            "cities":  params.get("cities", []),
            "goal":    params.get("goal"),
        },
        "confidence":       meta.get("confidence"),
        "model_type":       meta.get("model_type"),
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
    """Transforme POST /score de BO4 (endpoint legacy)."""
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
