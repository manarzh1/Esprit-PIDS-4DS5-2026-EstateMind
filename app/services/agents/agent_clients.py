"""
app/services/agents/agent_clients.py
=====================================
Clients HTTP pour les agents BO1-BO5.
BO1, BO2, BO3, BO4 sont entierement documentes et cables.

Reponses BO1 (POST /collect) :
  { total_listings, trusted_listings, anomaly_count, anomaly_rate,
    avg_trust_score, listings[{id,title,price,surface,city,source,
    trust_score,is_anomaly,property_type,sentiment_flags,shap_top_feature}],
    source_breakdown{tayara,mubawab,tecnocasa,remax}, ks_health }

Reponses BO2 (POST /analyse) :
  { city, cluster_id, cluster_label, cluster_cities, avg_price_m2,
    prophet_forecast{j30,j60,j90:{date,value,lower,upper}},
    trend_direction, trend_pct_90d,
    emerging_zones[{zone,emergence_score,action,shap_top_features}],
    market_action, total_listings }

Reponses BO3 (POST /api/estimate) :
  { success, estimation:{predicted,ci_lower,ci_upper,confidence,
    price_per_m2,city_median,city_ppm2,city_min,city_max,
    market_delta_pct,budget_delta,surface_possible,r2,rmse},
    distribution:{prices,price_per_m2,count} }

Reponses BO4 (POST /bo4/analyze) :
  { recommendations:[{city,score,roi,decision,explanation,
    projected_price,risk_level}],
    market_summary:{avg_roi,trend,total_assets_analyzed},
    model_metadata:{confidence,model_type,rl_signal},
    investment_score, ppo_action }
"""

import time
import asyncio
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.services.knowledge.kb_retriever import get_from_kb, store_in_kb
from app.services.knowledge.extractors import (
    extract_bo1_reliability,
    extract_bo2_territorial,
    extract_bo3_estimate,
    extract_bo3_recommendations,
    extract_bo3_trends,
    extract_bo4_analysis,
    extract_bo4_score,
)

settings = get_settings()


# ---------------------------------------------------------------------------
#  Utilitaires partages
# ---------------------------------------------------------------------------

def _fallback(agent: str, error: str) -> dict:
    return {
        "available": False,
        "agent": agent,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _headers(session_id: str | None = None) -> dict:
    h = {"Content-Type": "application/json", "X-Source-Agent": "BO6"}
    if session_id:
        h["X-Session-ID"] = session_id
    token = getattr(settings, "agent_auth_token", None)
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def _post(url, payload, timeout=None, session_id=None):
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(
        connect=5.0, read=float(timeout or settings.agent_timeout), write=5.0, pool=5.0
    )) as client:
        resp = await client.post(url, json=payload, headers=_headers(session_id))
        resp.raise_for_status()
        return resp.json(), int((time.monotonic() - t0) * 1000)


