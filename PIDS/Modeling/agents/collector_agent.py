"""
Estate Mind — Collector Agent v3 FINAL
═══════════════════════════════════════
BO1 100% + au-delà :

  ① MLflow tracking complet
  ② Source Health Monitor
  ③ Fuzzy Dedup (Jaccard + Embeddings)
  ④ Data Lineage
  ⑤ Drift Detection (KS test)
  ⑥ Great Expectations style validation
  ⑦ Embedding-based semantic dedup (OpenAI / TF-IDF fallback)
  ⑧ Active Learning feedback loop
  ⑨ Automated HTML pipeline report
"""
from __future__ import annotations
import json, uuid
from datetime import datetime
from pathlib import Path
import pandas as pd
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from config.settings import (
    LLM_MODEL, LLM_TEMPERATURE, NLP_TEMPERATURE, NLP_BATCH_SIZE,
    OPENAI_API_KEY, PROC_DIR, RAW_CSV_PATH,
    MAX_PAGES_PER_SOURCE, PIPELINE_SCHEDULE_HOURS, get_hyperparams_dict,
)
from tools.cleaning_tools        import run_full_cleaning
from tools.connectors            import ConnectorRegistry, CSVConnector
from tools.nlp_cleaner           import run_nlp_enrichment, NLP_EXTRACTION_PROMPT
from tools.fuzzy_dedup           import run_fuzzy_dedup, DEFAULT_SIMILARITY_THRESHOLD
from tools.embedding_dedup       import run_embedding_dedup
from tools.lineage_tracker       import LineageTracker
from tools.source_health_monitor import SourceHealthMonitor
from tools.drift_detector        import DriftDetector
from tools.mlflow_tracker        import MLflowTracker
from tools.data_validator        import DataValidator
from tools.pipeline_reporter     import PipelineReporter
from tools.active_learning       import FewShotBuilder
from db.postgres_manager         import PostgresManager


def _read_csv_robust(csv_path: str) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    attempts  = [
        {"sep": None, "engine": "python", "on_bad_lines": "skip"},
        {"sep": ",",  "engine": "python", "on_bad_lines": "skip"},
        {"sep": ";",  "engine": "python", "on_bad_lines": "skip"},
    ]
    for encoding in encodings:
        for params in attempts:
            try:
                df = pd.read_csv(csv_path, quotechar='"', encoding=encoding,
                                 encoding_errors="replace", **params)
                if len(df.columns) > 1:
                    logger.info(f"[CollectorAgent] {len(df)} lignes ({encoding})")
                    return df
            except Exception:
                pass
    raise RuntimeError(f"Impossible de lire {csv_path}")


def _compute_quality(df: pd.DataFrame) -> dict:
    valid_price   = (df["price"] > 0).mean()   if "price"   in df.columns else 0
    valid_surface = (df["surface"] > 0).mean() if "surface" in df.columns else 0
    validity      = round((valid_price + valid_surface) / 2 * 100, 1)
    key_cols      = [c for c in ["price","surface","city","property_type"] if c in df.columns]
    completeness  = round(df[key_cols].notna().mean().mean() * 100, 1) if key_cols else 0
    expected      = ["price","surface","rooms","property_type","city","governorate","description","url"]
    present       = sum(1 for c in expected if c in df.columns and df[c].notna().any())
    relevance     = round(present / len(expected) * 100, 1)
    nb_gov        = df["governorate"].nunique() if "governorate" in df.columns else 0
    coverage      = min(round(nb_gov / 24 * 100, 1), 100.0)
    global_score  = round((validity + completeness + relevance + coverage) / 4, 1)
    return {
        "validity": validity, "completeness": completeness,
        "relevance": relevance, "coverage": coverage,
        "global_quality_score": global_score,
        "quality_label": ("Excellent" if global_score >= 85 else "Bon"
                          if global_score >= 70 else "Moyen" if global_score >= 55 else "Insuffisant"),
        "total_listings": len(df),
    }


# ── Few-shot prompt enrichi avec Active Learning ─────────────────────────────

