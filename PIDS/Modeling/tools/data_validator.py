"""
Estate Mind — Data Validator (Great Expectations style)
═════════════════════════════════════════════════════════
Validation déclarative des données après chaque run pipeline.

Chaque "expectation" est une règle métier tunisienne explicite :
  - Prix entre 1 000 et 10 000 000 TND
  - Surface entre 5 et 5 000 m²
  - Taux de nullité price < 20%
  - city ne doit pas être null sur plus de 5% des lignes
  - property_type doit appartenir au vocabulaire contrôlé
  - Pas de doublons URL
  - Distribution prix/m² cohérente avec le marché tunisien
  - ...

Sortie :
  - ValidationReport (dict) → loggué dans MLflow
  - rapport HTML complet → data/reports/validation_TIMESTAMP.html
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
import numpy as np
from loguru import logger


# ══════════════════════════════════════════════════════════════════════════════
# EXPECTATION — règle unitaire
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Expectation:
    name:        str
    description: str
    column:      Optional[str]
    fn:          Callable[[pd.DataFrame], tuple[bool, str, Any]]
    critical:    bool = False   # Si True → pipeline bloqué si échec

    def evaluate(self, df: pd.DataFrame) -> "ExpectationResult":
        try:
            passed, detail, observed = self.fn(df)
        except Exception as e:
            passed, detail, observed = False, f"Exception : {e}", None
        return ExpectationResult(
            name=self.name, description=self.description,
            column=self.column, passed=passed,
            detail=detail, observed=observed, critical=self.critical,
        )


@dataclass
class ExpectationResult:
    name:        str
    description: str
    column:      Optional[str]
    passed:      bool
    detail:      str
    observed:    Any
    critical:    bool

    @property
    def status(self) -> str:
        return "✅ PASS" if self.passed else ("🔴 FAIL" if self.critical else "⚠️ WARN")


# ══════════════════════════════════════════════════════════════════════════════
# EXPECTATIONS SUITE — toutes les règles métier Estate Mind
# ══════════════════════════════════════════════════════════════════════════════

VALID_PROPERTY_TYPES = {
    "appartement", "villa", "maison", "terrain",
    "bureau_local", "studio", "immeuble", "ferme", "autre"
}

VALID_GOVERNORATES = {
    "Tunis", "Ariana", "Ben Arous", "Manouba", "Nabeul", "Zaghouan",
    "Bizerte", "Béja", "Jendouba", "Le Kef", "Siliana", "Sousse",
    "Monastir", "Mahdia", "Sfax", "Kairouan", "Kasserine", "Sidi Bouzid",
    "Gabès", "Médenine", "Tataouine", "Gafsa", "Tozeur", "Kébili",
}


def build_expectations() -> list[Expectation]:
    """Construit toutes les expectations Estate Mind."""
    return [

        # ── Volume ────────────────────────────────────────────────────────────
        Expectation(
            name="volume_minimum",
            description="Le dataset doit contenir au moins 10 annonces",
            column=None, critical=True,
            fn=lambda df: (
                len(df) >= 10,
                f"{len(df)} annonces",
                len(df),
            )
        ),

        # ── Prix ──────────────────────────────────────────────────────────────
        Expectation(
            name="price_not_null_rate",
            description="Taux de prix non-null < 20%",
            column="price", critical=True,
            fn=lambda df: (
                (null_r := df["price"].isna().mean()) < 0.20,
                f"{null_r*100:.1f}% de prix manquants",
                round(null_r, 3),
            ) if "price" in df.columns else (False, "colonne absente", None)
        ),
        Expectation(
            name="price_in_range",
            description="Prix entre 1 000 et 10 000 000 TND",
            column="price", critical=False,
            fn=lambda df: (
                (
                    pct_ok := (df["price"].dropna().between(1_000, 10_000_000).mean())
                ) >= 0.95,
                f"{pct_ok*100:.1f}% des prix dans la plage valide",
                round(pct_ok, 3),
            ) if "price" in df.columns else (True, "colonne absente", None)
        ),
        Expectation(
            name="price_no_zeros",
            description="Pas de prix à 0 TND",
            column="price", critical=False,
            fn=lambda df: (
                (n_zeros := (df["price"] == 0).sum()) == 0,
                f"{n_zeros} annonces avec prix=0",
                int(n_zeros),
            ) if "price" in df.columns else (True, "colonne absente", None)
        ),

        # ── Surface ───────────────────────────────────────────────────────────
        Expectation(
            name="surface_not_null_rate",
            description="Taux de surface non-null < 30%",
            column="surface", critical=False,
            fn=lambda df: (
                (null_r := df["surface"].isna().mean()) < 0.30,
                f"{null_r*100:.1f}% de surfaces manquantes",
                round(null_r, 3),
            ) if "surface" in df.columns else (False, "colonne absente", None)
        ),
        Expectation(
            name="surface_in_range",
            description="Surface entre 5 et 5 000 m²",
            column="surface", critical=False,
            fn=lambda df: (
                (pct := df["surface"].dropna().between(5, 5000).mean()) >= 0.95,
                f"{pct*100:.1f}% des surfaces dans la plage valide",
                round(pct, 3),
            ) if "surface" in df.columns else (True, "colonne absente", None)
        ),

        # ── Prix/m² ───────────────────────────────────────────────────────────
        Expectation(
            name="price_per_m2_coherent",
            description="Prix/m² médian entre 500 et 8 000 TND (marché tunisien)",
            column="price_per_m2", critical=False,
            fn=lambda df: (
                500 <= (med := float(df["price_per_m2"].dropna().median())) <= 8_000,
                f"Médiane prix/m² = {med:.0f} TND",
                round(med, 0),
            ) if "price_per_m2" in df.columns and df["price_per_m2"].notna().any()
              else (True, "colonne absente ou vide", None)
        ),

        # ── Localisation ──────────────────────────────────────────────────────
        Expectation(
            name="city_not_null_rate",
            description="Taux de ville non-null < 5%",
            column="city", critical=False,
            fn=lambda df: (
                (null_r := df["city"].isna().mean()) < 0.05,
                f"{null_r*100:.1f}% de villes manquantes",
                round(null_r, 3),
            ) if "city" in df.columns else (False, "colonne absente", None)
        ),

        # ── Types de bien ──────────────────────────────────────────────────────
        Expectation(
            name="property_type_valid",
            description="Types de bien dans le vocabulaire contrôlé",
            column="property_type", critical=False,
            fn=lambda df: (
                (pct := df["property_type"].dropna().isin(VALID_PROPERTY_TYPES).mean()) >= 0.95,
                f"{pct*100:.1f}% de types valides",
                round(pct, 3),
            ) if "property_type" in df.columns else (False, "colonne absente", None)
        ),

        # ── URL / déduplication ───────────────────────────────────────────────
        Expectation(
            name="url_unique",
            description="Pas de doublons d'URL",
            column="url", critical=True,
            fn=lambda df: (
                (n_dup := df["url"].dropna().duplicated().sum()) == 0,
                f"{n_dup} URLs en double",
                int(n_dup),
            ) if "url" in df.columns else (True, "colonne absente", None)
        ),

        # ── Description ───────────────────────────────────────────────────────
        Expectation(
            name="description_not_empty",
            description="Taux de descriptions vides < 40%",
            column="description", critical=False,
            fn=lambda df: (
                (null_r := df["description"].isna().mean() +
                           (df["description"] == "").mean()) < 0.40,
                f"{null_r*100:.1f}% de descriptions vides",
                round(null_r, 3),
            ) if "description" in df.columns else (False, "colonne absente", None)
        ),

        # ── Trust score ───────────────────────────────────────────────────────
        Expectation(
            name="trust_score_range",
            description="Trust scores entre 0 et 1",
            column="trust_score", critical=False,
            fn=lambda df: (
                (pct := df["trust_score"].dropna().between(0, 1).mean()) == 1.0,
                f"{pct*100:.1f}% de trust scores valides",
                round(pct, 3),
            ) if "trust_score" in df.columns else (True, "colonne absente", None)
        ),
        Expectation(
            name="suspect_rate_acceptable",
            description="Taux d'annonces suspectes < 30%",
            column="trust_score", critical=False,
            fn=lambda df: (
                (suspect_r := (df["trust_score"] < 0.50).mean()) < 0.30,
                f"{suspect_r*100:.1f}% d'annonces suspectes",
                round(suspect_r, 3),
            ) if "trust_score" in df.columns else (True, "colonne absente", None)
        ),

        # ── Couverture géographique ────────────────────────────────────────────
        Expectation(
            name="governorate_coverage",
            description="Au moins 5 gouvernorats couverts",
            column="governorate", critical=False,
            fn=lambda df: (
                (n := df["governorate"].nunique()) >= 5,
                f"{n}/24 gouvernorats couverts",
                int(n),
            ) if "governorate" in df.columns else (False, "colonne absente", None)
        ),

        # ── Sources ───────────────────────────────────────────────────────────
        Expectation(
            name="multi_source",
            description="Au moins 2 sources différentes",
            column="source", critical=False,
            fn=lambda df: (
                (n := df["source"].nunique()) >= 2,
                f"{n} source(s) : {', '.join(df['source'].unique()[:5])}",
                int(n),
            ) if "source" in df.columns else (False, "colonne absente", None)
        ),

        # ── Cohérence prix/surface ────────────────────────────────────────────
        Expectation(
            name="price_surface_correlation",
            description="Corrélation prix/surface > 0.30 (cohérence marché)",
            column=None, critical=False,
            fn=lambda df: (
                (corr := df[["price","surface"]].dropna().corr().iloc[0,1]) > 0.30,
                f"Corrélation prix/surface = {corr:.3f}",
                round(corr, 3),
            ) if "price" in df.columns and "surface" in df.columns else (True, "colonnes absentes", None)
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION REPORT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationReport:
    run_id:         str
    evaluated_at:   str = field(default_factory=lambda: datetime.utcnow().isoformat())
    n_total:        int = 0
    n_passed:       int = 0
    n_failed:       int = 0
    n_critical_failed: int = 0
    results:        list = field(default_factory=list)
    overall_passed: bool = True
    score:          float = 0.0
    summary:        str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [asdict(r) for r in self.results]
        return d


# ══════════════════════════════════════════════════════════════════════════════
# DATA VALIDATOR — moteur principal
# ══════════════════════════════════════════════════════════════════════════════

class DataValidator:
    """
    Valide le DataFrame selon une suite d'expectations déclaratives.
    Génère un rapport JSON + HTML après chaque run.
    """

    REPORTS_DIR = Path("data/reports")

    def __init__(self):
        self.expectations = build_expectations()

    def validate(self, df: pd.DataFrame, run_id: str = "unknown") -> ValidationReport:
        """Évalue toutes les expectations sur le DataFrame."""
        logger.info(f"[DataValidator] Validation de {len(df)} annonces...")
        report = ValidationReport(run_id=run_id, n_total=len(self.expectations))

        for exp in self.expectations:
            result = exp.evaluate(df)
            report.results.append(result)
            if result.passed:
                report.n_passed += 1
            else:
                report.n_failed += 1
                if result.critical:
                    report.n_critical_failed += 1

        report.overall_passed  = report.n_critical_failed == 0
        report.score           = round(report.n_passed / max(report.n_total, 1) * 100, 1)
        report.summary = (
            f"{report.n_passed}/{report.n_total} validations passées "
            f"({report.score}%) — "
            + ("OK" if report.overall_passed else f"{report.n_critical_failed} règle(s) critique(s) échouée(s)")
        )

        logger.info(f"[DataValidator] {report.summary}")
        return report

    def generate_html_report(self, report: ValidationReport, df: pd.DataFrame) -> Path:
        """Génère un rapport HTML complet et lisible."""
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.REPORTS_DIR / f"validation_{ts}.html"

        rows_html = ""
        for r in report.results:
            color   = "#1D9E75" if r.passed else ("#E24B4A" if r.critical else "#E8A84C")
            bg      = "#E1F5EE" if r.passed else ("#FCEBEB" if r.critical else "#FAEEDA")
            status  = "PASS" if r.passed else ("FAIL" if r.critical else "WARN")
            col_str = r.column or "—"
            rows_html += f"""
            <tr style="background:{bg}">
              <td style="padding:10px 14px;font-weight:500;color:{color}">{status}</td>
              <td style="padding:10px 14px">{r.name}</td>
              <td style="padding:10px 14px;color:#555">{col_str}</td>
              <td style="padding:10px 14px">{r.description}</td>
              <td style="padding:10px 14px;color:#333">{r.detail}</td>
            </tr>"""

        # Stats quick
        src_dist  = df["source"].value_counts().to_dict() if "source" in df.columns else {}
        type_dist = df["property_type"].value_counts().head(5).to_dict() if "property_type" in df.columns else {}
        src_rows  = "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>" for k,v in src_dist.items())
        type_rows = "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>" for k,v in type_dist.items())
        price_med = round(df["price"].median(), 0) if "price" in df.columns else "N/A"
        trust_avg = round(df["trust_score"].mean(), 3) if "trust_score" in df.columns else "N/A"

        overall_color = "#1D9E75" if report.overall_passed else "#E24B4A"
        overall_label = "VALIDATION RÉUSSIE" if report.overall_passed else "VALIDATION ÉCHOUÉE"

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Estate Mind — Rapport de validation {ts}</title>
  <style>
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f8f8f6;color:#222;margin:0;padding:32px}}
    .header{{background:#09090B;color:#F2F0EC;padding:32px 40px;border-radius:12px;margin-bottom:28px}}
    .header h1{{margin:0 0 4px;font-size:22px;font-weight:600}}
    .header p{{margin:0;color:#888;font-size:13px}}
    .badge{{display:inline-block;background:{overall_color};color:#fff;padding:6px 18px;
            border-radius:999px;font-size:13px;font-weight:600;margin-top:14px}}
    .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
    .kpi{{background:#fff;border:1px solid #e8e8e6;border-radius:10px;padding:20px 22px}}
    .kpi .val{{font-size:26px;font-weight:700;color:#09090B;font-family:Georgia,serif}}
    .kpi .lbl{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-top:4px}}
    .section{{background:#fff;border:1px solid #e8e8e6;border-radius:10px;margin-bottom:20px;overflow:hidden}}
    .section-title{{padding:16px 20px;font-weight:600;font-size:13px;
                    border-bottom:1px solid #e8e8e6;background:#fafaf8}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{padding:10px 14px;text-align:left;font-size:11px;color:#888;
        text-transform:uppercase;letter-spacing:.05em;background:#fafaf8;border-bottom:1px solid #e8e8e6}}
    td{{border-bottom:1px solid #f0f0ee}}
    .score-bar{{height:8px;background:#e8e8e6;border-radius:4px;margin-top:8px;overflow:hidden}}
    .score-fill{{height:100%;background:{overall_color};border-radius:4px;width:{report.score}%}}
    .footer{{color:#aaa;font-size:11px;margin-top:24px;text-align:center}}
  </style>
</head>
<body>
  <div class="header">
    <h1>Estate Mind — Rapport de validation des données</h1>
    <p>Run ID : {report.run_id} &nbsp;|&nbsp; Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")}</p>
    <div class="badge">{overall_label}</div>
    <div class="score-bar" style="margin-top:16px;max-width:400px">
      <div class="score-fill"></div>
    </div>
    <p style="margin-top:6px;font-size:12px;color:#aaa">{report.score}% des validations réussies ({report.n_passed}/{report.n_total})</p>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="val">{len(df):,}</div><div class="lbl">Annonces validées</div></div>
    <div class="kpi"><div class="val">{report.n_passed}/{report.n_total}</div><div class="lbl">Validations passées</div></div>
    <div class="kpi"><div class="val" style="color:#1D9E75">{price_med:,} TND</div><div class="lbl">Prix médian</div></div>
    <div class="kpi"><div class="val" style="color:#7F77DD">{trust_avg}</div><div class="lbl">Trust score moyen</div></div>
  </div>

  <div class="section">
    <div class="section-title">Résultats des validations</div>
    <table>
      <thead><tr><th>Statut</th><th>Règle</th><th>Colonne</th><th>Description</th><th>Observé</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div class="section">
      <div class="section-title">Distribution par source</div>
      <table><tbody>{src_rows}</tbody></table>
    </div>
    <div class="section">
      <div class="section-title">Top types de biens</div>
      <table><tbody>{type_rows}</tbody></table>
    </div>
  </div>

  <div class="footer">Estate Mind — BO1 Data Quality Report &nbsp;|&nbsp; pipeline v3</div>
</body>
</html>"""

        path.write_text(html, encoding="utf-8")
        logger.info(f"[DataValidator] Rapport HTML généré : {path}")
        return path

    def log_to_mlflow(self, report: ValidationReport) -> None:
        """Loggue les résultats dans MLflow."""
        try:
            import mlflow
            metrics = {
                "validation/score":          report.score,
                "validation/n_passed":       report.n_passed,
                "validation/n_failed":       report.n_failed,
                "validation/n_critical_fail":report.n_critical_failed,
                "validation/overall_passed": float(report.overall_passed),
            }
            for r in report.results:
                metrics[f"validation/{r.name}"] = float(r.passed)
            mlflow.log_metrics(metrics)
        except Exception as e:
            logger.warning(f"[DataValidator] MLflow log échoué : {e}")
