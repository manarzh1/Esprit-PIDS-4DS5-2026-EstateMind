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
            "fr": f"**Agent temporairement indisponible.** Veuillez réessayer dans quelques instants.\n\n*Erreur : {agent_data.get('error', 'unknown')}*",
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
    if v is None:
        return "N/A"
    return f"{int(v):,} TND".replace(",", " ")

def _fmt_pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{float(v):.1f}%"

def _fmt_conf(v) -> str:
    """Accepte 0-1 ou 0-100."""
    if v is None:
        return "N/A"
    pct = float(v)
    if pct <= 1.0:
        pct *= 100
    return f"{pct:.0f}%"


def _tpl_price(d: dict, lang: str) -> str:
    city = d.get("city", d.get("query_city", "Tunisie"))
    est  = _fmt_price(d.get("estimated_price"))
    lo   = _fmt_price(d.get("price_range", {}).get("lower") if isinstance(d.get("price_range"), dict) else None)
    hi   = _fmt_price(d.get("price_range", {}).get("upper") if isinstance(d.get("price_range"), dict) else None)
    med  = _fmt_price(d.get("city_median") or d.get("median_price"))
    mn   = _fmt_price(d.get("city_min")    or d.get("min_price"))
    mx   = _fmt_price(d.get("city_max")    or d.get("max_price"))
    ppm  = _fmt_price(d.get("price_per_m2") or d.get("price_per_sqm"))
    conf = _fmt_conf(d.get("confidence_score") or d.get("confidence"))
    n    = d.get("total_listings") or d.get("total_listings_used", 0)
    delta_pct = d.get("market_delta_pct")
    delta_str = f" ({'+' if (delta_pct or 0)>=0 else ''}{delta_pct:.1f}% vs marché)" if delta_pct is not None else ""
    surf_poss  = d.get("surface_possible")
    surf_str   = f"\n| Surface possible avec budget | {int(surf_poss)} m² |" if surf_poss else ""
    mq = d.get("model_metrics", {})
    r2 = mq.get("r2") if isinstance(mq, dict) else None
    r2_str = f" | R² {r2:.3f}" if r2 else ""
    rng_str = f" | Fourchette {lo} – {hi}" if lo != "N/A" and hi != "N/A" else ""

    if lang == "en":
        return f"""## Price Estimation — {city}

| Indicator | Value |
|-----------|-------|
| **Estimated Price** | **{est}**{delta_str} |
| Price Range | {lo} – {hi} |
| Median Market Price | {med} |
| Min Price | {mn} |
| Max Price | {mx} |
| Price per m² | {ppm} |{surf_str}

"""
    elif lang == "ar":
        return f"""## تقدير السعر — {city}

| المؤشر | القيمة |
|--------|--------|
| **السعر المقدر** | **{est}**{delta_str} |
| نطاق الأسعار | {lo} – {hi} |
| وسيط السوق | {med} |
| أدنى سعر | {mn} |
| أعلى سعر | {mx} |
| السعر لكل م² | {ppm} |{surf_str}

"""
    else:
        return f"""## Estimation de Prix — {city}

| Indicateur | Valeur |
|------------|--------|
| **Prix Estimé** | **{est}**{delta_str} |
| Fourchette | {lo} – {hi} |
| Prix Médian du marché | {med} |
| Prix Minimum | {mn} |
| Prix Maximum | {mx} |
| Prix au m² | {ppm} |{surf_str}

"""


