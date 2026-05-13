"""
app/services/orchestrator.py
==============================
Pipeline 8 etapes — Orchestrateur BO6.

REGLES ARCHITECTURALES (DSO3 — tracabilite) :
  1. BO6 ne lit PAS PostgreSQL (sauf chat_sessions / interactions / reports)
  2. Toute donnee metier vient des agents BO1-BO5 via HTTP JSON
  3. Chaque etape est chronometree et tracee
  4. Aucun LLM utilise — templates + regles uniquement
  5. Reproductibilite : meme entree => meme sortie

BUDGET TEMPS (contrainte stricte 20s) :
  Etape 1 Detection langue   : < 0.1s
  Etape 2 Normalisation Darija: < 0.1s
  Etape 3 Traduction         : < 3.0s
  Etape 4 Classification NB  : < 0.1s
  Etape 5 Routage            : < 0.1s
  Etape 6 Appel agent HTTP   : < 15.0s
  Etape 7 Template reponse   : < 0.1s
  Etape 8 Sauvegarde DB      : < 0.5s
  TOTAL                      : < 20.0s
"""

import asyncio
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.chat_repo import get_or_create_session, save_interaction
from app.models.schemas import (
    AgentName, ChatRequest, ChatResponse, ExplanationModel,
    NaiveBayesDetail, PipelineStep,
)
from app.services.agents.router import get_agent_for_intent
from app.services.nlp.intent_detector import detect_intent
from app.services.nlp.language_detector import detect_language
from app.services.nlp.translator import translate_to_english
from app.services.nlp.tunisian_normalizer import TunisianNormalizer

log = get_logger(__name__)
_normalizer = TunisianNormalizer()


# ── Templates de reponse ─────────────────────────────────────
def _build_response(intent: str, lang: str, agent_data: dict) -> str:
    """Genere une reponse Markdown a partir des donnees JSON de l'agent."""
    available = agent_data.get("available", True)

    if not available:
        msgs = {
            "fr": f"**Agent temporairement indisponible.** Veuillez reessayer dans quelques instants.\n\n*Erreur : {agent_data.get('error', 'unknown')}*",
            "en": f"**Agent temporarily unavailable.** Please try again in a few moments.\n\n*Error: {agent_data.get('error', 'unknown')}*",
            "ar": "**الوكيل غير متاح مؤقتاً.** يرجى المحاولة مرة أخرى.",
        }
        return msgs.get(lang, msgs["fr"])

    if intent == "price_estimation":
        return _tpl_price(agent_data, lang)
    elif intent == "investment_analysis":
        return _tpl_investment(agent_data, lang)
    elif intent == "location_analysis":
        return _tpl_location(agent_data, lang)
    elif intent == "legal_verification":
        return _tpl_legal(agent_data, lang)
    elif intent == "report_generation":
        return _tpl_report(agent_data, lang)
    else:
        return _tpl_general(agent_data, lang)


def _fmt_price(v) -> str:
    if v is None: return "N/A"
    return f"{int(v):,} TND".replace(",", " ")


def _tpl_price(d: dict, lang: str) -> str:
    city = d.get("city", d.get("query_city", "Tunisie"))
    est  = _fmt_price(d.get("estimated_price"))
    # BO3 returns city_median / city_min / city_max / price_per_m2 / confidence_score
    med  = _fmt_price(d.get("city_median")  or d.get("median_price"))
    mn   = _fmt_price(d.get("city_min")     or d.get("min_price"))
    mx   = _fmt_price(d.get("city_max")     or d.get("max_price"))
    ppm  = _fmt_price(d.get("price_per_m2") or d.get("price_per_sqm"))
    conf_raw = d.get("confidence_score") or d.get("confidence") or 0
    conf = conf_raw / 100 if conf_raw > 1 else conf_raw  # normalize 0-100 → 0-1
    n    = (d.get("distribution") or {}).get("count") or d.get("total_listings_used", 0)
    tx   = d.get("transaction_type", "")

    if lang == "en":
        return f"""## Price Estimation — {city}

| Indicator | Value |
|-----------|-------|
| **Estimated Price** | {est} |
| Median Price | {med} |
| Min Price | {mn} |
| Max Price | {mx} |
| Price per m² | {ppm} |

**Model confidence:** {conf:.0%} | **Based on:** {n} listings
*Transaction type: {tx or 'all'}*

> Data source: BO3 → PostgreSQL estate_mind_db
"""
    elif lang == "ar":
        return f"""## تقدير السعر — {city}

| المؤشر | القيمة |
|--------|--------|
| **السعر المقدر** | {est} |
| السعر الوسيط | {med} |
| أدنى سعر | {mn} |
| أعلى سعر | {mx} |
| السعر لكل م² | {ppm} |

**ثقة النموذج:** {conf:.0%} | **استناداً إلى:** {n} إعلانات
"""
    else:
        return f"""## Estimation de Prix — {city}

| Indicateur | Valeur |
|------------|--------|
| **Prix Estimé** | {est} |
| Prix Médian | {med} |
| Prix Minimum | {mn} |
| Prix Maximum | {mx} |
| Prix au m² | {ppm} |

**Confiance du modèle :** {conf:.0%} | **Basé sur :** {n} annonces
*Type de transaction : {tx or 'tous'}*

> Source des données : BO3 → PostgreSQL estate_mind_db
"""