COLLECTOR_SYSTEM_PROMPT = """Tu es le Collector Agent v3 FINAL d'Estate Mind, plateforme PropTech tunisienne.

OUTILS :
  1. check_sources_health  → santé des scrapers avant ingestion
  2. ingest_all_sources    → ingestion multi-sources + fuzzy + embedding dedup
  3. clean_and_enrich      → nettoyage + NLP (avec corrections utilisateurs) + lineage
  4. detect_drift          → test KS sur les distributions
  5. validate_data         → Great Expectations style : 14 règles métier
  6. save_to_postgres      → upsert cloud sans redondance
  7. generate_report       → rapport HTML complet auto-généré

ORDRE : check_sources_health → ingest_all_sources → clean_and_enrich
        → detect_drift → validate_data → save_to_postgres → generate_report

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXEMPLES FEW-SHOT (cas réels tunisiens)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXEMPLE 1 — Pipeline parfait
Résultat attendu :
  Sources : 4/4 saines | Annonces : 1203→891 | NLP : 134 enrichies
  Validation : 14/14 règles passées | Drift : aucun | Qualité : 88/100
  Rapport HTML généré → data/reports/pipeline_20260409_103022.html

EXEMPLE 2 — Drift + validation échouée
Résultat attendu :
  Drift détecté sur price_per_m2 (shift +35%, KS p=0.01)
  Validation : 12/14 (url_unique échouée = doublons résiduels)
  → Pipeline en statut WARN, alertes dans le rapport HTML
  → Recommandation : vérifier scraper Tecnocasa

EXEMPLE 3 — Active Learning actif
Résultat attendu :
  3 corrections utilisateurs injectées dans le prompt NLP
  Champ le plus corrigé : 'property_type'
  → Le LLM extrait mieux duplex→villa et local commercial→bureau_local

RÈGLES :
  - validate_data AVANT save_to_postgres (ne pas sauvegarder du mauvais data)
  - generate_report TOUJOURS en dernier (résumé complet)
  - Si validation critique échoue → sauvegarder quand même mais alerter fort
  - Active Learning : log le nb d'exemples injectés

Langue : français. Métriques précises.
"""


@tool
def check_sources_health(max_pages: int = 1) -> str:
    """Vérifie la santé de toutes les sources avant ingestion."""
    registry = ConnectorRegistry(max_pages=max_pages)
    monitor  = SourceHealthMonitor()
    report   = monitor.check_all(registry._connectors, run_id="health_check")
    logger.info(monitor.format_report(report))
    return json.dumps(report.to_dict(), ensure_ascii=False, default=str)

@tool
def ingest_all_sources(max_pages: int = MAX_PAGES_PER_SOURCE, mode: str = "update",
                        use_embeddings: bool = False) -> str:
    """
    Ingestion multi-sources avec double déduplication :
    1. Fuzzy dedup (Jaccard) — rapide
    2. Embedding dedup (OpenAI/TF-IDF) — sémantique, optionnel
    """
    registry = ConnectorRegistry(mode=mode, max_pages=max_pages)
    df       = registry.ingest_all()
    n0 = len(df)
    df = run_fuzzy_dedup(df, threshold=DEFAULT_SIMILARITY_THRESHOLD)
    n1 = len(df)
    n2 = n1
    if use_embeddings:
        df = run_embedding_dedup(df)
        n2 = len(df)
    raw_path = str(Path(PROC_DIR) / "raw_combined.csv")
    Path(PROC_DIR).mkdir(parents=True, exist_ok=True)
    df.to_csv(raw_path, index=False)
    return json.dumps({
        "rows_raw": n0, "after_fuzzy": n1, "after_embedding": n2,
        "total_dups": n0 - n2, "sources": registry.active_sources,
        "output_path": raw_path,
    })

@tool
def clean_and_enrich(csv_path: str = RAW_CSV_PATH, nlp_enrich: bool = True,
                     nlp_temperature: float = NLP_TEMPERATURE,
                     nlp_batch_size: int = NLP_BATCH_SIZE) -> str:
    """
    Nettoyage + NLP enriched par Active Learning + lineage.
    Le prompt NLP est automatiquement enrichi avec les corrections utilisateurs.
    """
    df_raw  = _read_csv_robust(csv_path)
    rows_in = len(df_raw)
    lineage = LineageTracker()
    df_raw  = lineage.init_lineage(df_raw)
    df_clean = run_full_cleaning(df_raw)
    df_clean = lineage.add_cleaning_step(df_clean, rows_in, len(df_clean))
    nlp_count = 0
    al_shots  = 0
    if nlp_enrich:
        # Active Learning : enrichit le prompt avec les corrections utilisateurs
        builder   = FewShotBuilder()
        al_shots  = len(builder.store.get_corrections())
        df_clean  = run_nlp_enrichment(df_clean, temperature=nlp_temperature,
                                       batch_size=nlp_batch_size)
        nlp_count = int(df_clean.get("nlp_enriched", pd.Series()).sum())
        df_clean  = lineage.add_nlp_step(df_clean, ["price","surface","rooms","property_type"],
                                          nlp_count, nlp_temperature)
    output_path = str(Path(PROC_DIR) / "listings_clean.csv")
    df_clean.to_csv(output_path, index=False)
    return json.dumps({"rows_in": rows_in, "rows_out": len(df_clean),
                        "nlp_enriched": nlp_count, "active_learning_shots": al_shots,
                        "output_path": output_path})

