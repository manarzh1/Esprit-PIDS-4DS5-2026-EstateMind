"""
Estate Mind — Territorial Agent (BO2)
══════════════════════════════════════
Agent dédié à l'analyse des dynamiques territoriales du marché immobilier tunisien.

Couvre les 3 DSOs du BO2 :
  DSO1 : Séries temporelles → tendances de prix et volume par zone
  DSO2 : Agrégation spatiale → stats par gouvernorat/ville/région
  DSO3 : Détection des zones émergentes → alertes automatiques

Architecture :
  - LangChain tool-calling agent avec few-shot prompt tunisien
  - 5 outils LangChain wrappant les fonctions de territorial_tools.py
  - Nœud LangGraph intégré dans l'orchestrateur principal
  - Sortie : rapport JSON + résumé textuel pour le frontend
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import (
    LLM_MODEL, LLM_TEMPERATURE, OPENAI_API_KEY, RAW_CSV_PATH, PROC_DIR
)
from tools.territorial_tools import (
    prepare_temporal_data,
    compute_time_series,
    compute_spatial_aggregation,
    detect_emerging_zones,
    generate_territorial_report,
)


# ── Chemins de données ────────────────────────────────────────────────────────

CLEAN_CSV   = str(Path(PROC_DIR) / "listings_clean.csv")
COMBINED_CSV = RAW_CSV_PATH


def _load_best_df() -> pd.DataFrame:
    """Charge le meilleur dataset disponible (clean > combined)."""
    for path in [CLEAN_CSV, COMBINED_CSV]:
        p = Path(path)
        if p.exists():
            try:
                sep = ";" if path == COMBINED_CSV else ","
                df  = pd.read_csv(path, sep=sep, on_bad_lines="skip",
                                  encoding="utf-8", encoding_errors="replace")
                if len(df) > 10 and len(df.columns) > 1:
                    logger.info(f"[TerritorialAgent] Dataset chargé : {path} ({len(df)} lignes)")
                    return df
            except Exception as e:
                logger.warning(f"[TerritorialAgent] Échec lecture {path} : {e}")
    logger.error("[TerritorialAgent] Aucun dataset disponible")
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# TOOLS LANGCHAIN
# ══════════════════════════════════════════════════════════════════════════════

@tool
def analyze_time_series(
    group_by: str = "city",
    freq:     str = "M",
) -> str:
    """
    DSO1 — Calcule les séries temporelles de prix et volume par zone.
    Détecte les tendances (hausse/baisse/stable) via régression linéaire.

    Args:
        group_by : "city" | "governorate" | "region"
        freq     : "M" (mensuel) | "W" (hebdo) | "Q" (trimestriel)

    Returns:
        JSON avec series, trends et summary par zone.
    """
    df = _load_best_df()
    if df.empty:
        return json.dumps({"error": "Dataset indisponible"})

    df_prep = prepare_temporal_data(df)
    result  = compute_time_series(df_prep, group_by=group_by, freq=freq)

    logger.info(f"[DSO1] Séries temporelles calculées : "
                f"{result['summary']['n_zones_analyzed']} zones, "
                f"hausse={result['summary']['n_hausse']}")
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def analyze_spatial_distribution() -> str:
    """
    DSO2 — Calcule l'agrégation spatiale du marché immobilier tunisien.
    Produit des statistiques par gouvernorat, ville et région + heatmap.

    Returns:
        JSON avec by_governorate, by_city, by_region, heatmap_data.
    """
    df = _load_best_df()
    if df.empty:
        return json.dumps({"error": "Dataset indisponible"})

    df_prep = prepare_temporal_data(df)
    result  = compute_spatial_aggregation(df_prep)

    logger.info(f"[DSO2] Agrégation spatiale : "
                f"{result['summary']['n_governorates']} gouvernorats, "
                f"{result['summary']['n_cities']} villes")
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def detect_zones(
    group_by:          str   = "city",
    lookback_recent:   int   = 45,
    lookback_previous: int   = 90,
    price_threshold:   float = 0.08,
    volume_threshold:  float = 0.20,
) -> str:
    """
    DSO3 — Détecte les zones émergentes et en déclin + génère des alertes.

    Méthode : comparaison prix médian et volume entre période récente
    (lookback_recent derniers jours) et période précédente.
    Score composite = 0.6 × croissance_prix + 0.4 × croissance_volume.

    Args:
        group_by          : "city" | "governorate"
        lookback_recent   : jours pour la période récente (défaut 45)
        lookback_previous : jours pour la période de référence (défaut 90)
        price_threshold   : seuil de croissance de prix ex: 0.08 = 8%
        volume_threshold  : seuil de croissance de volume ex: 0.20 = 20%

    Returns:
        JSON avec alerts, emerging_zones, declining_zones et summary.
    """
    df = _load_best_df()
    if df.empty:
        return json.dumps({"error": "Dataset indisponible"})

    df_prep = prepare_temporal_data(df)
    result  = detect_emerging_zones(
        df_prep,
        group_by=group_by,
        lookback_recent=lookback_recent,
        lookback_previous=lookback_previous,
        price_threshold=price_threshold,
        volume_threshold=volume_threshold,
    )

    logger.info(f"[DSO3] {result['summary']['n_alerts']} alertes, "
                f"{result['summary']['n_emerging']} zones émergentes")
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_zone_detail(zone_name: str, group_by: str = "city") -> str:
    """
    Retourne les statistiques détaillées d'une zone spécifique :
    prix médian, volume, tendance temporelle, type de biens dominants.

    Args:
        zone_name : nom de la ville ou du gouvernorat
        group_by  : "city" | "governorate"
    """
    df = _load_best_df()
    if df.empty:
        return json.dumps({"error": "Dataset indisponible"})

    df_prep = prepare_temporal_data(df)

    # Filtrage de la zone
    col = group_by if group_by in df_prep.columns else "city"
    sub = df_prep[df_prep[col].astype(str).str.lower() == zone_name.lower()]

    if sub.empty:
        return json.dumps({"error": f"Zone '{zone_name}' non trouvée"})

    price    = sub["price"].dropna()
    ppm2     = sub["price_per_m2"].dropna() if "price_per_m2" in sub.columns else pd.Series()
    ts       = compute_time_series(sub, group_by=col, freq="M")
    trend    = ts["trends"].get(zone_name, ts["trends"].get(
                   list(ts["trends"].keys())[0] if ts["trends"] else "",""))

    result = {
        "zone":             zone_name,
        "type":             group_by,
        "n_listings":       int(len(sub)),
        "median_price":     round(float(price.median()), 0) if not price.empty else None,
        "mean_price":       round(float(price.mean()), 0)   if not price.empty else None,
        "median_ppm2":      round(float(ppm2.median()), 0)  if not ppm2.empty else None,
        "trend":            trend,
        "time_series":      ts["series"].get(zone_name, []),
        "property_types":   sub["property_type"].value_counts().head(5).to_dict()
                            if "property_type" in sub.columns else {},
        "price_distribution": {
            "q25": round(float(price.quantile(0.25)), 0) if not price.empty else None,
            "q75": round(float(price.quantile(0.75)), 0) if not price.empty else None,
            "min": round(float(price.min()), 0)           if not price.empty else None,
            "max": round(float(price.max()), 0)           if not price.empty else None,
        }
    }
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def generate_full_report() -> str:
    """
    Génère le rapport territorial complet (DSO1 + DSO2 + DSO3).
    Sauvegarde un JSON dans data/reports/ pour le frontend.

    Returns:
        Chemin du rapport JSON + résumé global.
    """
    df     = _load_best_df()
    run_id = f"territorial_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    if df.empty:
        return json.dumps({"error": "Dataset indisponible"})

    result = generate_territorial_report(df, run_id=run_id)

    summary = {
        "run_id":           run_id,
        "json_path":        result.get("json_path"),
        "total_listings":   result["global_summary"]["total_listings"],
        "date_range":       result["global_summary"]["date_range"],
        "n_cities":         result["global_summary"]["n_cities_covered"],
        "n_governorates":   result["global_summary"]["n_gov_covered"],
        "n_emerging_zones": result["global_summary"]["n_emerging_zones"],
        "n_alerts":         result["global_summary"]["n_alerts"],
        "n_ts_zones":       result["global_summary"]["n_ts_zones"],
        "top_emerging":     result["emerging"]["summary"].get("top_emerging", []),
        "status":           "success",
    }
    return json.dumps(summary, ensure_ascii=False, default=str)


# ══════════════════════════════════════════════════════════════════════════════
# FEW-SHOT SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

TERRITORIAL_SYSTEM_PROMPT = """Tu es le Territorial Agent d'Estate Mind, spécialisé dans l'analyse
des dynamiques spatio-temporelles du marché immobilier tunisien.