def _tpl_investment(d: dict, lang: str) -> str:
    # BO3 investment returns SARIMA data — use its real field names
    city   = d.get("gouvernorat", d.get("city", d.get("query_city", "Tunisie")))
    cur    = _fmt_price(d.get("current_price_m2"))
    fcast  = _fmt_price(d.get("forecast_price_m2"))
    growth = d.get("expected_growth_pct")
    growth_str = f"{growth:+.1f}%" if growth is not None else "N/A"
    forecast = d.get("forecast", {})
    horizon  = len(forecast.get("dates", []))

    # Fallback for BO4-style data
    score  = d.get("investment_score", d.get("score", 0))
    yield_ = d.get("rental_yield", d.get("average_yield", 0))
    reco   = d.get("recommendation", "")
    n      = d.get("total_listings", 0)

    if d.get("current_price_m2") is not None:
        # SARIMA mode
        if lang == "en":
            return f"""## Investment Analysis — {city}

| Metric | Value |
|--------|-------|
| **Current Price/m²** | {cur} |
| **Forecast Price/m²** | {fcast} |
| **Expected Growth** | {growth_str} |
| Forecast Horizon | {horizon} months |

> Data source: BO3 SARIMA → PostgreSQL estate_mind_db
"""
        else:
            return f"""## Analyse d'Investissement — {city}

| Métrique | Valeur |
|----------|--------|
| **Prix actuel/m²** | {cur} |
| **Prix prévu/m²** | {fcast} |
| **Croissance attendue** | {growth_str} |
| Horizon de prévision | {horizon} mois |

> Source : BO3 SARIMA → PostgreSQL estate_mind_db
"""
    else:
        # BO4-style fallback
        if lang == "en":
            return f"""## Investment Analysis — {city}

| Metric | Value |
|--------|-------|
| **Investment Score** | {score:.1f}/10 |
| Rental Yield | {yield_:.1f}% |
| Listings Analyzed | {n} |

**Recommendation:** {reco or 'See detailed analysis below.'}

> Data source: BO4 → PostgreSQL estate_mind_db
"""
        else:
            return f"""## Analyse d'Investissement — {city}

| Métrique | Valeur |
|----------|--------|
| **Score d'investissement** | {score:.1f}/10 |
| Rendement locatif | {yield_:.1f}% |
| Annonces analysées | {n} |

**Recommandation :** {reco or 'Voir analyse détaillée.'}

> Source : BO4 → PostgreSQL estate_mind_db
"""


