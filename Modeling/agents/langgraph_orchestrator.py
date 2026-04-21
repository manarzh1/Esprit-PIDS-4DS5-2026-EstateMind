"""
Estate Mind — LangGraph Orchestrator (v2 corrigé)
══════════════════════════════════════════════════
Architecture multi-agent avec mémoire persistante.

Graphe :
    START
      │
   supervisor  ◄──────────────────────────┐
      │ route                              │
      ├── collector_node                   │
      ├── risk_node                        │ résultats
      ├── legal_node                       │
      ├── market_node                      │
      └── synthesizer_node ───────────────┘
                │
               END

Mémoire :
  - MemorySaver  : persiste l'historique entre appels (par thread_id)
  - EstateMindState.messages : conversation complète accessible à tous les nœuds
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from loguru import logger

from config.settings import LLM_MODEL, OPENAI_API_KEY, PROC_DIR, RAW_CSV_PATH
from agents.graph_state import EstateMindState

from agents.collector_agent import _read_csv_robust
from tools.cleaning_tools import run_full_cleaning
from tools.legal_tools import compute_legal_risk_score, search_legal_rules
from tools.risk_tools import compute_trust_score, get_fraud_flags, run_trust_scoring


# ──────────────────────────────────────────────────────────────────────────────
# UTILITAIRE ANTI-SÉRIALISATION NUMPY
# ──────────────────────────────────────────────────────────────────────────────

def to_python(obj: Any) -> Any:
    """
    Convertit récursivement les types NumPy / pandas en types Python natifs
    compatibles avec msgpack / LangGraph MemorySaver.
    """
    if isinstance(obj, dict):
        return {str(k): to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_python(v) for v in obj]
    if isinstance(obj, tuple):
        return [to_python(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# ─── LLM partagé ──────────────────────────────────────────────────────────────

def _get_llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=temperature,
        api_key=OPENAI_API_KEY,
    )


# ══════════════════════════════════════════════════════════════════════════════
# NŒUD 1 — SUPERVISOR
# ══════════════════════════════════════════════════════════════════════════════

SUPERVISOR_SYSTEM = """Tu es le Supervisor Agent d'Estate Mind, plateforme PropTech tunisienne.

Tu analyses la demande de l'utilisateur et décides quel(s) agent(s) appeler.

AGENTS DISPONIBLES :
  - collector   : charger/nettoyer un CSV d'annonces brutes
  - risk        : calculer le trust score et détecter les fraudes
  - legal       : analyse juridique RAG (lois tunisiennes)
  - market      : aperçu statistique du marché immobilier
  - synthesizer : formuler la réponse finale à l'utilisateur

RÈGLES DE ROUTING :
  • "pipeline" / "traite" / "nettoie le CSV" → collector → risk → legal → synthesizer
  • "analyse cette annonce" / "évalue" → risk + legal → synthesizer
  • "marché" / "prix moyen" / "statistiques" → market → synthesizer
  • "statut" / "status" / "système" → synthesizer
  • Question générale sur l'immobilier → synthesizer directement
  • Si tu as besoin de données non disponibles → demande via synthesizer

Réponds UNIQUEMENT avec un JSON valide :
{
  "intent": "<pipeline|analyze|market|status|chat>",
  "next_node": "<collector|risk|legal|market|synthesizer>",
  "reasoning": "<explication courte en français>",
  "needs_csv": <true|false>
}
"""


def supervisor_node(state: EstateMindState) -> dict:
    logger.info("━━━ [Supervisor] Analyse de la requête")

    query = state["user_query"]
    visited = state.get("visited_nodes", [])
    has_data = bool(
        state.get("cleaned_csv_path")
        and Path(state.get("cleaned_csv_path", "")).exists()
    )

    if visited and "synthesizer" not in visited:
        intent = state.get("intent", "chat")
        if intent == "pipeline" and all(n in visited for n in ["collector", "risk", "legal"]):
            logger.info("[Supervisor] Pipeline complet → synthesizer")
            return to_python({"next_node": "synthesizer", "visited_nodes": visited})

        if intent == "analyze" and all(n in visited for n in ["risk", "legal"]):
            logger.info("[Supervisor] Analyse complète → synthesizer")
            return to_python({"next_node": "synthesizer", "visited_nodes": visited})

        if intent == "market" and "market" in visited:
            logger.info("[Supervisor] Marché traité → synthesizer")
            return to_python({"next_node": "synthesizer", "visited_nodes": visited})

    llm = _get_llm(temperature=0.0)

    context = f"""