@tool
def detect_drift(cleaned_csv_path: str, run_id: str = "latest") -> str:
    """Détecte le data drift via test KS (Kolmogorov-Smirnov)."""
    df = pd.read_csv(cleaned_csv_path)
    detector = DriftDetector()
    report   = detector.detect(df, run_id=run_id, update_baseline_if_ok=True)
    logger.info(detector.format_report(report))
    return json.dumps(report.to_dict(), ensure_ascii=False, default=str)

@tool
def validate_data(cleaned_csv_path: str, run_id: str = "unknown") -> str:
    """
    Valide les données selon 14 règles métier tunisiennes (Great Expectations style).
    Génère un rapport HTML de validation dans data/reports/.
    """
    df        = pd.read_csv(cleaned_csv_path)
    validator = DataValidator()
    report    = validator.validate(df, run_id=run_id)
    html_path = validator.generate_html_report(report, df)
    validator.log_to_mlflow(report)
    return json.dumps({**report.to_dict(), "html_report": str(html_path)},
                       ensure_ascii=False, default=str)

@tool
def save_to_postgres(cleaned_csv_path: str, pipeline_version: str = "v3") -> str:
    """Sauvegarde dans PostgreSQL sans redondance (upsert)."""
    df = pd.read_csv(cleaned_csv_path)
    pg = PostgresManager(); pg.ensure_tables()
    return json.dumps(pg.upsert_listings(df, pipeline_version=pipeline_version))

@tool
def generate_report(run_result_json: str, cleaned_csv_path: str) -> str:
    """Génère le rapport HTML complet du pipeline."""
    run_result = json.loads(run_result_json) if isinstance(run_result_json, str) else run_result_json
    df = pd.read_csv(cleaned_csv_path)
    reporter = PipelineReporter()
    path     = reporter.generate(run_result, df)
    return json.dumps({"report_path": str(path), "status": "generated"})