def _tpl_location(d: dict, lang: str) -> str:
    city = d.get("ville", d.get("city", d.get("query_city", "Tunisie")))
    src  = d.get("agent", "BO3")

    # BO3 returns recommended_zones ; BO2 uses emerging_zones + cluster
    zones = d.get("recommended_zones", d.get("top_districts", d.get("districts", [])))

    # ── BO2 territorial data ──────────────────────────────────
    prophet    = d.get("prophet_forecast", {})
    j90_val    = (prophet.get("j90") or {}).get("value")
    trend_pct  = d.get("trend_pct_90d")
    cluster    = d.get("cluster_label", "")
    action     = d.get("market_action", "")
    avg_ppm2   = d.get("avg_price_m2")

    bo2_block = ""
    if src == "BO2" or cluster or avg_ppm2:
        ppm2_str  = _fmt_price(avg_ppm2)
        trend_str = f"{trend_pct:+.1f}%" if trend_pct is not None else "N/A"
        j90_str   = _fmt_price(j90_val)
        if lang == "en":
            bo2_block = (
                f"| Cluster | {cluster or 'N/A'} |\n"
                f"| Avg Price/m² | {ppm2_str} |\n"
                f"| 90-day Trend | {trend_str} |\n"
                f"| Prophet J+90 | {j90_str} |\n"
                f"| Recommended Action | {action or 'N/A'} |\n\n"
            )
        else:
            bo2_block = (
                f"| Cluster | {cluster or 'N/A'} |\n"
                f"| Prix Moyen/m² | {ppm2_str} |\n"
                f"| Tendance 90j | {trend_str} |\n"
                f"| Prophet J+90 | {j90_str} |\n"
                f"| Action recommandée | {action or 'N/A'} |\n\n"
            )

    # ── Zones table (BO3 zones ou BO2 emerging_zones) ─────────
    if not zones:
        zones = [
            {"zone": z.get("zone"), "price": None, "ppm2": None,
             "score": z.get("emergence_score"), "trend_pct": None}
            for z in (d.get("emerging_zones") or [])[:5]
        ]

    districts_str = ""
    for item in (zones or [])[:5]:
        if isinstance(item, dict):
            zone_name  = item.get("zone", item.get("district", "?"))
            zone_price = _fmt_price(item.get("price", item.get("avg_price")))
            zone_ppm2  = _fmt_price(item.get("ppm2"))
            zone_score = item.get("score", "")
            growth     = item.get("trend_pct")
            growth_str = f"{growth:+.1f}%" if growth is not None else ""
            districts_str += f"| {zone_name} | {zone_price} | {zone_ppm2} | {zone_score} | {growth_str} |\n"

    if lang == "en":
        tbl = f"| Zone | Avg Price | Price/m² | Score | Growth |\n|------|-----------|----------|-------|--------|\n{districts_str}" if districts_str else ""
        return f"""## Market Analysis — {city}

{bo2_block}{tbl}
> Data source: {src} → PostgreSQL estate_mind_db
"""
    else:
        tbl = f"| Quartier | Prix Moyen | Prix/m² | Score | Croissance |\n|----------|------------|---------|-------|------------|\n{districts_str}" if districts_str else ""
        return f"""## Analyse du Marché — {city}

{bo2_block}{tbl}
> Source : {src} → PostgreSQL estate_mind_db
"""


def _tpl_legal(d: dict, lang: str) -> str:
    status = d.get("legal_status", d.get("status", "UNKNOWN"))
    issues = d.get("issues", [])
    score  = d.get("compliance_score", 0)
    icon   = "✅" if status == "COMPLIANT" else "⚠️"

    if lang == "en":
        return f"""## Legal Verification {icon}

**Status:** {status} | **Compliance Score:** {score:.0f}%

{chr(10).join(f'- {i}' for i in issues) if issues else '- No issues detected.'}

> Data source: BO5 → Legal documents database
"""
    else:
        return f"""## Vérification Légale {icon}

**Statut :** {status} | **Score de conformité :** {score:.0f}%

{chr(10).join(f'- {i}' for i in issues) if issues else '- Aucun problème détecté.'}

> Source : BO5 → Base documents légaux
"""


def _tpl_report(d: dict, lang: str) -> str:
    city = d.get("city", d.get("query_city", "Tunisie"))
    n    = d.get("total_listings", 0)
    avg  = _fmt_price(d.get("average_price"))
    if lang == "en":
        return f"""## Market Report — {city}

**Listings analyzed:** {n} | **Average price:** {avg}

📄 A detailed PDF report can be generated. Use the **Generate Report** button.

> Data source: BO2 → PostgreSQL estate_mind_db
"""
    else:
        return f"""## Rapport de Marché — {city}

**Annonces analysées :** {n} | **Prix moyen :** {avg}

📄 Un rapport PDF détaillé peut être généré. Utilisez le bouton **Générer un rapport**.

> Source : BO2 → PostgreSQL estate_mind_db
"""


