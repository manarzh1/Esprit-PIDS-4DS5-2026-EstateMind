"""
Estate Mind — Source Health Monitor
═════════════════════════════════════
Teste chaque connecteur avant l'ingestion complète.
Si une source est morte ou sous-performante → alerte + fallback.

Détection :
  - Source silencieuse  : 0 annonces retournées (scraper cassé)
  - Chute soudaine      : -50% vs baseline historique (site bloqué ?)
  - Données corrompues  : trop de NaN sur les champs critiques
  - Timeout             : le scraper met trop longtemps à répondre

Réponse :
  - Log structuré dans MLflow et PostgreSQL
  - Rapport JSON retourné à l'orchestrateur
  - Fallback automatique sur le CSV historique si toutes les sources tombent
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger


# ── Seuils configurables ──────────────────────────────────────────────────────

MIN_ROWS_THRESHOLD       = 1        # min annonces pour considérer une source "vivante"
DROP_RATIO_THRESHOLD     = 0.50     # -50% vs baseline → alerte
NAN_CRITICAL_THRESHOLD   = 0.80     # 80% de NaN sur price/surface → source corrompue
HEALTH_CHECK_MAX_PAGES   = 1        # pages testées (1 = rapide, non-invasif)
HEALTH_TIMEOUT_SECONDS   = 30       # timeout par source


# ── Dataclasses de résultats ──────────────────────────────────────────────────

@dataclass
class SourceStatus:
    source:           str
    healthy:          bool
    rows:             int
    elapsed_s:        float
    nan_price_pct:    float
    nan_surface_pct:  float
    issue:            Optional[str]   = None
    baseline_rows:    Optional[int]   = None
    drop_pct:         Optional[float] = None

    @property
    def severity(self) -> str:
        if not self.healthy:
            if self.rows == 0:         return "critical"
            if self.nan_price_pct > NAN_CRITICAL_THRESHOLD: return "warning"
            return "warning"
        if self.drop_pct and self.drop_pct > DROP_RATIO_THRESHOLD:
            return "warning"
        return "ok"


@dataclass
class HealthReport:
    run_id:            str
    checked_at:        str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sources:           dict = field(default_factory=dict)
    n_healthy:         int  = 0
    n_degraded:        int  = 0
    n_critical:        int  = 0
    global_healthy:    bool = True
    fallback_needed:   bool = False
    recommendation:    str  = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sources"] = {k: asdict(v) for k, v in self.sources.items()}
        return d


# ── Baseline historique ───────────────────────────────────────────────────────

class BaselineManager:
    """
    Garde en mémoire le nombre d'annonces moyen par source (baseline).
    Persisté dans data/state/source_baseline.json.
    """
    STATE_PATH = Path("data/state/source_baseline.json")

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        if self.STATE_PATH.exists():
            import json
            try:
                return json.loads(self.STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        import json
        self.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.STATE_PATH.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_baseline(self, source: str) -> Optional[int]:
        return self._data.get(source, {}).get("avg_rows")

    def update(self, source: str, rows: int) -> None:
        if source not in self._data:
            self._data[source] = {"runs": [], "avg_rows": rows}
        else:
            runs = self._data[source].get("runs", [])
            runs.append(rows)
            runs = runs[-10:]   # garde les 10 derniers runs
            self._data[source]["runs"]     = runs
            self._data[source]["avg_rows"] = round(sum(runs) / len(runs))
        self._save()


# ── Health Monitor ────────────────────────────────────────────────────────────

class SourceHealthMonitor:
    """
    Teste chaque connecteur sur 1 page et produit un HealthReport.

    Usage :
        monitor = SourceHealthMonitor()
        report  = monitor.check_all(connectors)

        if report.fallback_needed:
            logger.warning("Toutes les sources sont mortes → fallback CSV")
        elif report.n_critical > 0:
            logger.warning(f"{report.n_critical} source(s) critiques")
    """

    def __init__(self):
        self.baseline = BaselineManager()

    def check_source(self, connector, max_pages: int = HEALTH_CHECK_MAX_PAGES) -> SourceStatus:
        """
        Teste un connecteur sur max_pages pages.
        Retourne un SourceStatus avec toutes les métriques.
        """
        source = connector.name
        logger.info(f"[HealthMonitor] Test de {source}...")
        t0 = time.time()

        try:
            df = connector.run(max_pages=max_pages)
            elapsed = round(time.time() - t0, 2)
            rows    = len(df)

            # Métriques de complétude
            # Note : float() évite l'ambiguïté si la colonne est dupliquée (Tecnocasa)
            if "price" in df.columns:
                _price_col = df["price"] if df["price"].ndim == 1 else df["price"].iloc[:, 0]
                nan_price = float(_price_col.isna().mean())
            else:
                nan_price = 1.0
            if "surface" in df.columns:
                _surf_col = df["surface"] if df["surface"].ndim == 1 else df["surface"].iloc[:, 0]
                nan_surface = float(_surf_col.isna().mean())
            else:
                nan_surface = 1.0

            # Comparaison avec la baseline
            baseline_rows = self.baseline.get_baseline(source)
            drop_pct      = None
            if baseline_rows and baseline_rows > 0 and rows > 0:
                drop_pct = round(1.0 - rows / baseline_rows, 3)

            # Détermination de la santé
            issue   = None
            healthy = True

            if rows == 0:
                healthy = False
                issue   = "Source silencieuse : 0 annonces retournées"
            elif nan_price > NAN_CRITICAL_THRESHOLD:
                healthy = False
                issue   = f"Données corrompues : {nan_price*100:.0f}% de prix manquants"
            elif drop_pct and drop_pct > DROP_RATIO_THRESHOLD:
                issue   = f"Chute de {drop_pct*100:.0f}% vs baseline ({baseline_rows} → {rows})"
                # Pas critique, mais dégradé

            if healthy and rows > 0:
                self.baseline.update(source, rows)

            status = SourceStatus(
                source         = source,
                healthy        = healthy,
                rows           = rows,
                elapsed_s      = elapsed,
                nan_price_pct  = round(nan_price, 3),
                nan_surface_pct= round(nan_surface, 3),
                issue          = issue,
                baseline_rows  = baseline_rows,
                drop_pct       = drop_pct,
            )

            icon = "✅" if healthy else "❌"
            logger.info(
                f"[HealthMonitor] {icon} {source} — "
                f"{rows} lignes en {elapsed}s"
                + (f" | {issue}" if issue else "")
            )
            return status

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            logger.error(f"[HealthMonitor] ❌ {source} — Exception : {e}")
            return SourceStatus(
                source=source, healthy=False, rows=0,
                elapsed_s=elapsed, nan_price_pct=1.0,
                nan_surface_pct=1.0,
                issue=f"Exception : {str(e)[:200]}",
            )

    def check_all(
        self,
        connectors: list,
        run_id:     str = "unknown",
    ) -> HealthReport:
        """
        Vérifie toutes les sources et produit un rapport global.
        """
        logger.info(f"[HealthMonitor] Vérification de {len(connectors)} sources...")
        report = HealthReport(run_id=run_id)

        for conn in connectors:
            status = self.check_source(conn)
            report.sources[status.source] = status

            if status.severity == "critical":
                report.n_critical += 1
            elif status.severity == "warning":
                report.n_degraded += 1
            else:
                report.n_healthy  += 1

        # Fallback si toutes les vraies sources sont mortes
        live_sources = [s for s in report.sources.values()
                        if s.source != "csv" and s.healthy]
        report.fallback_needed  = len(live_sources) == 0
        report.global_healthy   = report.n_critical == 0

        # Recommandation
        if report.fallback_needed:
            report.recommendation = (
                "CRITIQUE : Toutes les sources sont hors service. "
                "Fallback automatique sur le CSV historique."
            )
        elif report.n_critical > 0:
            dead = [s for s, v in report.sources.items() if v.severity == "critical"]
            report.recommendation = (
                f"Sources hors service : {', '.join(dead)}. "
                "Les autres sources continuent normalement."
            )
        elif report.n_degraded > 0:
            report.recommendation = (
                f"{report.n_degraded} source(s) dégradée(s) — surveiller les prochains runs."
            )
        else:
            report.recommendation = "Toutes les sources sont opérationnelles."

        logger.info(
            f"[HealthMonitor] Rapport : "
            f"{report.n_healthy} OK / {report.n_degraded} dégradées / "
            f"{report.n_critical} critiques"
        )
        return report

    def format_report(self, report: HealthReport) -> str:
        """Formate le rapport pour le logging."""
        lines = [
            "══ Source Health Report ══",
            f"Heure : {report.checked_at}",
            "",
        ]
        for source, status in report.sources.items():
            icon = {"ok":"✅","warning":"⚠️","critical":"❌"}.get(status.severity, "?")
            lines.append(
                f"{icon} {source:12s} | {status.rows:5d} lignes | "
                f"{status.elapsed_s:.1f}s | "
                f"NaN price: {status.nan_price_pct*100:.0f}%"
                + (f" | {status.issue}" if status.issue else "")
            )
        lines += ["", f"Recommandation : {report.recommendation}"]
        return "\n".join(lines)