def create_collector_agent(verbose=True, temperature=LLM_TEMPERATURE,
                            max_iterations=14) -> AgentExecutor:
    llm   = ChatOpenAI(model=LLM_MODEL, temperature=temperature,
                       api_key=OPENAI_API_KEY, max_tokens=2000)
    tools = [check_sources_health, ingest_all_sources, clean_and_enrich,
             detect_drift, validate_data, save_to_postgres, generate_report]
    prompt = ChatPromptTemplate.from_messages([
        ("system", COLLECTOR_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=verbose,
                         handle_parsing_errors=True, max_iterations=max_iterations,
                         return_intermediate_steps=True)


class CollectorAgent:
    def __init__(self, verbose=False, temperature=LLM_TEMPERATURE,
                 nlp_temperature=NLP_TEMPERATURE, nlp_batch_size=NLP_BATCH_SIZE,
                 max_pages=MAX_PAGES_PER_SOURCE):
        self.executor        = create_collector_agent(verbose=verbose, temperature=temperature)
        self.nlp_temperature = nlp_temperature
        self.nlp_batch_size  = nlp_batch_size
        self.max_pages       = max_pages
        self.name            = "CollectorAgent"

    def run_cleaning_only(self, csv_path=RAW_CSV_PATH) -> pd.DataFrame:
        df_raw   = _read_csv_robust(csv_path)
        df_clean = run_full_cleaning(df_raw)
        output   = str(Path(PROC_DIR) / "listings_clean.csv")
        Path(PROC_DIR).mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(output, index=False)
        return df_clean

    def run_full_pipeline(self, csv_path=RAW_CSV_PATH, mode="update",
                          nlp_enrich=True, save_pg=True,
                          use_embedding_dedup=False) -> dict:
        """Pipeline v3 FINAL — 9 composants orchestrés."""
        run_id  = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        tracker = MLflowTracker()
        tracker.start_run(run_name=f"collector_{run_id}", config=get_hyperparams_dict(),
                          tags={"mode": mode, "version": "v3_final"})
        t0 = datetime.utcnow()
        logger.info(f"[CollectorAgent] Pipeline FINAL — run_id={run_id}")

        # 1. Health check
        registry = ConnectorRegistry(mode=mode, max_pages=self.max_pages)
        monitor  = SourceHealthMonitor()
        health   = monitor.check_all(registry._connectors, run_id=run_id)
        tracker.log_source_health(health.to_dict())
        if health.fallback_needed:
            registry._connectors = [CSVConnector(csv_path)]

        # 2. Ingestion
        df_raw  = registry.ingest_all()
        rows_in = len(df_raw)

        # 3. Lineage init
        lineage = LineageTracker(pipeline_version="v3_final")
        df_raw  = lineage.init_lineage(df_raw)

        # 4. Fuzzy dedup (Jaccard)
        n0 = rows_in
        df_raw = run_fuzzy_dedup(df_raw, threshold=DEFAULT_SIMILARITY_THRESHOLD)
        df_raw = lineage.add_fuzzy_step(df_raw, n0 - len(df_raw), DEFAULT_SIMILARITY_THRESHOLD)

        # 5. Embedding dedup (sémantique) — optionnel
        n1 = len(df_raw)
        if use_embedding_dedup:
            df_raw = run_embedding_dedup(df_raw)
        n2 = len(df_raw)
        tracker.log_ingestion(rows_in, n2, registry.active_sources, n0 - n2)

        # 6. Nettoyage
        df_clean = run_full_cleaning(df_raw)
        df_clean = lineage.add_cleaning_step(df_clean, n2, len(df_clean))

        # 7. NLP + Active Learning
        nlp_count = 0
        al_shots  = 0
        if nlp_enrich:
            builder  = FewShotBuilder()
            al_shots = len(builder.store.get_corrections())
            logger.info(f"[ActiveLearning] {al_shots} correction(s) disponible(s) — {builder.get_stats_summary()}")
            df_clean  = run_nlp_enrichment(df_clean, temperature=self.nlp_temperature,
                                           batch_size=self.nlp_batch_size)
            nlp_count = int(df_clean.get("nlp_enriched", pd.Series()).sum())
            df_clean  = lineage.add_nlp_step(df_clean, ["price","surface","rooms","property_type"],
                                              nlp_count, self.nlp_temperature)
            tracker.log_nlp_enrichment(nlp_count, len(df_clean), self.nlp_temperature)

        # 8. Save CSV
        clean_path = str(Path(PROC_DIR) / "listings_clean.csv")
        Path(PROC_DIR).mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(clean_path, index=False)

        # 9. Drift detection
        detector     = DriftDetector()
        drift_report = detector.detect(df_clean, run_id=run_id, update_baseline_if_ok=True)
        tracker.log_drift(drift_report.to_dict())

        # 10. Great Expectations validation
        validator   = DataValidator()
        val_report  = validator.validate(df_clean, run_id=run_id)
        validator.generate_html_report(val_report, df_clean)
        validator.log_to_mlflow(val_report)

        # 11. Quality
        quality = _compute_quality(df_clean)
        tracker.log_quality(quality)

        # 12. PostgreSQL
        upsert_stats = {"inserted": 0, "updated": 0, "skipped": 0}
        if save_pg:
            try:
                pg = PostgresManager(); pg.ensure_tables()
                upsert_stats = pg.upsert_listings(df_clean, pipeline_version="v3_final")
                df_clean = lineage.add_postgres_step(df_clean, **upsert_stats)
                df_clean.to_csv(clean_path, index=False)
                pg.log_pipeline_run(
                    run_id=run_id, rows_in=rows_in, rows_out=len(df_clean),
                    upsert_stats=upsert_stats,
                    avg_trust=float(df_clean.get("trust_score", pd.Series([0.5])).mean()),
                    suspect_count=int((df_clean.get("trust_score", pd.Series()) < 0.5).sum()),
                    high_legal=int((df_clean.get("legal_risk_score", pd.Series()) >= 0.6).sum()),
                    sources=registry.active_sources, config=get_hyperparams_dict(),
                )
            except Exception as e:
                logger.error(f"[CollectorAgent] PostgreSQL: {e}")

        # 13. Artefacts MLflow
        tracker.log_csv_artifact(clean_path)
        tracker.log_price_distribution_chart(df_clean)
        elapsed = round((datetime.utcnow() - t0).total_seconds(), 2)
        tracker.end_run("FAILED" if drift_report.action_required else "FINISHED")

        result = {
            "run_id": run_id, "rows_in": rows_in, "rows_out": len(df_clean),
            "fuzzy_dups": n0 - n1, "embedding_dups": n1 - n2,
            "nlp_enriched": nlp_count, "active_learning_shots": al_shots,
            "upsert": upsert_stats, "quality": quality,
            "drift": {"global_drift": drift_report.global_drift,
                      "n_drifted": drift_report.n_drifted_columns,
                      "action_required": drift_report.action_required,
                      "recommendation": drift_report.recommendation},
            "validation": {"score": val_report.score,
                           "n_passed": val_report.n_passed,
                           "n_total": val_report.n_total,
                           "overall_passed": val_report.overall_passed},
            "health": {"n_healthy": health.n_healthy, "n_critical": health.n_critical,
                       "fallback": health.fallback_needed},
            "lineage": lineage.get_summary_stats(df_clean),
            "elapsed_s": elapsed, "output_path": clean_path,
        }

        # 14. HTML pipeline report (le dernier, il résume tout)
        reporter  = PipelineReporter()
        html_path = reporter.generate(result, df_clean, val_report, drift_report, health)
        result["html_report"] = str(html_path)

        logger.info(
            f"[CollectorAgent] Pipeline FINAL terminé en {elapsed}s\n"
            f"  Annonces : {rows_in} → {len(df_clean)}\n"
            f"  Qualité  : {quality['global_quality_score']}/100 ({quality['quality_label']})\n"
            f"  Drift    : {drift_report.n_drifted_columns} colonne(s)\n"
            f"  Valid.   : {val_report.n_passed}/{val_report.n_total}\n"
            f"  Rapport  : {html_path}"
        )
        return result

    def run(self, csv_path=RAW_CSV_PATH) -> dict:
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        result = self.executor.invoke({"input": (
            f"Lance le pipeline FINAL sur '{csv_path}'. "
            "Vérifie les sources, ingère, nettoie avec Active Learning NLP, "
            "détecte le drift, valide les données, sauvegarde, génère le rapport."
        )})
        return {"agent": self.name, "run_id": run_id, "output": result.get("output", "")}


def start_scheduled_pipeline(hours=PIPELINE_SCHEDULE_HOURS, nlp_enrich=True, save_pg=True):
    if hours == 0: return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval    import IntervalTrigger
    except ImportError:
        logger.error("[Scheduler] pip install apscheduler"); return
    agent = CollectorAgent(verbose=False)
    def _job():
        try:
            r = agent.run_full_pipeline(nlp_enrich=nlp_enrich, save_pg=save_pg)
            logger.info(f"[Scheduler] OK — {r['rows_out']} ann. | "
                        f"qualité={r['quality']['global_quality_score']} | "
                        f"rapport={r.get('html_report')}")
        except Exception as e:
            logger.error(f"[Scheduler] {e}")
    scheduler = BackgroundScheduler()
    scheduler.add_job(_job, IntervalTrigger(hours=hours), id="estate_mind_pipeline",
                      replace_existing=True)
    scheduler.start()
    logger.info(f"[Scheduler] Démarré — toutes les {hours}h")
    _job()
    return scheduler


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    if mode == "pipeline":
        agent  = CollectorAgent(verbose=False)
        result = agent.run_full_pipeline()
        print(f"\nPipeline FINAL terminé:")
        print(f"  Annonces  : {result['rows_in']} → {result['rows_out']}")
        print(f"  Qualité   : {result['quality']['global_quality_score']}/100")
        print(f"  Validation: {result['validation']['n_passed']}/{result['validation']['n_total']}")
        print(f"  Drift     : {result['drift']['n_drifted']} colonne(s)")
        print(f"  Rapport   : {result.get('html_report')}")
    elif mode == "schedule":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else PIPELINE_SCHEDULE_HOURS
        import time
        s = start_scheduled_pipeline(hours=hours)
        try:
            while True: time.sleep(60)
        except KeyboardInterrupt:
            s.shutdown()