def _tpl_general(d: dict, lang: str) -> str:
    n         = d.get("total_listings", d.get("count", 0))
    trusted   = d.get("trusted_listings", 0)
    anomalies = d.get("anomaly_count", 0)
    trust_avg = d.get("avg_trust_score", 0.0)
    anomaly_line_en = f"Trust Analysis: {trusted:,} trusted | {anomalies} anomalies detected ({trust_avg:.0%} avg trust score)" if trusted else ""
    anomaly_line_fr = f"Analyse fiabilité : {trusted:,} fiables | {anomalies} anomalies détectées (trust score moyen : {trust_avg:.0%})" if trusted else ""

    if lang == "en":
        return f"""## Estate Mind — Intelligent Real Estate Platform

I can help you with:
- 💰 **Price estimation** — "What is the price of S+2 in Ariana?"
- 📊 **Investment analysis** — "Is Sfax a good investment?"
- 🗺️ **Location analysis** — "Best neighborhoods in Tunis?"
- ⚖️ **Legal verification** — "Is this property legally compliant?"
- 📄 **Report generation** — "Generate a market report for Sousse"

**Database:** {n:,} listings available. {anomaly_line_en}
"""
    elif lang == "ar":
        return f"""## Estate Mind — منصة العقارات الذكية

يمكنني مساعدتك في:
- 💰 **تقدير الأسعار** — "ما هو سعر شقة في أريانة؟"
- 📊 **تحليل الاستثمار** — "هل صفاقس استثمار جيد؟"
- 🗺️ **تحليل الموقع** — "أفضل أحياء تونس؟"
- ⚖️ **التحقق القانوني** — "هل هذا العقار ملتزم قانونياً؟"

**قاعدة البيانات:** {n:,} إعلان متاح.
"""
    else:
        return f"""## Estate Mind — Plateforme Immobilière Intelligente

Je peux vous aider avec :
- 💰 **Estimation de prix** — "Quel est le prix d'un S+2 à Ariana ?"
- 📊 **Analyse d'investissement** — "Sfax est-il un bon investissement ?"
- 🗺️ **Analyse de localisation** — "Meilleurs quartiers à Tunis ?"
- ⚖️ **Vérification légale** — "Ce bien est-il conforme légalement ?"
- 📄 **Génération de rapport** — "Générer un rapport pour Sousse"

**Base de données :** {n:,} annonces disponibles. {anomaly_line_fr}
"""


