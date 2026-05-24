"""
app/services/agents/agent_clients.py
=====================================
Clients HTTP + mode direct (USE_HTTP_AGENTS=false) pour les agents BO1-BO5.
En mode direct, les appels HTTP sont remplacés par les mock agents avec données réelles.
"""

import time
import asyncio
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.services.knowledge.kb_retriever import get_from_kb, store_in_kb
from app.services.knowledge.extractors import (
    extract_bo3_estimate,
    extract_bo3_recommendations,
    extract_bo3_trends,
    extract_bo4_analysis,
    extract_bo4_score,
)

# ── Mock agents (activés quand USE_HTTP_AGENTS=false) ────────────────────────
from app.services.agents.bo1_mock_agent import (
    analyze_listing     as _bo1_analyze_listing,
    get_listings        as _bo1_get_listings,
    get_dashboard       as _bo1_get_dashboard,
    detect_anomaly      as _bo1_detect_anomaly,
)
from app.services.agents.bo2_mock_agent import (
    get_forecast        as _bo2_get_forecast,
    get_clusters        as _bo2_get_clusters,
    get_cluster_city    as _bo2_get_cluster_city,
    predict_emerging    as _bo2_predict_emerging,
    get_market_overview as _bo2_get_market_overview,
    get_xai_forecast    as _bo2_get_xai_forecast,
)
from app.services.agents.bo3_mock_agent import (
    estimate_price   as _bo3_estimate_price,
    recommend_zones  as _bo3_recommend_zones,
    sarima_invest    as _bo3_sarima_invest,
)
from app.services.agents.bo4_mock_agent import (
    score_investment       as _bo4_score_investment,
    get_investment_profile as _bo4_get_investment_profile,
    compare_cities         as _bo4_compare_cities,
)

settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _fallback(agent: str, error: str) -> dict:
    return {
        "available": False,
        "agent":     agent,
        "error":     error,
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
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=float(timeout or settings.agent_timeout), write=5.0, pool=5.0)
    ) as client:
        resp = await client.post(url, json=payload, headers=_headers(session_id))
        resp.raise_for_status()
        return resp.json(), int((time.monotonic() - t0) * 1000)

async def _get(url, timeout=None, session_id=None):
    t0 = time.monotonic()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=float(timeout or settings.agent_timeout), write=5.0, pool=5.0)
    ) as client:
        resp = await client.get(url, headers=_headers(session_id))
        resp.raise_for_status()
        return resp.json(), int((time.monotonic() - t0) * 1000)


# ─────────────────────────────────────────────────────────────────────────────
#  BO3
# ─────────────────────────────────────────────────────────────────────────────