Requête utilisateur : {query}
Données disponibles : {"OUI (CSV nettoyé chargé)" if has_data else "NON (aucun CSV chargé)"}
Nœuds déjà exécutés ce tour : {visited or "aucun"}
Historique conversation : {len(state.get("messages", []))} messages précédents
"""

    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM),
        HumanMessage(content=context),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()

        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        routing = json.loads(raw.strip())

    except Exception as e:
        logger.warning(f"[Supervisor] Parsing LLM échoué ({e}), routing par défaut")
        routing = {
            "intent": "chat",
            "next_node": "synthesizer",
            "reasoning": "fallback",
        }

    intent = routing.get("intent", "chat")
    next_node = routing.get("next_node", "synthesizer")
    reasoning = routing.get("reasoning", "")

    logger.info(f"[Supervisor] Intent={intent} → {next_node} | {reasoning}")

    new_messages = []
    if not visited:
        new_messages.append(HumanMessage(content=query))

    payload = {
        "intent": intent,
        "next_node": next_node,
        "visited_nodes": visited + ["supervisor"],
        "messages": new_messages,
        "errors": state.get("errors", []),
    }
    return to_python(payload)


# ══════════════════════════════════════════════════════════════════════════════
# NŒUD 2 — COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

def collector_node(state: EstateMindState) -> dict:
    logger.info("━━━ [Collector] Démarrage nettoyage")

    csv_path = state.get("csv_path") or RAW_CSV_PATH
    errors = state.get("errors", [])

    try:
        df_raw = _read_csv_robust(csv_path)
        rows_in = int(len(df_raw))
        logger.info(f"[Collector] {rows_in} lignes chargées")

        df_clean = run_full_cleaning(df_raw)
        rows_out = int(len(df_clean))

        Path(PROC_DIR).mkdir(parents=True, exist_ok=True)
        output_path = str(Path(PROC_DIR) / "listings_clean.csv")
        df_clean.to_csv(output_path, index=False)

        report = {
            "rows_in": rows_in,
            "rows_out": rows_out,
            "duplicates_removed": int(rows_in - rows_out),
            "missing_price_pct": float(round(df_clean["price"].isna().mean() * 100, 2))
            if "price" in df_clean.columns else None,
            "missing_surface_pct": float(round(df_clean["surface"].isna().mean() * 100, 2))
            if "surface" in df_clean.columns else None,
            "property_type_dist": to_python(
                df_clean["property_type"].value_counts().head(8).to_dict()
            ) if "property_type" in df_clean.columns else {},
            "governorate_dist": to_python(
                df_clean["governorate"].value_counts().head(10).to_dict()
            ) if "governorate" in df_clean.columns else {},
            "price_stats": {
                "mean": float(round(df_clean["price"].mean(), 2))
                if "price" in df_clean.columns and df_clean["price"].notna().any() else None,
                "median": float(round(df_clean["price"].median(), 2))
                if "price" in df_clean.columns and df_clean["price"].notna().any() else None,
                "min": float(round(df_clean["price"].min(), 2))
                if "price" in df_clean.columns and df_clean["price"].notna().any() else None,
                "max": float(round(df_clean["price"].max(), 2))
                if "price" in df_clean.columns and df_clean["price"].notna().any() else None,
            },
            "output_path": str(output_path),
        }

        logger.info(f"[Collector] ✅ {rows_out} annonces nettoyées → {output_path}")

        payload = {
            "cleaned_csv_path": str(output_path),
            "collector_report": to_python(report),
            "visited_nodes": state.get("visited_nodes", []) + ["collector"],
            "errors": errors,
            "messages": [
                AIMessage(content=f"[Collector] ✅ {rows_out}/{rows_in} annonces nettoyées et sauvegardées.")
            ],
        }
        return to_python(payload)

    except Exception as e:
        msg = f"Collector échoué : {e}"
        logger.error(f"[Collector] ❌ {e}")
        payload = {
            "errors": errors + [msg],
            "visited_nodes": state.get("visited_nodes", []) + ["collector"],
            "messages": [AIMessage(content=f"[Collector] ❌ {msg}")],
        }
        return to_python(payload)


# ══════════════════════════════════════════════════════════════════════════════
# NŒUD 3 — RISK
# ══════════════════════════════════════════════════════════════════════════════

def risk_node(state: EstateMindState) -> dict:
    logger.info("━━━ [Risk] Trust scoring")

    errors = state.get("errors", [])
    listing = state.get("listing")

    try:
        import pandas as pd

        if listing:
            row = pd.Series(listing)
            df_ref = pd.DataFrame([listing])

            score = float(compute_trust_score(row, df_ref))
            flags = to_python(get_fraud_flags(row, df_ref))
            level = "Fiable" if score >= 0.75 else ("Moyen" if score >= 0.50 else "Suspect")

            report = {
                "trust_score": float(score),
                "trust_level": str(level),
                "fraud_flags": flags,
                "mode": "single",
            }

            logger.info(f"[Risk] Annonce unique — score={score}, niveau={level}")

        else:
            cleaned_path = state.get("cleaned_csv_path") or str(Path(PROC_DIR) / "listings_clean.csv")

            if not Path(cleaned_path).exists():
                raise FileNotFoundError(f"CSV introuvable : {cleaned_path}")

            df = pd.read_csv(cleaned_path)
            df = run_trust_scoring(df)
            df.to_csv(cleaned_path, index=False)

            mean_score = float(round(df["trust_score"].mean(), 3))
            median_score = float(round(df["trust_score"].median(), 3))
            fiable_count = int((df["trust_score"] >= 0.75).sum())
            moyen_count = int(((df["trust_score"] >= 0.50) & (df["trust_score"] < 0.75)).sum())
            suspect_count = int((df["trust_score"] < 0.50).sum())
            total_count = int(len(df))

            report = {
                "mean_trust_score": mean_score,
                "median_trust_score": median_score,
                "fiable_count": fiable_count,
                "moyen_count": moyen_count,
                "suspect_count": suspect_count,
                "total": total_count,
                "mode": "batch",
            }

            logger.info(f"[Risk] Batch — mean={mean_score}, suspects={suspect_count}/{total_count}")

        report = to_python(report)

        payload = {
            "risk_report": report,
            "trust_score": report.get("trust_score") or report.get("mean_trust_score"),
            "trust_level": report.get("trust_level", ""),
            "fraud_flags": report.get("fraud_flags", []),
            "visited_nodes": state.get("visited_nodes", []) + ["risk"],
            "errors": errors,
            "messages": [
                AIMessage(
                    content=(
                        f"[Risk] ✅ Trust scoring terminé — score moyen : "
                        f"{report.get('mean_trust_score') or report.get('trust_score')}"
                    )
                )
            ],
        }
        return to_python(payload)

    except Exception as e:
        msg = f"Risk scoring échoué : {e}"
        logger.error(f"[Risk] ❌ {e}")
        payload = {
            "errors": errors + [msg],
            "visited_nodes": state.get("visited_nodes", []) + ["risk"],
            "messages": [AIMessage(content=f"[Risk] ❌ {msg}")],
        }
        return to_python(payload)


# ══════════════════════════════════════════════════════════════════════════════
# NŒUD 4 — LEGAL
# ══════════════════════════════════════════════════════════════════════════════

def legal_node(state: EstateMindState) -> dict:
    logger.info("━━━ [Legal] Analyse juridique")

    errors = state.get("errors", [])
    listing = state.get("listing")

    try:
        import pandas as pd

        if listing:
            description = str(listing.get("description", ""))
            city = str(listing.get("city", ""))
            property_type = str(listing.get("property_type", ""))

            risk_data = compute_legal_risk_score(description, city)

            query = f"{property_type} {city} {description[:200]}"
            rag_docs = search_legal_rules(query, k=3)

            relevant_laws = [
                {
                    "article": str(doc.get("article", "N/A")),
                    "excerpt": str(doc.get("content", ""))[:280],
                    "source": str(doc.get("source", "N/A")),
                    "relevance": float(doc.get("relevance", 0)) if doc.get("relevance") is not None else 0.0,
                }
                for doc in rag_docs
            ]

            risk_data["relevant_laws"] = relevant_laws
            risk_data["mode"] = "single"

            report = to_python(risk_data)
            logger.info(f"[Legal] Score={report.get('legal_risk_score')}, niveau={report.get('risk_level')}")

        else:
            cleaned_path = state.get("cleaned_csv_path") or str(Path(PROC_DIR) / "listings_clean.csv")

            if not Path(cleaned_path).exists():
                raise FileNotFoundError(f"CSV introuvable : {cleaned_path}")

            df = pd.read_csv(cleaned_path)
            n = min(50, len(df))

            scores = []
            for _, row in df.head(n).iterrows():
                r = compute_legal_risk_score(
                    str(row.get("description", "")),
                    str(row.get("city", ""))
                )
                scores.append(float(r["legal_risk_score"]))

            scores += [0.1] * max(0, (len(df) - n))
            df["legal_risk_score"] = scores
            df.to_csv(cleaned_path, index=False)

            high_risk = int(sum(1 for s in scores if s >= 0.6))
            medium_risk = int(sum(1 for s in scores if 0.3 <= s < 0.6))
            low_risk = int(sum(1 for s in scores if s < 0.3))

            report = {
                "analyzed": int(n),
                "high_risk_count": high_risk,
                "medium_risk_count": medium_risk,
                "low_risk_count": low_risk,
                "avg_score": float(round(sum(scores[:n]) / n, 3)) if n > 0 else 0.0,
                "mode": "batch",
            }

            logger.info(f"[Legal] Batch — haut={high_risk}, moyen={medium_risk}, faible={low_risk}")

        report = to_python(report)

        payload = {
            "legal_report": report,
            "legal_risk_score": report.get("legal_risk_score"),
            "legal_risk_level": report.get("risk_level", ""),
            "relevant_laws": report.get("relevant_laws", []),
            "legal_recommendations": report.get("recommendations", []),
            "visited_nodes": state.get("visited_nodes", []) + ["legal"],
            "errors": errors,
            "messages": [
                AIMessage(
                    content=(
                        f"[Legal] ✅ Analyse juridique terminée — niveau : "
                        f"{report.get('risk_level', report.get('avg_score', 'N/A'))}"
                    )
                )
            ],
        }
        return to_python(payload)

    except Exception as e:
        msg = f"Analyse légale échouée : {e}"
        logger.error(f"[Legal] ❌ {e}")
        payload = {
            "errors": errors + [msg],
            "visited_nodes": state.get("visited_nodes", []) + ["legal"],
            "messages": [AIMessage(content=f"[Legal] ❌ {msg}")],
        }
        return to_python(payload)


# ══════════════════════════════════════════════════════════════════════════════
# NŒUD 5 — MARKET
# ══════════════════════════════════════════════════════════════════════════════

def market_node(state: EstateMindState) -> dict:
    logger.info("━━━ [Market] Vue marché")

    errors = state.get("errors", [])

    try:
        import pandas as pd

        cleaned_path = state.get("cleaned_csv_path") or str(Path(PROC_DIR) / "listings_clean.csv")

        if not Path(cleaned_path).exists():
            raise FileNotFoundError("Dataset non disponible. Lancez d'abord le pipeline.")

        df = pd.read_csv(cleaned_path)

        query = state.get("user_query", "").lower()
        city = ""
        prop_type = ""

        governorates = [
            "tunis", "ariana", "sousse", "sfax", "nabeul", "monastir",
            "bizerte", "hammamet", "la marsa", "carthage", "djerba",
        ]
        for gov in governorates:
            if gov in query:
                city = gov.title()
                break

        property_types = ["appartement", "villa", "terrain", "maison", "studio", "bureau"]
        for pt in property_types:
            if pt in query:
                prop_type = pt
                break

        df_filtered = df.copy()

        if city and "city" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["city"].astype(str).str.lower() == city.lower()]

        if prop_type and "property_type" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["property_type"].astype(str).str.lower() == prop_type.lower()]

        if len(df_filtered) < 3:
            df_filtered = df

        df_filtered = df_filtered.copy()
        df_filtered["ppm2"] = df_filtered["price"] / df_filtered["surface"]

        report = {
            "filters": {
                "city": city or "Toutes",
                "property_type": prop_type or "Tous",
            },
            "sample_size": int(len(df_filtered)),
            "price": {
                "median": float(round(df_filtered["price"].median(), 0)),
                "mean": float(round(df_filtered["price"].mean(), 0)),
                "min": float(round(df_filtered["price"].min(), 0)),
                "max": float(round(df_filtered["price"].max(), 0)),
            },
            "surface": {
                "median": float(round(df_filtered["surface"].median(), 1)),
                "mean": float(round(df_filtered["surface"].mean(), 1)),
            },
            "price_per_m2": {
                "median": float(round(df_filtered["ppm2"].median(), 0)),
                "mean": float(round(df_filtered["ppm2"].mean(), 0)),
            },
            "property_types": to_python(
                df_filtered["property_type"].value_counts().head(6).to_dict()
            ) if "property_type" in df_filtered.columns else {},
            "top_cities": to_python(
                df_filtered["city"].value_counts().head(6).to_dict()
            ) if (not city and "city" in df_filtered.columns) else {},
        }

        logger.info(f"[Market] ✅ {report['sample_size']} annonces analysées")

        payload = {
            "market_report": to_python(report),
            "visited_nodes": state.get("visited_nodes", []) + ["market"],
            "errors": errors,
            "messages": [
                AIMessage(content=f"[Market] ✅ Vue marché calculée — {report['sample_size']} annonces.")
            ],
        }
        return to_python(payload)

    except Exception as e:
        msg = f"Vue marché échouée : {e}"
        logger.error(f"[Market] ❌ {e}")
        payload = {
            "errors": errors + [msg],
            "visited_nodes": state.get("visited_nodes", []) + ["market"],
            "messages": [AIMessage(content=f"[Market] ❌ {msg}")],
        }
        return to_python(payload)


# ══════════════════════════════════════════════════════════════════════════════
# NŒUD 6 — SYNTHESIZER
# ══════════════════════════════════════════════════════════════════════════════

SYNTHESIZER_SYSTEM = """Tu es le Synthesizer d'Estate Mind, plateforme PropTech tunisienne.