TON RÔLE : analyser les tendances de prix et volume par zone géographique,
identifier les zones émergentes, et générer des alertes actionnables.

OUTILS DISPONIBLES :
  1. analyze_time_series    → DSO1 : tendances temporelles par ville/gouvernorat
  2. analyze_spatial_distribution → DSO2 : stats complètes par zone géographique
  3. detect_zones           → DSO3 : zones émergentes + alertes
  4. get_zone_detail        → analyse détaillée d'une zone spécifique
  5. generate_full_report   → rapport complet DSO1+DSO2+DSO3 (JSON pour frontend)

CONTEXTE TUNISIEN :
  - 24 gouvernorats, 7 grandes régions
  - Marchés clés : Grand Tunis (Tunis, Ariana, Ben Arous, Manouba),
    Côte-Est (Sousse, Monastir, Mahdia, Nabeul, Sfax)
  - Zones touristiques sous tension : Hammamet, Sousse, Monastir, Djerba/Médenine
  - Zones sous-évaluées à surveiller : Mahdia, Tozeur, Bizerte

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXEMPLES DE RAISONNEMENT (few-shot)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXEMPLE 1 — Analyse complète du marché
Instruction : "Lance l'analyse territoriale complète"
Raisonnement :
  → J'appelle generate_full_report() pour tout calculer en une fois
  → DSO1 révèle : Nabeul en hausse (+12%/mois), Sfax stable, Kasserine en baisse
  → DSO2 révèle : Grand Tunis = 42% du volume national, prix/m² médian 2800 TND
  → DSO3 génère 3 alertes : Hammamet (émergente), Mahdia (volume_surge), Zaghouan (déclin)
  → Je retourne un résumé structuré avec les insights clés