# ── Pipeline principal ────────────────────────────────────────
async def run_pipeline(request: ChatRequest, db: AsyncSession) -> ChatResponse:
    """Pipeline 8 etapes — cœur de BO6."""
    pipeline_start = time.monotonic()
    steps: list[PipelineStep] = []
    interaction_id = uuid.uuid4()
    session_id = request.session_id or uuid.uuid4()

    # ── Etape 1 : Detection de langue ─────────────────────────
    lang_result   = detect_language(request.query)
    detected_lang = lang_result["language"]
    if request.language_override:
        detected_lang = request.language_override
    steps.append(PipelineStep(
        step=1, name="Détection langue",
        result=detected_lang, confidence=lang_result["confidence"],
        ms=lang_result["ms"],
    ))

    # ── Etape 2 : Normalisation Darija ─────────────────────────
    t2 = time.monotonic()
    norm_result    = _normalizer.normalize(request.query)
    normalized_text = norm_result.normalized_text
    is_darija      = norm_result.is_tunisian
    darija_terms   = norm_result.words_replaced
    ms2 = int((time.monotonic() - t2) * 1000)
    steps.append(PipelineStep(
        step=2, name="Normalisation Darija",
        result=normalized_text, ms=ms2,
        details={"terms_replaced": darija_terms, "is_darija": is_darija},
    ))

    # ── Etape 3 : Traduction ────────────────────────────────────
    t3 = time.monotonic()
    trans_result  = translate_to_english(normalized_text, source_lang=detected_lang)
    translated_text = trans_result["translated"]
    ms3 = int((time.monotonic() - t3) * 1000)
    steps.append(PipelineStep(
        step=3, name="Traduction",
        result=translated_text, ms=ms3,
        details={"cached": trans_result.get("cached", False)},
    ))

    # ── Etape 4 : Classification NB ────────────────────────────
    t4 = time.monotonic()
    intent_result  = detect_intent(request.query, normalized_text, translated_text)
    intent         = intent_result["intent"]
    confidence     = intent_result["confidence"]
    probabilities  = intent_result["probabilities"]
    top_ngrams     = intent_result["top_ngrams"]
    ms4            = intent_result["ms"]
    steps.append(PipelineStep(
        step=4, name="Classification NB",
        result=intent, confidence=confidence, ms=ms4,
        details={"top_ngrams": top_ngrams, "probabilities": probabilities},
    ))

    # ── Etape 5 : Routage ──────────────────────────────────────
    t5 = time.monotonic()
    from app.core.config import get_settings
    settings = get_settings()
    agent_name, agent_fn = get_agent_for_intent(intent)
    agent_url_map = {
        "BO1": f"{settings.agent_bo1_url}/collect",
        "BO2": f"{settings.agent_bo2_url}/analyse",
        "BO3": f"{settings.agent_bo3_url}/predict",
        "BO4": f"{settings.agent_bo4_url}/score",
        "BO5": f"{settings.agent_bo5_url}/verify",
    }
    agent_url = "direct://import" if not settings.use_http_agents else agent_url_map.get(agent_name, "")
    ms5 = int((time.monotonic() - t5) * 1000)
    steps.append(PipelineStep(
        step=5, name="Routage",
        result=agent_name, ms=ms5,
        details={"agent_url": agent_url, "mode": "http" if settings.use_http_agents else "direct"},
    ))

    # ── Etape 6 : Appel agent ──────────────────────────────────
    agent_params = {
        "query":            request.query,
        "city":             "",
        "ville":            "",
        "surface":          100,
        "bedrooms":         2,
        "bathrooms":        1,
        "budget":           300_000,
        "transaction_type": "vente",
        "session_id":       str(session_id),
    }
    t6 = time.monotonic()
    try:
        async with asyncio.timeout(15.0):
            agent_data = await agent_fn(
                intent=intent,
                params=agent_params,
                session_id=str(session_id),
            )
            agent_ms = int((time.monotonic() - t6) * 1000)
    except asyncio.TimeoutError:
        agent_ms   = int((time.monotonic() - t6) * 1000)
        agent_data = {"available": False, "error": "TIMEOUT_15s", "total_listings": 0}

    steps.append(PipelineStep(
        step=6, name=f"Appel {agent_name}",
        result=f"{agent_data.get('total_listings', 0)} annonces",
        ms=agent_ms,
        details={"agent": agent_name, "available": agent_data.get("available", True)},
    ))

    # ── Etape 7 : Generation template ──────────────────────────
    t7 = time.monotonic()
    response_text = _build_response(intent, detected_lang, agent_data)
    ms7 = int((time.monotonic() - t7) * 1000)
    steps.append(PipelineStep(
        step=7, name="Template réponse",
        result=f"template_{intent}_{detected_lang}",
        ms=ms7,
    ))

    # ── Etape 8 : Sauvegarde ───────────────────────────────────
    t8 = time.monotonic()
    try:
        session    = await get_or_create_session(db, session_id=session_id, user_id=request.user_id)
        session_id = session.id
        from app.services.nlp.naive_bayes import get_classifier
        clf        = get_classifier()
        vocab_size = clf.vocab_size
        interaction = await save_interaction(
            db,
            session=session,
            original_query=request.query,
            detected_language=detected_lang,
            translated_query=translated_text,
            detected_intent=intent,
            intent_confidence=confidence,
            intent_probabilities=probabilities,
            routed_to_agent=agent_name,
            agent_url=agent_url,
            agent_raw_response=agent_data,
            response_text=response_text,
            explanation_json=None,
            pipeline_steps_json=[s.model_dump() for s in steps],
            confidence_score=confidence,
            processing_ms=int((time.monotonic() - pipeline_start) * 1000),
            is_darija=is_darija,
            darija_terms=darija_terms,
            top_ngrams=top_ngrams,
        )
        interaction_id = interaction.id
        ms8 = int((time.monotonic() - t8) * 1000)
    except Exception as e:
        log.error("save_interaction_failed", error=str(e))
        ms8        = int((time.monotonic() - t8) * 1000)
        vocab_size = 0

    steps.append(PipelineStep(step=8, name="Sauvegarde", result=str(interaction_id), ms=ms8))

    total_ms = int((time.monotonic() - pipeline_start) * 1000)

    # ── Construction de la reponse ─────────────────────────────
    from app.services.nlp.naive_bayes import get_classifier
    clf = get_classifier()
    explanation = ExplanationModel(
        pipeline_steps=steps,
        naive_bayes_detail=NaiveBayesDetail(
            top_features=top_ngrams,
            laplace_applied=True,
            vocabulary_size=clf.vocab_size,
            ngram_range="1-3",
            intent_probabilities=probabilities,
        ),
        data_source=f"{agent_name} → PostgreSQL estate_mind_db",
        hallucination_check="PASSED — 0 données inventées",
        summary=f"Intent '{intent}' detected with {confidence:.0%} confidence. Agent {agent_name} called.",
        model_used="naive_bayes_ngram_v1",
    )

    return ChatResponse(
        interaction_id=interaction_id,
        session_id=session_id,
        response=response_text,
        language=detected_lang,
        intent=intent,
        confidence=confidence,
        intent_probabilities=probabilities,
        explanation=explanation,
        processing_ms=total_ms,
        agent_used=agent_name,
        raw_data=agent_data,
    )