async def _get(url, timeout=None, session_id=None):
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(
        connect=5.0, read=float(timeout or settings.agent_timeout), write=5.0, pool=5.0
    )) as client:
        resp = await client.get(url, headers=_headers(session_id))
        resp.raise_for_status()
        return resp.json(), int((time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
#  BO1 - Fiabilite du marche  (M1 XGBoost, M2 IsolationForest, M3 NLP)
#  Port 8001 - Endpoint : POST /collect
# ---------------------------------------------------------------------------

async def call_bo1(intent, params, session_id=None):
    base = settings.agent_bo1_url.rstrip("/")
    cached = await get_from_kb("BO1", intent, params)
    if cached:
        cached["from_cache"] = True
        return cached
    try:
        payload = {
            "query":      params.get("query", ""),
            "session_id": session_id or "",
            "city":       params.get("city", params.get("ville", "")),
        }
        raw, ms = await _post(f"{base}/collect", payload, session_id=session_id)

        result = {
            "available": True, "agent": "BO1", "intent": intent, "response_ms": ms,
            "total_listings":   raw.get("total_listings", 0),
            "trusted_listings": raw.get("trusted_listings", 0),
            "anomaly_count":    raw.get("anomaly_count", 0),
            "anomaly_rate":     raw.get("anomaly_rate", 0.0),
            "avg_trust_score":  raw.get("avg_trust_score", 0.0),
            "listings": [
                {
                    "id": l.get("id"), "title": l.get("title"),
                    "price": l.get("price"), "surface": l.get("surface"),
                    "city": l.get("city"), "source": l.get("source"),
                    "trust_score": l.get("trust_score"),
                    "is_anomaly": l.get("is_anomaly", False),
                    "property_type": l.get("property_type"),
                    "sentiment_flags": l.get("sentiment_flags", []),
                    "shap_top_feature": l.get("shap_top_feature"),
                }
                for l in (raw.get("listings") or [])[:5]
            ],
            "source_breakdown": raw.get("source_breakdown", {"tayara": 0, "mubawab": 0, "tecnocasa": 0, "remax": 0}),
            "ks_health": raw.get("ks_health", {}),
            "from_cache": False,
        }
        knowledge = extract_bo1_reliability(result, params)
        await store_in_kb("BO1", intent, params, knowledge, ttl_minutes=30)
        return result
    except asyncio.TimeoutError:
        return _fallback("BO1", f"Timeout apres {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO1", f"BO1 injoignable sur {settings.agent_bo1_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO1", f"BO1 HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return _fallback("BO1", f"Erreur inattendue BO1: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
#  BO2 - Dynamiques territoriales  (M4 Prophet, M5 K-Means, M6 XGBoost)
#  Port 8002 - Endpoint : POST /analyse
# ---------------------------------------------------------------------------

async def call_bo2(intent, params, session_id=None):
    base = settings.agent_bo2_url.rstrip("/")
    cached = await get_from_kb("BO2", intent, params)
    if cached:
        cached["from_cache"] = True
        return cached
    try:
        payload = {
            "query":            params.get("query", ""),
            "city":             params.get("city", params.get("ville", "Tunis")),
            "transaction_type": params.get("transaction_type", "vente"),
        }
        raw, ms = await _post(f"{base}/analyse", payload, session_id=session_id)

        prophet = raw.get("prophet_forecast", {})
        emerging = [
            {
                "zone": z.get("zone"), "emergence_score": z.get("emergence_score"),
                "action": z.get("action"), "shap_top_features": z.get("shap_top_features", []),
            }
            for z in (raw.get("emerging_zones") or [])[:3]
        ]

        result = {
            "available": True, "agent": "BO2", "intent": intent, "response_ms": ms,
            "city":           raw.get("city", payload["city"]),
            "cluster_id":     raw.get("cluster_id"),
            "cluster_label":  raw.get("cluster_label"),
            "cluster_cities": raw.get("cluster_cities", []),
            "avg_price_m2":   raw.get("avg_price_m2"),
            "prophet_forecast": {
                "j30": prophet.get("j30", {}),
                "j60": prophet.get("j60", {}),
                "j90": prophet.get("j90", {}),
            },
            "trend_direction": raw.get("trend_direction", "stable"),
            "trend_pct_90d":   raw.get("trend_pct_90d", 0.0),
            "emerging_zones":  emerging,
            "market_action":   raw.get("market_action", "monitoring standard"),
            "total_listings":  raw.get("total_listings", 0),
            "from_cache": False,
        }
        knowledge = extract_bo2_territorial(result, params)
        await store_in_kb("BO2", intent, params, knowledge, ttl_minutes=120)
        return result
    except asyncio.TimeoutError:
        return _fallback("BO2", f"Timeout apres {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO2", f"BO2 injoignable sur {settings.agent_bo2_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO2", f"BO2 HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return _fallback("BO2", f"Erreur inattendue BO2: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
#  BO3 - Previsions SARIMA + Estimation de prix  (port 8003)
# ---------------------------------------------------------------------------

async def call_bo3(intent, params, session_id=None):
    base = settings.agent_bo3_url.rstrip("/")
    cached = await get_from_kb("BO3", intent, params)
    if cached:
        cached["from_cache"] = True
        return cached
    try:
        if intent == "price_estimation":
            payload = {
                "city":            params.get("city", params.get("ville", "Tunis")),
                "surface":         float(params.get("surface", params.get("surface_m2", 100))),
                "bedrooms":        float(params.get("bedrooms", params.get("chambres", 2))),
                "bathrooms":       float(params.get("bathrooms", params.get("salles_bain", 1))),
                "budget":          float(params.get("budget", 0)),
                "etage":           float(params.get("etage", 2)),
                "equipment_score": float(params.get("equipment_score", 5)),
            }
            raw, ms = await _post(f"{base}/api/estimate", payload, session_id=session_id)
            if not raw.get("success"):
                return _fallback("BO3", "BO3 a retourne success=false sur /api/estimate")
            est = raw.get("estimation", {})
            dist = raw.get("distribution", {})
            result = {
                "available": True, "agent": "BO3", "intent": "price_estimation", "response_ms": ms,
                "estimated_price": est.get("predicted"),
                "price_range": {"lower": est.get("ci_lower"), "upper": est.get("ci_upper")},
                "confidence_score": est.get("confidence"),
                "price_per_m2":     est.get("price_per_m2"),
                "city_median":      est.get("city_median"),
                "city_ppm2":        est.get("city_ppm2"),
                "city_min":         est.get("city_min"),
                "city_max":         est.get("city_max"),
                "market_delta_pct": est.get("market_delta_pct"),
                "budget_delta":     est.get("budget_delta"),
                "surface_possible": est.get("surface_possible"),
                "model_metrics":    {"r2": est.get("r2"), "rmse": est.get("rmse")},
                "distribution":     {"prices": dist.get("prices", []), "price_per_m2": dist.get("price_per_m2", []), "count": dist.get("count", 0)},
                "from_cache": False,
            }
            knowledge = extract_bo3_estimate(result, params)
            await store_in_kb("BO3", intent, params, knowledge, ttl_minutes=60)
            return result

        if intent in ("location_analysis", "general_query"):
            payload = {
                "budget":    float(params.get("budget", 300_000)),
                "ville":     params.get("ville", params.get("city", "Tunis")),
                "type_bien": params.get("type_bien", "appartement"),
                "priorities": params.get("priorities", []),
            }
            raw, ms = await _post(f"{base}/api/recommend", payload, session_id=session_id)
            result = {
                "available": True, "agent": "BO3", "intent": intent, "response_ms": ms,
                "recommended_zones": [
                    {"zone": z.get("zone"), "price": z.get("price"), "ppm2": z.get("ppm2"),
                     "score": z.get("score"), "advantages": z.get("avantages", []), "trend_pct": z.get("trend")}
                    for z in (raw.get("zones") or [])[:3]
                ],
                "ville": raw.get("ville"), "type_bien": raw.get("type_bien"),
                "data_source": raw.get("data_source"), "from_cache": False,
            }
            knowledge = extract_bo3_recommendations(result, params)
            await store_in_kb("BO3", intent, params, knowledge, ttl_minutes=120)
            return result

        if intent == "investment_analysis":
            gouvernorat = params.get("gouvernorat", params.get("ville", params.get("city", "Tunis")))
            train_payload = {
                "gouvernorat": gouvernorat, "variable": params.get("variable", "PRIX_M2_MEDIAN"),
                "p": int(params.get("p", 1)), "d": int(params.get("d", 1)), "q": int(params.get("q", 1)),
                "P": int(params.get("P", 1)), "D": int(params.get("D", 1)), "Q": int(params.get("Q", 0)),
                "horizon": int(params.get("horizon", 6)),
            }
            train_raw, train_ms = await _post(f"{base}/api/train", train_payload, session_id=session_id)
            if not train_raw.get("success"):
                return _fallback("BO3", "BO3 /api/train a echoue")
            sarima = train_raw.get("data") or {}
            if not sarima:
                analysis_raw, _ = await _get(f"{base}/api/analysis", session_id=session_id)
                sarima = analysis_raw.get("data", {})
            prevision = sarima.get("prevision", {})
            result = {
                "available": True, "agent": "BO3", "intent": "investment_analysis", "response_ms": train_ms,
                "gouvernorat": sarima.get("gouvernorat"), "variable": sarima.get("variable"),
                "model_quality": {"aic": sarima.get("aic"), "bic": sarima.get("bic"),
                                  "adf_stat": sarima.get("adf_stat"), "adf_pval": sarima.get("adf_pval"),
                                  "order": sarima.get("order"), "seasonal_order": sarima.get("seasonal_order")},
                "historical": sarima.get("historique", {}),
                "forecast": {"dates": prevision.get("dates", []), "values": prevision.get("valeurs", []),
                             "lower": prevision.get("lower", []), "upper": prevision.get("upper", [])},
                "current_price_m2":    sarima.get("derniere_valeur"),
                "forecast_price_m2":   sarima.get("prevision_finale"),
                "expected_growth_pct": sarima.get("hausse_pct"),
                "from_cache": False,
            }
            knowledge = extract_bo3_trends(result, params)
            await store_in_kb("BO3", intent, params, knowledge, ttl_minutes=1440)
            return result

        return await call_bo3("location_analysis", params, session_id=session_id)

    except asyncio.TimeoutError:
        return _fallback("BO3", f"Timeout apres {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO3", f"BO3 injoignable sur {settings.agent_bo3_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO3", f"BO3 HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return _fallback("BO3", f"Erreur inattendue BO3: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
#  BO4 - Intelligence decisionnelle d'investissement
#  PPO Agent, SHAP, BUY/HOLD/AVOID  (port 8004)
# ---------------------------------------------------------------------------

async def call_bo4(intent, params, session_id=None):
    base = settings.agent_bo4_url.rstrip("/")
    cached = await get_from_kb("BO4", intent, params)
    if cached:
        cached["from_cache"] = True
        return cached
    try:
        payload = {
            "budget":  float(params.get("budget", 300_000)),
            "cities":  params.get("cities", [params.get("ville", params.get("city", "Tunis"))]),
            "goal":    params.get("goal", "investissement"),
            "horizon": int(params.get("horizon", 5)),
            "risk":    params.get("risk", "modere"),
        }
        raw, ms = await _post(f"{base}/bo4/analyze", payload, session_id=session_id)
        if "recommendations" in raw:
            knowledge = extract_bo4_analysis(raw, payload)
        else:
            raw2, ms2 = await _post(f"{base}/score", payload, session_id=session_id)
            knowledge = extract_bo4_score(raw2, payload)
            ms += ms2
        knowledge["available"]   = True
        knowledge["agent"]       = "BO4"
        knowledge["response_ms"] = ms
        knowledge["from_cache"]  = False
        await store_in_kb("BO4", intent, params, knowledge, ttl_minutes=240)
        return knowledge
    except asyncio.TimeoutError:
        return _fallback("BO4", f"Timeout apres {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO4", f"BO4 injoignable sur {settings.agent_bo4_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO4", f"BO4 HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return _fallback("BO4", f"Erreur inattendue BO4: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
#  BO5 - Conformite legale CDR/CATU  (port 8005)
# ---------------------------------------------------------------------------

async def call_bo5(intent, params, session_id=None):
    base = settings.agent_bo5_url.rstrip("/")
    try:
        raw, ms = await _post(f"{base}/verify", params, session_id=session_id)
        raw["available"] = True
        raw["agent"] = "BO5"
        raw["response_ms"] = ms
        return raw
    except asyncio.TimeoutError:
        return _fallback("BO5", f"Timeout apres {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO5", f"BO5 injoignable sur {settings.agent_bo5_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO5", f"BO5 HTTP {e.response.status_code}")
    except Exception as e:
        return _fallback("BO5", f"Erreur BO5: {e}")


# ---------------------------------------------------------------------------
#  Health check global
# ---------------------------------------------------------------------------

async def check_all_agents() -> dict:
    agents = {
        "BO1": settings.agent_bo1_url.rstrip("/") + "/health",
        "BO2": settings.agent_bo2_url.rstrip("/") + "/health",
        "BO3": settings.agent_bo3_url.rstrip("/") + "/health",
        "BO4": settings.agent_bo4_url.rstrip("/") + "/health",
        "BO5": settings.agent_bo5_url.rstrip("/") + "/health",
    }
    async def ping(name, url):
        try:
            data, _ = await _get(url, timeout=5)
            return name, "ok" if data.get("status") == "ok" else "degraded"
        except Exception:
            return name, "unavailable"
    results = await asyncio.gather(*[ping(n, u) for n, u in agents.items()], return_exceptions=False)
    return dict(results)


# ---------------------------------------------------------------------------
#  APPELS DIRECTS - 0ms overhead reseau (USE_HTTP_AGENTS=false)
# ---------------------------------------------------------------------------

async def direct_bo1(intent, params, session_id=None):
    """Appel direct BO1 — identique au mode HTTP (comme direct_bo3 / direct_bo4)."""
    return await call_bo1(intent=intent, params=params, session_id=session_id)


async def direct_bo2(intent, params, session_id=None):
    """Appel direct BO2 — identique au mode HTTP (comme direct_bo3 / direct_bo4)."""
    return await call_bo2(intent=intent, params=params, session_id=session_id)


async def direct_bo3(intent, params, session_id=None):
    return await call_bo3(intent=intent, params=params, session_id=session_id)


async def direct_bo4(intent, params, session_id=None):
    return await call_bo4(intent=intent, params=params, session_id=session_id)


async def direct_bo5(intent, params, session_id=None):
    return {
        "available": True, "agent": "BO5", "intent": intent,
        "legal_status": "UNKNOWN", "compliance_score": 0,
        "issues": [], "from_cache": False,
        "note": "BO5 direct mode - stub",
    }


# ---------------------------------------------------------------------------
#  DISPATCH UNIFIE
# ---------------------------------------------------------------------------

def _make_dispatcher(http_fn, direct_fn):
    async def dispatcher(intent, params, session_id=None):
        if get_settings().use_http_agents:
            return await http_fn(intent=intent, params=params, session_id=session_id)
        return await direct_fn(intent=intent, params=params, session_id=session_id)
    return dispatcher


dispatch_bo1 = _make_dispatcher(call_bo1, direct_bo1)
dispatch_bo2 = _make_dispatcher(call_bo2, direct_bo2)
dispatch_bo3 = _make_dispatcher(call_bo3, direct_bo3)
dispatch_bo4 = _make_dispatcher(call_bo4, direct_bo4)
dispatch_bo5 = _make_dispatcher(call_bo5, direct_bo5)