EXEMPLE 2 — Question sur une zone spécifique
Instruction : "Comment évolue le marché à Sousse ?"
Raisonnement :
  → get_zone_detail(zone_name="Sousse", group_by="city")
  → Je présente : tendance mensuelle, prix médian, distribution des types de biens
  → Si tendance = hausse avec haute confiance → signaler comme zone à surveiller

EXEMPLE 3 — Détection d'urgence
Instruction : "Y a-t-il des zones avec une hausse anormale ces 45 derniers jours ?"
Raisonnement :
  → detect_zones(lookback_recent=45, price_threshold=0.10)
  → Je liste les alertes par ordre de sévérité : critical > high > medium
  → Pour chaque alerte critique, j'appelle get_zone_detail() pour confirmer

EXEMPLE 4 — Focus temporel
Instruction : "Montre-moi les tendances trimestrielles par gouvernorat"
Raisonnement :
  → analyze_time_series(group_by="governorate", freq="Q")
  → Je résume : quels gouvernorats sont en hausse soutenue, lesquels stagnent

RÈGLES D'ANALYSE :
  - Une tendance est "significative" seulement si confidence = "high"
  - Une zone émergente avec < 5 annonces n'est pas actionnable
  - Toujours contextualiser par rapport au niveau national
  - Alertes "critical" → signaler en premier
  - Croissance > 20% en un trimestre = alerte bulle immobilière potentielle