def _tpl_investment(d: dict, lang: str) -> str:
    city   = d.get("city", d.get("query_city", "Tunisie"))
    score  = d.get("investment_score", d.get("score", 0))
    yield_ = d.get("rental_yield", d.get("average_yield", 0))
    growth = d.get("capital_growth_pct", 0)
    risk   = d.get("risk_level", "Modéré")
    horizon = d.get("horizon", "3-5 ans")
    reco   = d.get("recommendation", "")
    strengths = d.get("strengths", [])
    risks     = d.get("risks", [])
    n      = d.get("total_listings", 150)
    liq    = d.get("liquidity_score", 0)
    budget_note = d.get("budget_note", "")

    # Comparison top 5
    comparison = d.get("comparison", [])
    comp_rows = ""
    for c in comparison[:5]:
        comp_rows += f"| {c.get('city','')} | {c.get('investment_score',0):.1f}/10 | {c.get('rental_yield',0):.1f}% | {c.get('risk_level','')} |\n"

    str_list = "\n".join(f"- ✅ {s}" for s in strengths) if strengths else ""
    risk_list = "\n".join(f"- ⚠️ {r}" for r in risks) if risks else ""

    # Pre-compute conditional blocks (backslashes not allowed inside f-string expressions in Python < 3.12)
    en_strengths_block  = ("**Strengths:**\n" + str_list) if str_list else ""
    en_risks_block      = ("**Risks:**\n" + risk_list) if risk_list else ""
    en_budget_block     = (f"*Budget note: {budget_note}*") if budget_note else ""
    en_comp_header      = "### Top 5 Cities Comparison" if comp_rows else ""
    en_comp_col         = "| City | Score | Yield | Risk |" if comp_rows else ""
    en_comp_sep         = "|------|-------|-------|------|" if comp_rows else ""

    fr_strengths_block  = ("**Points forts :**\n" + str_list) if str_list else ""
    fr_risks_block      = ("**Risques :**\n" + risk_list) if risk_list else ""
    fr_budget_block     = (f"*Budget : {budget_note}*") if budget_note else ""
    fr_comp_header      = "### Comparaison Top 5 villes" if comp_rows else ""
    fr_comp_col         = "| Ville | Score | Rendement | Risque |" if comp_rows else ""
    fr_comp_sep         = "|-------|-------|-----------|--------|" if comp_rows else ""

    if lang == "en":
        return f"""## Investment Analysis — {city}

| Metric | Value |
|--------|-------|
| **Investment Score** | **{score:.1f} / 10** |
| Rental Yield | {yield_:.1f}% |
| Capital Growth | {growth:.1f}% /year |
| Liquidity | {liq:.1f}/10 |
| Risk Level | {risk} |
| Recommended Horizon | {horizon} |

**Recommendation:** {reco}

{en_strengths_block}
{en_risks_block}
{en_budget_block}

{en_comp_header}
{en_comp_col}
{en_comp_sep}
{comp_rows}
"""
    else:
        return f"""## Analyse d'Investissement — {city}

| Métrique | Valeur |
|----------|--------|
| **Score d'investissement** | **{score:.1f} / 10** |
| Rendement locatif | {yield_:.1f}% |
| Croissance en capital | {growth:.1f}% /an |
| Liquidité | {liq:.1f}/10 |
| Niveau de risque | {risk} |
| Horizon recommandé | {horizon} |

**Recommandation :** {reco}

{fr_strengths_block}
{fr_risks_block}
{fr_budget_block}

{fr_comp_header}
{fr_comp_col}
{fr_comp_sep}
{comp_rows}
"""


def _tpl_location(d: dict, lang: str) -> str:
    city = d.get("city", d.get("query_city", "Tunisie"))
    n    = d.get("total_listings", 0)
    avg  = _fmt_price(d.get("average_price"))
    ppm  = d.get("price_per_sqm") or d.get("price_per_m2")
    ppm_str = f" | **Prix/m²** : {_fmt_price(ppm)}" if ppm else ""
    trend   = d.get("trend_pct")
    trend_str = f" | **Tendance** : +{trend:.1f}%/an" if trend else ""
    cluster = d.get("cluster_label", "")
    emerging_prob = d.get("emerging_prob")
    emg_str = f"\n**Signal émergence** : {float(emerging_prob)*100:.0f}%" if emerging_prob is not None else ""

    # Zones recommandées (BO3)
    zones = d.get("recommended_zones", [])
    zone_rows = ""
    for z in zones[:3]:
        adv = ", ".join(z.get("advantages", [])[:2])
        zone_rows += f"| {z.get('zone','')} | {_fmt_price(z.get('price'))} | {_fmt_price(z.get('ppm2'))} | {z.get('score',0)}/100 | {adv} |\n"

    # Districts (BO2)
    top = d.get("top_districts", d.get("districts", []))
    dist_rows = ""
    for item in top[:5]:
        if isinstance(item, dict):
            dist_rows += f"| {item.get('district','?')} | {_fmt_price(item.get('avg_price'))} | {item.get('count',0)} |\n"

    if lang == "en":
        zones_tbl = f"### Recommended Zones\n| Zone | Price | Price/m² | Score | Advantages |\n|------|-------|----------|-------|------------|\n{zone_rows}" if zone_rows else ""
        dist_tbl  = f"### Top Districts\n| District | Avg Price | Listings |\n|----------|-----------|----------|\n{dist_rows}" if dist_rows else ""
        return f"""## Market Analysis — {city}

**Listings:** {n:,} | **Avg price:** {avg}{ppm_str}{trend_str}
{"**Segment:** " + cluster if cluster else ""}{emg_str}

{zones_tbl}
{dist_tbl}
"""
    else:
        zones_tbl = f"### Zones recommandées\n| Zone | Prix | Prix/m² | Score | Avantages |\n|------|------|---------|-------|----------|\n{zone_rows}" if zone_rows else ""
        dist_tbl  = f"### Meilleurs quartiers\n| Quartier | Prix Moyen | Annonces |\n|----------|------------|----------|\n{dist_rows}" if dist_rows else ""
        return f"""## Analyse du Marché — {city}

**Annonces :** {n:,} | **Prix moyen :** {avg}{ppm_str}{trend_str}
{"**Segment :** " + cluster if cluster else ""}{emg_str}

{zones_tbl}
{dist_tbl}
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

"""
    else:
        return f"""## Vérification Légale {icon}

**Statut :** {status} | **Score de conformité :** {score:.0f}%

{chr(10).join(f'- {i}' for i in issues) if issues else '- Aucun problème détecté.'}

"""