def _call_bo3_direct(intent, params):
    city = params.get("city", params.get("ville", "Tunis"))

    if intent == "price_estimation":
        raw = _bo3_estimate_price(
            city=city,
            surface=float(params.get("surface", params.get("surface_m2", 100))),
            bedrooms=float(params.get("bedrooms", params.get("chambres", 2))),
            bathrooms=float(params.get("bathrooms", params.get("salles_bain", 1))),
            budget=float(params.get("budget", 0)),
        )
        est  = raw["estimation"]
        dist = raw["distribution"]
        conf_pct = est["confidence"]
        return {
            "available":          True,
            "agent":              "BO3",
            "intent":             "price_estimation",
            "city":               raw["city_resolved"],
            "query_city":         raw["city_resolved"],
            "estimated_price":    est["predicted"],
            "price_range":        {"lower": est["ci_lower"], "upper": est["ci_upper"]},
            "confidence_score":   conf_pct,
            "price_per_m2":       est["price_per_m2"],
            "city_median":        est["city_median"],
            "city_ppm2":          est["city_ppm2"],
            "city_min":           est["city_min"],
            "city_max":           est["city_max"],
            "market_delta_pct":   est["market_delta_pct"],
            "budget_delta":       est["budget_delta"],
            "surface_possible":   est["surface_possible"],
            "model_metrics":      {"r2": est["r2"], "rmse": est["rmse"]},
            "distribution":       dist,
            "total_listings":     raw["total_listings"],
            # Alias pour _tpl_price dans orchestrator
            "median_price":       est["city_median"],
            "min_price":          est["city_min"],
            "max_price":          est["city_max"],
            "price_per_sqm":      est["price_per_m2"],
            "confidence":         conf_pct / 100.0,
            "total_listings_used": raw["total_listings"],
            "transaction_type":   "vente",
            "from_cache":         False,
        }

    if intent in ("location_analysis", "general_query"):
        raw = _bo3_recommend_zones(
            ville=city,
            budget=float(params.get("budget", 300_000)),
            type_bien=params.get("type_bien", "appartement"),
        )
        zones = raw["zones"]
        return {
            "available":     True,
            "agent":         "BO3",
            "intent":        intent,
            "city":          raw["ville"],
            "query_city":    raw["ville"],
            "recommended_zones": [
                {"zone": z["zone"], "price": z["price"], "ppm2": z["ppm2"],
                 "score": z["score"], "advantages": z["avantages"], "trend_pct": z["trend"]}
                for z in zones[:3]
            ],
            "ville":         raw["ville"],
            "type_bien":     raw["type_bien"],
            "data_source":   raw["data_source"],
            "total_listings": raw["total_listings"],
            "average_price": zones[0]["price"] if zones else None,
            "top_districts": [
                {"district": z["zone"], "avg_price": z["price"], "count": raw["total_listings"] // max(len(zones), 1)}
                for z in zones[:5]
            ],
            "from_cache":    False,
        }

    if intent == "investment_analysis":
        raw  = _bo3_sarima_invest(gouvernorat=city)
        data = raw["data"]
        return {
            "available":           True,
            "agent":               "BO3",
            "intent":              "investment_analysis",
            "gouvernorat":         data["gouvernorat"],
            "variable":            data["variable"],
            "model_quality": {
                "aic": data["aic"], "bic": data["bic"],
                "adf_stat": data["adf_stat"], "adf_pval": data["adf_pval"],
                "order": data["order"], "seasonal_order": data["seasonal_order"],
            },
            "historical": data["historique"],
            "forecast": {
                "dates":  data["prevision"]["dates"],
                "values": data["prevision"]["valeurs"],
                "lower":  [],
                "upper":  [],
            },
            "current_price_m2":    data["derniere_valeur"],
            "forecast_price_m2":   data["prevision_finale"],
            "expected_growth_pct": data["hausse_pct"],
            "from_cache":          False,
        }

    return _call_bo3_direct("location_analysis", params)


async def call_bo3(intent, params, session_id=None):
    if not settings.use_http_agents:
        return _call_bo3_direct(intent, params)

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
                return _fallback("BO3", "BO3 success=false")
            est  = raw.get("estimation", {})
            dist = raw.get("distribution", {})
            conf_pct = est.get("confidence", 0)
            result = {
                "available": True, "agent": "BO3", "intent": "price_estimation", "response_ms": ms,
                "estimated_price":    est.get("predicted"),
                "price_range":        {"lower": est.get("ci_lower"), "upper": est.get("ci_upper")},
                "confidence_score":   conf_pct,
                "price_per_m2":       est.get("price_per_m2"),
                "city_median":        est.get("city_median"),
                "city_ppm2":          est.get("city_ppm2"),
                "city_min":           est.get("city_min"),
                "city_max":           est.get("city_max"),
                "market_delta_pct":   est.get("market_delta_pct"),
                "budget_delta":       est.get("budget_delta"),
                "surface_possible":   est.get("surface_possible"),
                "model_metrics":      {"r2": est.get("r2"), "rmse": est.get("rmse")},
                "distribution":       {"prices": dist.get("prices",[]), "price_per_m2": dist.get("price_per_m2",[]), "count": dist.get("count",0)},
                "from_cache": False,
                "median_price":       est.get("city_median"),
                "min_price":          est.get("city_min"),
                "max_price":          est.get("city_max"),
                "price_per_sqm":      est.get("price_per_m2"),
                "confidence":         (conf_pct or 0) / 100.0,
                "total_listings_used": dist.get("count", 0),
                "transaction_type":   "vente",
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
            zones = raw.get("zones", [])
            result = {
                "available": True, "agent": "BO3", "intent": intent, "response_ms": ms,
                "recommended_zones": [
                    {"zone": z.get("zone"), "price": z.get("price"), "ppm2": z.get("ppm2"),
                     "score": z.get("score"), "advantages": z.get("avantages",[]), "trend_pct": z.get("trend")}
                    for z in zones[:3]
                ],
                "ville": raw.get("ville"), "type_bien": raw.get("type_bien"),
                "data_source": raw.get("data_source"), "from_cache": False,
                "average_price": zones[0].get("price") if zones else None,
                "top_districts": [{"district": z.get("zone"), "avg_price": z.get("price"), "count": 50} for z in zones[:5]],
            }
            knowledge = extract_bo3_recommendations(result, params)
            await store_in_kb("BO3", intent, params, knowledge, ttl_minutes=120)
            return result

        if intent == "investment_analysis":
            gouvernorat = params.get("gouvernorat", params.get("ville", params.get("city", "Tunis")))
            train_payload = {
                "gouvernorat": gouvernorat, "variable": params.get("variable","PRIX_M2_MEDIAN"),
                "p": int(params.get("p",1)), "d": int(params.get("d",1)), "q": int(params.get("q",1)),
                "P": int(params.get("P",1)), "D": int(params.get("D",1)), "Q": int(params.get("Q",0)),
                "horizon": int(params.get("horizon",6)),
            }
            train_raw, train_ms = await _post(f"{base}/api/train", train_payload, session_id=session_id)
            if not train_raw.get("success"):
                return _fallback("BO3", "BO3 /api/train failed")
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
                "forecast": {"dates": prevision.get("dates",[]), "values": prevision.get("valeurs",[]),
                             "lower": prevision.get("lower",[]), "upper": prevision.get("upper",[])},
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
        return _fallback("BO3", f"Timeout après {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO3", f"BO3 injoignable sur {settings.agent_bo3_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO3", f"BO3 HTTP {e.response.status_code}")
    except Exception as e:
        return _fallback("BO3", f"Erreur BO3: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  BO1
# ─────────────────────────────────────────────────────────────────────────────

def _call_bo1_direct(intent, params):
    city = params.get("city", params.get("ville", "Tunis"))
    dashboard = _bo1_get_dashboard()
    listings  = _bo1_get_listings(city=city, min_trust=0.5, limit=5)
    trust_info = _bo1_analyze_listing(
        price=float(params.get("budget", params.get("price", 300000))),
        surface=float(params.get("surface", 100)),
        city=city,
        description=params.get("query", ""),
        source="tayara",
    )
    anomaly = _bo1_detect_anomaly(
        price=float(params.get("budget", params.get("price", 300000))),
        surface=float(params.get("surface", 100)),
    )
    city_listings = _bo1_get_listings(city=city, min_trust=0.0, limit=500)
    city_count = len(city_listings)
    city_avg_trust = sum(l.get("trust_score", 0.7) for l in city_listings) / max(city_count, 1)
    return {
        "available":         True,
        "agent":             "BO1",
        "intent":            intent,
        "city":              city,
        "query_city":        city,
        "total_listings":    dashboard["total"],
        "total_listings_used": city_count or dashboard["total"],
        "count":             dashboard["total"],
        "trust_score":       trust_info.get("trust_score", city_avg_trust),
        "trust_label":       trust_info.get("trust_label", trust_info.get("label", "Fiable")),
        "city_avg_trust":    round(city_avg_trust, 3),
        "anomaly_detected":  anomaly.get("is_anomaly", False),
        "anomaly_reason":    anomaly.get("reason", ""),
        "suspect_count":     dashboard["suspect_count"],
        "sources":           dashboard["sources"],
        "sample_listings":   listings[:3],
        "market_health":     "Sain" if city_avg_trust > 0.75 else "Modéré",
        "reliability_pct":   round(city_avg_trust * 100, 1),
        "average_price":     None,
        "from_cache":        False,
    }


async def call_bo1(intent, params, session_id=None):
    if not settings.use_http_agents:
        return _call_bo1_direct(intent, params)

    base = settings.agent_bo1_url.rstrip("/")
    try:
        payload = {
            "query":      params.get("query", ""),
            "session_id": session_id or "",
            "city":       params.get("city", params.get("ville", "")),
        }
        raw, ms = await _post(f"{base}/collect", payload, session_id=session_id)
        raw["available"]   = True
        raw["agent"]       = "BO1"
        raw["response_ms"] = ms
        raw.setdefault("total_listings", raw.get("count", 0))
        return raw
    except asyncio.TimeoutError:
        return _fallback("BO1", f"Timeout après {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO1", f"BO1 injoignable sur {settings.agent_bo1_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO1", f"BO1 HTTP {e.response.status_code}")
    except Exception as e:
        return _fallback("BO1", f"Erreur BO1: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  BO2
# ─────────────────────────────────────────────────────────────────────────────

def _call_bo2_direct(intent, params):
    city = params.get("city", params.get("ville", "Tunis"))
    forecast = _bo2_get_forecast(city=city)
    cluster  = _bo2_get_cluster_city(city=city)
    emerging = _bo2_predict_emerging(
        city=city,
        median_price=forecast.get("last_known_price", forecast.get("last_known", 2500)),
    )
    xai      = _bo2_get_xai_forecast(city=city)
    overview = _bo2_get_market_overview()
    ppm2_val = forecast.get("mean_predicted", 2500)
    cluster_cities = cluster.get("cluster_cities", cluster.get("cities", [city]))
    top_districts = [
        {"district": c, "avg_price": int(ppm2_val * 100), "count": 50}
        for c in cluster_cities[:5]
    ]
    return {
        "available":          True,
        "agent":              "BO2",
        "intent":             intent,
        "city":               city,
        "query_city":         city,
        "total_listings":     8673,
        "total_listings_used": overview.get("total_listings", 8673),
        "count":              overview.get("total_listings", 8673),
        "average_price":      int(ppm2_val * 100),
        "price_per_sqm":      ppm2_val,
        "trend_pct":          forecast.get("trend_pct", 2.5),
        "trend_label":        forecast.get("trend_label", "hausse"),
        "mape":               forecast.get("model_mape", forecast.get("mape", 12.0)),
        "cluster_label":      cluster.get("cluster_label", cluster.get("label", "Villes intermédiaires")),
        "cluster_id":         cluster.get("cluster_id", 2),
        "emerging_prob":      emerging.get("emergence_proba", emerging.get("emerging_probability", 0.5)),
        "emerging_signal":    "Fort signal" if emerging.get("emergence_proba", 0) >= 0.85 else "Signal modéré",
        "xai_factors":        xai.get("factors", []),
        "top_districts":      top_districts,
        "districts":          top_districts,
        "national_median":    overview.get("national_median_ppm2", 2500),
        "from_cache":         False,
    }


async def call_bo2(intent, params, session_id=None):
    if not settings.use_http_agents:
        return _call_bo2_direct(intent, params)

    base = settings.agent_bo2_url.rstrip("/")
    try:
        payload = {
            "query":            params.get("query", ""),
            "city":             params.get("city", params.get("ville", "")),
            "transaction_type": params.get("transaction_type", "vente"),
        }
        raw, ms = await _post(f"{base}/analyse", payload, session_id=session_id)
        raw["available"]   = True
        raw["agent"]       = "BO2"
        raw["response_ms"] = ms
        raw.setdefault("total_listings", raw.get("count", 0))
        return raw
    except asyncio.TimeoutError:
        return _fallback("BO2", f"Timeout après {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO2", f"BO2 injoignable sur {settings.agent_bo2_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO2", f"BO2 HTTP {e.response.status_code}")
    except Exception as e:
        return _fallback("BO2", f"Erreur BO2: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  BO4
# ─────────────────────────────────────────────────────────────────────────────

def _call_bo4_direct(intent, params):
    city   = params.get("city", params.get("ville", "Tunis"))
    budget = float(params.get("budget", 300_000))
    ptype  = params.get("property_type", params.get("type_bien", "appartement"))

    scored   = _bo4_score_investment(city=city, budget=budget, property_type=ptype)
    cities_q = params.get("cities", [city])
    if len(cities_q) < 2:
        cities_q = ["Tunis", "Hammamet", "Sousse", "Sfax", "Nabeul"]
    comparison = _bo4_compare_cities(cities=cities_q)

    return {
        "available":          True,
        "agent":              "BO4",
        "intent":             intent,
        "city":               city,
        "query_city":         city,
        "investment_score":   scored["investment_score"],
        "score":              scored["investment_score"],
        "rental_yield":       scored["rental_yield"],
        "average_yield":      scored["rental_yield"],
        "capital_growth_pct": scored["capital_growth_pct"],
        "liquidity_score":    scored["liquidity_score"],
        "risk_level":         scored["risk_level"],
        "horizon":            scored["horizon"],
        "budget_note":        scored["budget_note"],
        "recommendation":     scored["recommendation"],
        "strengths":          scored["strengths"],
        "risks":              scored["risks"],
        "total_listings":     scored["total_listings"],
        "comparison":         comparison["comparison"],
        "national":           comparison["national"],
        "from_cache":         False,
    }


async def call_bo4(intent, params, session_id=None):
    if not settings.use_http_agents:
        return _call_bo4_direct(intent, params)

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
            "risk":    params.get("risk", "modéré"),
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
        knowledge.setdefault("total_listings", 150)
        await store_in_kb("BO4", intent, params, knowledge, ttl_minutes=240)
        return knowledge
    except asyncio.TimeoutError:
        return _fallback("BO4", f"Timeout après {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO4", f"BO4 injoignable sur {settings.agent_bo4_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO4", f"BO4 HTTP {e.response.status_code}")
    except Exception as e:
        return _fallback("BO4", f"Erreur BO4: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  BO5
# ─────────────────────────────────────────────────────────────────────────────

async def call_bo5(intent, params, session_id=None):
    base = settings.agent_bo5_url.rstrip("/")
    try:
        raw, ms = await _post(f"{base}/verify", params, session_id=session_id)
        raw["available"]   = True
        raw["agent"]       = "BO5"
        raw["response_ms"] = ms
        return raw
    except asyncio.TimeoutError:
        return _fallback("BO5", f"Timeout après {settings.agent_timeout}s")
    except httpx.ConnectError:
        return _fallback("BO5", f"BO5 injoignable sur {settings.agent_bo5_url}")
    except httpx.HTTPStatusError as e:
        return _fallback("BO5", f"BO5 HTTP {e.response.status_code}")
    except Exception as e:
        return _fallback("BO5", f"Erreur BO5: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Health check global
# ─────────────────────────────────────────────────────────────────────────────

async def check_all_agents() -> dict:
    if not settings.use_http_agents:
        return {
            "BO1": "ok (direct)",
            "BO2": "ok (direct)",
            "BO3": "ok (direct)",
            "BO4": "ok (direct)",
            "BO5": "unavailable",
        }

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

    results = await asyncio.gather(*[ping(n, u) for n, u in agents.items()])
    return dict(results)