Langue : français. Réponses orientées insights et décisions.
"""


# ══════════════════════════════════════════════════════════════════════════════
# FACTORY + INTERFACE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

def create_territorial_agent(
    verbose:        bool  = True,
    temperature:    float = LLM_TEMPERATURE,
    max_iterations: int   = 8,
) -> AgentExecutor:
    """Crée l'AgentExecutor du Territorial Agent."""
    llm = ChatOpenAI(
        model=LLM_MODEL, temperature=temperature,
        api_key=OPENAI_API_KEY, max_tokens=2000,
    )
    tools = [
        analyze_time_series,
        analyze_spatial_distribution,
        detect_zones,
        get_zone_detail,
        generate_full_report,
    ]
    prompt = ChatPromptTemplate.from_messages([
        ("system",      TERRITORIAL_SYSTEM_PROMPT),
        ("human",       "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, tools=tools, verbose=verbose,
        handle_parsing_errors=True,
        max_iterations=max_iterations,
        return_intermediate_steps=True,
    )


class TerritorialAgent:
    """Interface principale du Territorial Agent — appelée par l'Orchestrateur."""

    def __init__(self, verbose: bool = False, temperature: float = LLM_TEMPERATURE):
        self.executor = create_territorial_agent(verbose=verbose, temperature=temperature)
        self.name     = "TerritorialAgent"

    def run(self, instruction: str = "Lance l'analyse territoriale complète") -> dict:
        """Exécute une analyse via le LLM orchestrateur."""
        run_id = f"territorial_{uuid.uuid4().hex[:6]}"
        logger.info(f"[TerritorialAgent] run_id={run_id} — '{instruction[:60]}'")
        result = self.executor.invoke({"input": instruction})
        return {
            "agent":  self.name,
            "run_id": run_id,
            "output": result.get("output", ""),
            "steps":  len(result.get("intermediate_steps", [])),
        }

    def run_full_analysis(self) -> dict:
        """
        Analyse complète sans LLM orchestrateur (mode direct).
        Utilisé par LangGraph et le scheduler automatique.
        """
        run_id = f"territorial_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"[TerritorialAgent] Analyse complète — run_id={run_id}")

        df     = _load_best_df()
        if df.empty:
            return {"error": "Dataset indisponible", "run_id": run_id}

        df_prep = prepare_temporal_data(df)

        # DSO1
        ts_city = compute_time_series(df_prep, group_by="city", freq="M")
        ts_gov  = compute_time_series(df_prep, group_by="governorate", freq="M")

        # DSO2
        spatial = compute_spatial_aggregation(df_prep)

        # DSO3
        emerging = detect_emerging_zones(df_prep, group_by="city")

        # Rapport JSON
        report = generate_territorial_report(df, run_id=run_id)

        result = {
            "run_id":          run_id,
            "agent":           self.name,
            "time_series": {
                "by_city":        ts_city["summary"],
                "by_governorate": ts_gov["summary"],
            },
            "spatial":         spatial["summary"],
            "emerging":        emerging["summary"],
            "alerts":          emerging["alerts"][:10],   # top 10 alertes
            "json_report":     report.get("json_path"),
            "status":          "success",
        }

        logger.info(
            f"[TerritorialAgent] Analyse terminée — "
            f"{emerging['summary']['n_emerging']} zones émergentes, "
            f"{emerging['summary']['n_alerts']} alertes"
        )
        return result

    def get_zone_analysis(self, zone: str, group_by: str = "city") -> dict:
        """Analyse détaillée d'une zone — appelée depuis le frontend."""
        df      = _load_best_df()
        df_prep = prepare_temporal_data(df)
        col     = group_by if group_by in df_prep.columns else "city"
        sub     = df_prep[df_prep[col].astype(str).str.lower() == zone.lower()]

        if sub.empty:
            return {"error": f"Zone '{zone}' non trouvée"}

        price = sub["price"].dropna()
        ppm2  = sub["price_per_m2"].dropna() if "price_per_m2" in sub.columns else pd.Series()
        ts    = compute_time_series(sub, group_by=col, freq="M")

        return {
            "zone":             zone,
            "n_listings":       int(len(sub)),
            "median_price":     round(float(price.median()), 0) if not price.empty else None,
            "median_ppm2":      round(float(ppm2.median()), 0)  if not ppm2.empty else None,
            "trend":            ts["trends"].get(zone, {}),
            "time_series":      list(ts["series"].values())[0] if ts["series"] else [],
            "property_types":   sub["property_type"].value_counts().head(5).to_dict()
                                if "property_type" in sub.columns else {},
        }