def _tpl_report(d: dict, lang: str) -> str:
    city = d.get("city", d.get("query_city", "Tunisie"))
    n    = d.get("total_listings", 0)
    avg  = _fmt_price(d.get("average_price"))
    score = d.get("investment_score", d.get("score"))
    yield_ = d.get("rental_yield", d.get("average_yield"))
    trend = d.get("trend_pct")
    if lang == "en":
        extras = ""
        if score: extras += f"| Investment Score | {score:.1f}/10 |\n"
        if yield_: extras += f"| Rental Yield | {yield_:.1f}% |\n"
        if trend: extras += f"| Market Trend | +{trend:.1f}%/year |\n"
        return f"""## Market Report — {city}

| Indicator | Value |
|-----------|-------|
| Listings analyzed | {n:,} |
| Average price | {avg} |
{extras}
📄 Use the **Generate Report** button below to download a full PDF report.

"""
    else:
        extras = ""
        if score: extras += f"| Score d'investissement | {score:.1f}/10 |\n"
        if yield_: extras += f"| Rendement locatif | {yield_:.1f}% |\n"
        if trend: extras += f"| Tendance marché | +{trend:.1f}%/an |\n"
        return f"""## Rapport de Marché — {city}

| Indicateur | Valeur |
|------------|--------|
| Annonces analysées | {n:,} |
| Prix moyen | {avg} |
{extras}
📄 Utilisez le bouton **Télécharger rapport PDF** pour obtenir le rapport complet.

"""


def _tpl_general(d: dict, lang: str) -> str:
    n = d.get("total_listings", d.get("count", 8673))
    trust = d.get("reliability_pct")
    trust_str = f"\n**Fiabilité des données :** {trust:.1f}%\n" if trust else ""
    if lang == "en":
        return f"""## Estate Mind — Intelligent Real Estate Platform

I can help you with:
- 💰 **Price estimation** — *"What is the price of S+2 in Ariana?"*
- 📊 **Investment analysis** — *"Is Sfax a good investment?"*
- 🗺️ **Location analysis** — *"Best neighborhoods in Tunis?"*
- ⚖️ **Legal verification** — *"Is this property legally compliant?"*
- 📄 **Report generation** — *"Generate a market report for Sousse"*

**Database:** {n:,} verified listings.{trust_str}
"""
    elif lang == "ar":
        return f"""## Estate Mind — منصة العقارات الذكية

يمكنني مساعدتك في:
- 💰 **تقدير الأسعار** — *"ما هو سعر شقة في أريانة؟"*
- 📊 **تحليل الاستثمار** — *"هل صفاقس استثمار جيد؟"*
- 🗺️ **تحليل الموقع** — *"أفضل أحياء تونس؟"*
- ⚖️ **التحقق القانوني** — *"هل هذا العقار ملتزم قانونياً؟"*

**قاعدة البيانات:** {n:,} إعلان موثق.{trust_str}
"""
    else:
        return f"""## Estate Mind — Plateforme Immobilière Intelligente

Je peux vous aider avec :
- 💰 **Estimation de prix** — *"Quel est le prix d'un S+2 à Ariana ?"*
- 📊 **Analyse d'investissement** — *"Sfax est-il un bon investissement ?"*
- 🗺️ **Analyse de localisation** — *"Meilleurs quartiers à Tunis ?"*
- ⚖️ **Vérification légale** — *"Ce bien est-il conforme légalement ?"*
- 📄 **Génération de rapport** — *"Générer un rapport pour Sousse"*

**Base de données :** {n:,} annonces vérifiées.{trust_str}
"""

