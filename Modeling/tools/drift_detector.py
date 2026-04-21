"""
Estate Mind — Data Drift Detector
════════════════════════════════════
Détecte automatiquement si la distribution des données a dérivé
par rapport à une baseline de référence.

Cas d'usage :
  - Scraper retourne des données corrompues (ex: tous les prix à 0)
  - Choc du marché immobilier (hausse/baisse soudaine des prix)
  - Zone géographique nouvellement couverte (shift de la distribution)
  - Bug dans le nettoyage (surface_m2 en cm² par erreur)

Test utilisé : Kolmogorov-Smirnov (KS test)
  - Non-paramétrique → pas d'hypothèse sur la forme de la distribution
  - Sensible aux shifts ET aux changements de forme
  - p-value < 0.05 → drift statistiquement significatif

Colonnes surveillées :
  price, surface, price_per_m2, trust_score, legal_risk_score, rooms
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("[DriftDetector] scipy non installé — pip install scipy")


# ── Configuration ─────────────────────────────────────────────────────────────

DRIFT_COLUMNS = ["price", "surface", "price_per_m2", "trust_score", "rooms"]
KS_PVALUE_THRESHOLD  = 0.05     # p < 0.05 → drift détecté
MEAN_SHIFT_THRESHOLD = 0.20     # shift de +/-20% de la moyenne → alerte
MIN_SAMPLE_SIZE      = 30       # min lignes pour que le test soit valide
BASELINE_PATH        = Path("data/state/drift_baseline.json")


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ColumnDrift:
    column:        str
    drifted:       bool
    ks_statistic:  Optional[float]
    p_value:       Optional[float]
    mean_baseline: Optional[float]
    mean_current:  Optional[float]
    mean_shift_pct:Optional[float]
    std_baseline:  Optional[float]
    std_current:   Optional[float]
    n_baseline:    int
    n_current:     int
    reason:        Optional[str] = None

    @property
    def severity(self) -> str:
        if not self.drifted:            return "ok"
        if self.mean_shift_pct and abs(self.mean_shift_pct) > 0.40:
            return "critical"
        return "warning"


@dataclass
class DriftReport:
    run_id:              str
    checked_at:          str = field(default_factory=lambda: datetime.utcnow().isoformat())
    columns:             dict = field(default_factory=dict)
    n_drifted_columns:   int  = 0
    global_drift:        bool = False
    baseline_run_id:     Optional[str] = None
    recommendation:      str  = ""
    action_required:     bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["columns"] = {k: asdict(v) for k, v in self.columns.items()}
        return d


# ── Gestion de la baseline ────────────────────────────────────────────────────

class BaselineStore:
    """Persiste la baseline de référence pour la comparaison de drift."""

    def __init__(self, path: Path = BASELINE_PATH):
        self.path = path

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def exists(self) -> bool:
        return self.path.exists() and bool(self._load())

    def save_baseline(self, df: pd.DataFrame, run_id: str) -> None:
        """Sauvegarde les statistiques de la distribution actuelle comme baseline."""
        baseline = {"run_id": run_id, "saved_at": datetime.utcnow().isoformat(), "columns": {}}
        for col in DRIFT_COLUMNS:
            if col not in df.columns:
                continue
            series = df[col].dropna()
            if len(series) < MIN_SAMPLE_SIZE:
                continue
            baseline["columns"][col] = {
                "mean":       float(series.mean()),
                "std":        float(series.std()),
                "median":     float(series.median()),
                "q25":        float(series.quantile(0.25)),
                "q75":        float(series.quantile(0.75)),
                "min":        float(series.min()),
                "max":        float(series.max()),
                "n":          int(len(series)),
                # Stocke un échantillon pour le test KS
                "sample":     series.sample(min(500, len(series)), random_state=42).tolist(),
            }
        self._save(baseline)
        logger.info(f"[DriftDetector] Baseline sauvegardée : run_id={run_id}, "
                    f"{len(baseline['columns'])} colonnes")

    def load_baseline(self) -> Optional[dict]:
        data = self._load()
        return data if data else None


# ── Détecteur principal ───────────────────────────────────────────────────────

class DriftDetector:
    """
    Détecte le data drift sur le dataset courant vs une baseline.

    Si aucune baseline n'existe → en crée une automatiquement.
    Si la baseline existe → compare et produit un rapport.
    """

    def __init__(self):
        self.store = BaselineStore()

    def _ks_test(
        self,
        baseline_sample: list,
        current_series:  pd.Series,
    ) -> tuple[float, float]:
        """Test KS entre la baseline et la distribution courante."""
        if not SCIPY_AVAILABLE:
            return 0.0, 1.0   # pas de drift détecté si scipy absent

        ref = np.array(baseline_sample)
        cur = current_series.dropna().values

        if len(ref) < MIN_SAMPLE_SIZE or len(cur) < MIN_SAMPLE_SIZE:
            return 0.0, 1.0

        try:
            stat, pvalue = scipy_stats.ks_2samp(ref, cur)
            return float(stat), float(pvalue)
        except Exception:
            return 0.0, 1.0

    def detect(
        self,
        df:     pd.DataFrame,
        run_id: str,
        update_baseline_if_ok: bool = False,
    ) -> DriftReport:
        """
        Compare le DataFrame courant à la baseline.

        Args:
            df                    : dataset nettoyé du run courant
            run_id                : identifiant du run (pour le rapport)
            update_baseline_if_ok : met à jour la baseline si aucun drift détecté

        Returns:
            DriftReport avec le détail par colonne
        """
        report = DriftReport(run_id=run_id)

        # ── Pas de baseline → on en crée une ──────────────────────────────────
        if not self.store.exists():
            logger.info("[DriftDetector] Aucune baseline — création initiale")
            self.store.save_baseline(df, run_id)
            report.recommendation = (
                "Baseline créée pour ce run. "
                "Le drift sera détecté à partir du prochain run."
            )
            report.global_drift = False
            return report

        baseline = self.store.load_baseline()
        report.baseline_run_id = baseline.get("run_id", "?")
        logger.info(f"[DriftDetector] Comparaison vs baseline run_id={report.baseline_run_id}")

        # ── Analyse colonne par colonne ────────────────────────────────────────
        n_drifted = 0

        for col in DRIFT_COLUMNS:
            if col not in df.columns:
                continue
            col_data = df[col].dropna()
            if len(col_data) < MIN_SAMPLE_SIZE:
                continue

            baseline_col = baseline.get("columns", {}).get(col)
            if not baseline_col:
                continue

            # Test KS
            ks_stat, p_val = self._ks_test(
                baseline_col.get("sample", []),
                col_data,
            )

            # Shift de la moyenne
            mean_base = baseline_col.get("mean", 0)
            mean_cur  = float(col_data.mean())
            shift_pct = (mean_cur - mean_base) / max(abs(mean_base), 1e-9)

            # Drift détecté si KS p-value < seuil OU shift important
            drifted = (p_val < KS_PVALUE_THRESHOLD) or (abs(shift_pct) > MEAN_SHIFT_THRESHOLD)

            reason = None
            if drifted:
                n_drifted += 1
                if p_val < KS_PVALUE_THRESHOLD:
                    reason = f"Distribution modifiée (KS p={p_val:.4f})"
                if abs(shift_pct) > MEAN_SHIFT_THRESHOLD:
                    direction = "hausse" if shift_pct > 0 else "baisse"
                    reason = (reason or "") + f" | Shift {direction} de {abs(shift_pct)*100:.1f}%"

            report.columns[col] = ColumnDrift(
                column        = col,
                drifted       = drifted,
                ks_statistic  = round(ks_stat, 4),
                p_value       = round(p_val, 4),
                mean_baseline = round(mean_base, 2),
                mean_current  = round(mean_cur, 2),
                mean_shift_pct= round(shift_pct, 3),
                std_baseline  = round(baseline_col.get("std", 0), 2),
                std_current   = round(float(col_data.std()), 2),
                n_baseline    = baseline_col.get("n", 0),
                n_current     = len(col_data),
                reason        = reason,
            )

            if drifted:
                logger.warning(f"[DriftDetector] Drift détecté sur '{col}': {reason}")

        report.n_drifted_columns = n_drifted
        report.global_drift      = n_drifted > 0
        report.action_required   = n_drifted >= 2   # 2+ colonnes = action requise

        # ── Recommandation ─────────────────────────────────────────────────────
        if report.action_required:
            drifted_cols = [c for c, v in report.columns.items() if v.drifted]
            report.recommendation = (
                f"ALERTE : Drift détecté sur {n_drifted} colonne(s) : "
                f"{', '.join(drifted_cols)}. "
                "Vérifier les scrapers et la qualité des données."
            )
        elif report.global_drift:
            report.recommendation = (
                "Légère variation détectée. Surveiller les prochains runs."
            )
        else:
            report.recommendation = (
                "Aucun drift significatif. Distribution stable."
            )
            if update_baseline_if_ok:
                self.store.save_baseline(df, run_id)
                logger.info("[DriftDetector] Baseline mise à jour (pas de drift)")

        logger.info(
            f"[DriftDetector] Résultat : {n_drifted}/{len(report.columns)} colonnes driftées"
        )
        return report

    def format_report(self, report: DriftReport) -> str:
        """Formate le rapport pour le logging."""
        lines = [
            "══ Data Drift Report ══",
            f"Run     : {report.run_id}",
            f"Baseline: {report.baseline_run_id}",
            f"Heure   : {report.checked_at}",
            "",
        ]
        for col, info in report.columns.items():
            icon = "❌" if info.drifted else "✅"
            shift_str = f" | shift={info.mean_shift_pct*100:+.1f}%" if info.mean_shift_pct else ""
            lines.append(
                f"{icon} {col:20s} | KS={info.ks_statistic:.3f} p={info.p_value:.4f}"
                f"{shift_str}"
                + (f"\n   → {info.reason}" if info.reason else "")
            )
        lines += ["", f"Recommandation : {report.recommendation}"]
        return "\n".join(lines)