Tu reçois les résultats bruts des agents spécialisés (Collector, Risk, Legal, Market)
et tu formules une réponse claire, structurée et orientée action pour l'utilisateur.

RÈGLES :
- Langue : français
- Ton : professionnel, concis, orienté décision
- Toujours expliquer ce que signifient les scores (trust_score, legal_risk_score)
- Inclure des recommandations concrètes
- Si des erreurs sont présentes, les mentionner clairement
- Ne jamais inventer de données non présentes dans le contexte
- Maximum 400 mots dans la réponse
"""


def synthesizer_node(state: EstateMindState) -> dict:
    logger.info("━━━ [Synthesizer] Formulation de la réponse")

    llm = _get_llm(temperature=0.2)

    context_parts = [f"Requête : {state.get('user_query', '')}"]

    if state.get("collector_report"):
        r = state["collector_report"]
        context_parts.append(
            f"\n[COLLECTOR]\n"
            f"- Lignes brutes : {r.get('rows_in')} → nettoyées : {r.get('rows_out')}\n"
            f"- Doublons supprimés : {r.get('duplicates_removed')}\n"
            f"- Fichier produit : {r.get('output_path')}"
        )

    if state.get("risk_report"):
        r = state["risk_report"]
        if r.get("mode") == "batch":
            context_parts.append(
                f"\n[RISK SCORING]\n"
                f"- Score moyen de confiance : {r.get('mean_trust_score')}/1.0\n"
                f"- Fiables (≥0.75) : {r.get('fiable_count')} | "
                f"Moyens : {r.get('moyen_count')} | "
                f"Suspects (<0.50) : {r.get('suspect_count')}"
            )
        else:
            context_parts.append(
                f"\n[RISK SCORING - ANNONCE UNIQUE]\n"
                f"- Trust score : {r.get('trust_score')}/1.0\n"
                f"- Niveau : {r.get('trust_level')}\n"
                f"- Signaux d'alerte : {', '.join(r.get('fraud_flags', [])) or 'aucun'}"
            )

    if state.get("legal_report"):
        r = state["legal_report"]
        if r.get("mode") == "batch":
            context_parts.append(
                f"\n[ANALYSE JURIDIQUE]\n"
                f"- Risque élevé : {r.get('high_risk_count')} annonces\n"
                f"- Risque moyen : {r.get('medium_risk_count')} annonces\n"
                f"- Risque faible : {r.get('low_risk_count')} annonces\n"
                f"- Score moyen : {r.get('avg_score')}"
            )
        else:
            laws = r.get("relevant_laws", [])
            laws_text = "\n".join(
                f"  • {l.get('article', 'N/A')} ({l.get('source', 'N/A')}) : {l.get('excerpt', '')[:150]}"
                for l in laws[:2]
            )
            recs = "\n".join(f"  → {rec}" for rec in r.get("recommendations", [])[:3])
            context_parts.append(
                f"\n[ANALYSE JURIDIQUE - ANNONCE UNIQUE]\n"
                f"- Score de risque légal : {r.get('legal_risk_score')}/1.0\n"
                f"- Niveau : {r.get('risk_level')}\n"
                f"- Signaux : {', '.join(r.get('flags', [])) or 'aucun'}\n"
                f"- Lois pertinentes :\n{laws_text}\n"
                f"- Recommandations :\n{recs}"
            )

    if state.get("market_report"):
        r = state["market_report"]
        p = r.get("price", {})
        ppm2 = r.get("price_per_m2", {})
        context_parts.append(
            f"\n[VUE MARCHÉ]\n"
            f"- Filtre : {r['filters']['city']} / {r['filters']['property_type']}\n"
            f"- Échantillon : {r.get('sample_size')} annonces\n"
            f"- Prix médian : {p.get('median')} TND | Moyen : {p.get('mean')} TND\n"
            f"- Prix/m² médian : {ppm2.get('median')} TND/m²\n"
            f"- Types de biens : {r.get('property_types', {})}"
        )

    if state.get("errors"):
        context_parts.append(
            f"\n[ERREURS]\n" + "\n".join(f"- {e}" for e in state["errors"])
        )

    context = "\n".join(context_parts)

    messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(content=context),
    ]

    try:
        response = llm.invoke(messages)
        final_response = response.content
    except Exception as e:
        logger.error(f"[Synthesizer] Erreur LLM : {e}")
        final_response = f"Résultats disponibles :\n{context}"

    logger.info(f"[Synthesizer] ✅ Réponse générée ({len(final_response)} chars)")

    payload = {
        "final_response": final_response,
        "visited_nodes": state.get("visited_nodes", []) + ["synthesizer"],
        "messages": [AIMessage(content=final_response)],
    }
    return to_python(payload)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTEURS
# ══════════════════════════════════════════════════════════════════════════════

def route_after_supervisor(
    state: EstateMindState,
) -> Literal["collector", "risk", "legal", "market", "synthesizer"]:
    next_node = state.get("next_node", "synthesizer")
    valid = {"collector", "risk", "legal", "market", "synthesizer"}
    return next_node if next_node in valid else "synthesizer"


def route_after_collector(
    state: EstateMindState,
) -> Literal["risk", "synthesizer"]:
    intent = state.get("intent", "chat")
    errors = state.get("errors", [])
    if errors or intent not in ("pipeline",):
        return "synthesizer"
    return "risk"


def route_after_risk(
    state: EstateMindState,
) -> Literal["legal", "synthesizer"]:
    intent = state.get("intent", "chat")
    errors = state.get("errors", [])
    if errors or intent not in ("pipeline", "analyze"):
        return "synthesizer"
    return "legal"


def route_after_legal(state: EstateMindState) -> Literal["synthesizer"]:
    return "synthesizer"


def route_after_market(state: EstateMindState) -> Literal["synthesizer"]:
    return "synthesizer"


# ══════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DU GRAPHE
# ══════════════════════════════════════════════════════════════════════════════

def build_estate_mind_graph() -> Any:
    graph = StateGraph(EstateMindState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("collector", collector_node)
    graph.add_node("risk", risk_node)
    graph.add_node("legal", legal_node)
    graph.add_node("market", market_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "collector": "collector",
            "risk": "risk",
            "legal": "legal",
            "market": "market",
            "synthesizer": "synthesizer",
        },
    )

    graph.add_conditional_edges(
        "collector",
        route_after_collector,
        {
            "risk": "risk",
            "synthesizer": "synthesizer",
        },
    )

    graph.add_conditional_edges(
        "risk",
        route_after_risk,
        {
            "legal": "legal",
            "synthesizer": "synthesizer",
        },
    )

    graph.add_conditional_edges(
        "legal",
        route_after_legal,
        {
            "synthesizer": "synthesizer",
        },
    )

    graph.add_conditional_edges(
        "market",
        route_after_market,
        {
            "synthesizer": "synthesizer",
        },
    )

    graph.add_edge("synthesizer", END)

    memory = MemorySaver()
    compiled = graph.compile(checkpointer=memory)

    logger.info("[LangGraph] ✅ Graphe Estate Mind compilé avec MemorySaver")
    return compiled


# ══════════════════════════════════════════════════════════════════════════════
# INTERFACE PUBLIQUE
# ══════════════════════════════════════════════════════════════════════════════

class EstateMindGraph:
    """
    Interface principale d'Estate Mind avec LangGraph + mémoire.
    """

    def __init__(self):
        self.graph = build_estate_mind_graph()
        logger.info("[EstateMindGraph] Prêt")

    def chat(
        self,
        user_input: str,
        thread_id: str = "default",
        csv_path: str | None = None,
        listing: dict | None = None,
    ) -> str:
        logger.info(f"[EstateMindGraph] thread={thread_id} | input={user_input[:80]}...")

        config = {"configurable": {"thread_id": thread_id}}

        initial_state: EstateMindState = {
            "messages": [],
            "user_query": user_input,
            "next_node": None,
            "visited_nodes": [],
            "intent": None,
            "csv_path": csv_path or RAW_CSV_PATH,
            "cleaned_csv_path": None,
            "collector_report": None,
            "risk_report": None,
            "trust_score": None,
            "trust_level": None,
            "fraud_flags": None,
            "legal_report": None,
            "legal_risk_score": None,
            "legal_risk_level": None,
            "relevant_laws": None,
            "legal_recommendations": None,
            "market_report": None,
            "listing": listing,
            "final_response": None,
            "errors": [],
        }

        result = self.graph.invoke(initial_state, config=config)
        return result.get("final_response", "Aucune réponse générée.")

    def analyze_property(
        self,
        description: str,
        price: float,
        surface: float,
        city: str,
        property_type: str = "appartement",
        source: str = "particulier",
        thread_id: str = "default",
    ) -> str:
        listing = {
            "description": description,
            "price": price,
            "surface": surface,
            "city": city,
            "property_type": property_type,
            "source": source,
        }
        return self.chat(
            user_input=f"Analyse cette annonce immobilière à {city} : {description[:100]}",
            thread_id=thread_id,
            listing=listing,
        )

    def run_pipeline(
        self,
        csv_path: str = RAW_CSV_PATH,
        thread_id: str = "default",
    ) -> str:
        return self.chat(
            user_input="Lance le pipeline complet : nettoyage, trust scoring et analyse juridique.",
            thread_id=thread_id,
            csv_path=csv_path,
        )

    def get_memory(self, thread_id: str = "default") -> list:
        config = {"configurable": {"thread_id": thread_id}}
        try:
            snapshot = self.graph.get_state(config)
            return snapshot.values.get("messages", [])
        except Exception:
            return []


# ══════════════════════════════════════════════════════════════════════════════
# RUN DIRECT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    agent = EstateMindGraph()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        response = agent.chat(query, thread_id="cli")
        print(response)
    else:
        print("\n🏠 Estate Mind — LangGraph Agent")
        print("   Tape 'quit' pour quitter\n")

        session = "demo_session"
        while True:
            try:
                user_input = input("Vous : ").strip()
                if user_input.lower() in ("quit", "exit", "q"):
                    break
                if not user_input:
                    continue

                response = agent.chat(user_input, thread_id=session)
                print(f"\nEstate Mind : {response}\n")
                print("─" * 60)

            except KeyboardInterrupt:
                break

    print("\nAu revoir !")