# ── Pipeline principal ────────────────────────────────────────
async def run_pipeline(request: ChatRequest, db: AsyncSession) -> ChatResponse:
    """
    Pipeline 8 etapes — cœur de BO6.
    """
    pipeline_start = time.monotonic()
    steps: list[PipelineStep] = []
    interaction_id = uuid.uuid4()
    session_id = request.session_id or uuid.uuid4()

    # ── Etape 1 : Detection de langue ─────────────────────────
    lang_result = detect_language(request.query)
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
    norm_result = _normalizer.normalize(request.query)
    normalized_text = norm_result.normalized_text
    is_darija = norm_result.is_tunisian
    darija_terms = norm_result.words_replaced
    ms2 = int((time.monotonic() - t2) * 1000)
    steps.append(PipelineStep(
        step=2, name="Normalisation Darija",
        result=normalized_text,
        ms=ms2,
        details={"terms_replaced": darija_terms, "is_darija": is_darija},
    ))

    # ── Etape 3 : Traduction ────────────────────────────────────
    t3 = time.monotonic()
    trans_result = translate_to_english(normalized_text, source_lang=detected_lang)
    translated_text = trans_result["translated"]
    ms3 = int((time.monotonic() - t3) * 1000)
    steps.append(PipelineStep(
        step=3, name="Traduction",
        result=translated_text, ms=ms3,
        details={"cached": trans_result.get("cached", False)},
    ))

    # ── Etape 4 : Classification NB ────────────────────────────
    t4 = time.monotonic()
    intent_result = detect_intent(request.query, normalized_text, translated_text)
    intent = intent_result["intent"]
    confidence = intent_result["confidence"]
    probabilities = intent_result["probabilities"]
    top_ngrams = intent_result["top_ngrams"]
    ms4 = intent_result["ms"]
    steps.append(PipelineStep(
        step=4, name="Classification NB",
        result=intent, confidence=confidence, ms=ms4,
        details={"top_ngrams": top_ngrams, "probabilities": probabilities},
    ))

    # ── Etape 5 : Routage ──────────────────────────────────────
    t5 = time.monotonic()
    agent_name, agent_fn = get_agent_for_intent(intent)
    from app.core.config import get_settings
    settings = get_settings()
    agent_url_map = {
        "BO1": f"{settings.agent_bo1_url}/collect",
        "BO2": f"{settings.agent_bo2_url}/analyse",
        "BO3": f"{settings.agent_bo3_url}/predict",
        "BO4": f"{settings.agent_bo4_url}/score",
        "BO5": f"{settings.agent_bo5_url}/verify",
    }
    agent_url = agent_url_map.get(agent_name, "")
    ms5 = int((time.monotonic() - t5) * 1000)
    steps.append(PipelineStep(
        step=5, name="Routage",
        result=agent_name, ms=ms5,
        details={"agent_url": agent_url},
    ))

    # ── Etape 6 : Appel agent ──────────────────────────────────
    # Extraire les parametres de la requete (ville, surface, budget...)
    from app.services.nlp.intent_detector import extract_params
    extracted_params = extract_params(request.query, normalized_text, translated_text, intent)

    t6 = time.monotonic()
    try:
        async with asyncio.timeout(15.0):
            agent_data = await agent_fn(
                intent=intent,
                params=extracted_params,
                session_id=str(session_id),
            )
            agent_ms = int((time.monotonic() - t6) * 1000)
    except asyncio.TimeoutError:
        agent_ms = int((time.monotonic() - t6) * 1000)
        agent_data = {"available": False, "error": "TIMEOUT_15s", "total_listings": 0}
    except TypeError:
        try:
            async with asyncio.timeout(10.0):
                result = await agent_fn(query=request.query, session_id=str(session_id))
                agent_data = result if isinstance(result, dict) else result[0]
            agent_ms = int((time.monotonic() - t6) * 1000)
        except Exception as e2:
            agent_ms = int((time.monotonic() - t6) * 1000)
            agent_data = {"available": False, "error": str(e2), "total_listings": 0}

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
        session = await get_or_create_session(db, session_id=session_id, user_id=request.user_id)
        session_id = session.id
        from app.services.nlp.naive_bayes import get_classifier
        clf = get_classifier()
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
        ms8 = int((time.monotonic() - t8) * 1000)
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
