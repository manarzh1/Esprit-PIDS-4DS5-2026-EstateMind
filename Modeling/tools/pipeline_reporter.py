"""
Estate Mind — Automated Pipeline Report
═════════════════════════════════════════
Génère un rapport HTML complet et professionnel après chaque run pipeline.

Contenu du rapport :
  - Résumé exécutif (1 page) avec statut global
  - Métriques clés : annonces, qualité, trust, drift, health
  - Comparaison vs run précédent (delta en %)
  - Graphiques ASCII des distributions (sans dépendance matplotlib)
  - Top 5 annonces suspectes
  - Alertes actives
  - Lineage summary
  - Validation report embed

Sauvegardé dans data/reports/pipeline_TIMESTAMP.html
Accessible directement dans le navigateur.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from loguru import logger


REPORTS_DIR   = Path("data/reports")
STATE_PATH    = Path("data/state/last_report_state.json")


# ── Chargement/sauvegarde du dernier état (pour la comparaison) ───────────────

def _load_last_state() -> dict:
    if STATE_PATH.exists():
        try: return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except: return {}
    return {}

def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str))


# ── Helpers visuels ───────────────────────────────────────────────────────────

def _delta_badge(current: float, previous: Optional[float], higher_is_better: bool = True) -> str:
    if previous is None or previous == 0:
        return ""
    delta = (current - previous) / abs(previous) * 100
    good  = delta > 0 if higher_is_better else delta < 0
    color = "#1D9E75" if good else "#E24B4A"
    sign  = "+" if delta > 0 else ""
    return f'<span style="font-size:11px;color:{color};margin-left:6px">{sign}{delta:.1f}%</span>'

def _bar(value: float, max_val: float, width: int = 120, color: str = "#1D9E75") -> str:
    pct = min(value / max(max_val, 1) * 100, 100)
    return (f'<div style="height:6px;background:#eee;border-radius:3px;width:{width}px;display:inline-block;vertical-align:middle">'
            f'<div style="height:100%;width:{pct:.0f}%;background:{color};border-radius:3px"></div></div>')

def _trust_color(score: float) -> str:
    if score >= 0.75: return "#1D9E75"
    if score >= 0.50: return "#E8A84C"
    return "#E24B4A"

def _legal_color(score: float) -> str:
    if score < 0.30: return "#1D9E75"
    if score < 0.60: return "#E8A84C"
    return "#E24B4A"


# ══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATEUR DE RAPPORT
# ══════════════════════════════════════════════════════════════════════════════

class PipelineReporter:
    """Génère le rapport HTML complet du pipeline."""

    def generate(
        self,
        run_result:        dict,
        df_clean:          pd.DataFrame,
        validation_report: Optional[Any] = None,
        drift_report:      Optional[Any] = None,
        health_report:     Optional[Any] = None,
    ) -> Path:
        """
        Génère le rapport HTML et le sauvegarde.

        Args:
            run_result        : dict retourné par CollectorAgent.run_full_pipeline()
            df_clean          : DataFrame final nettoyé
            validation_report : ValidationReport (optionnel)
            drift_report      : DriftReport (optionnel)
            health_report     : HealthReport (optionnel)

        Returns:
            Path vers le fichier HTML généré
        """
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        path      = REPORTS_DIR / f"pipeline_{ts}.html"
        last      = _load_last_state()
        run_id    = run_result.get("run_id", "unknown")
        rows_out  = run_result.get("rows_out", len(df_clean))
        quality   = run_result.get("quality", {})
        drift     = run_result.get("drift", {})
        health    = run_result.get("health", {})
        upsert    = run_result.get("upsert", {})
        elapsed   = run_result.get("elapsed_s", 0)

        # ── Statut global ─────────────────────────────────────────────────────
        has_drift    = drift.get("action_required", False)
        has_critical = health.get("n_critical", 0) > 0
        val_failed   = validation_report and not validation_report.overall_passed if validation_report else False
        global_ok    = not has_drift and not has_critical and not val_failed

        status_color = "#1D9E75" if global_ok else "#E24B4A"
        status_label = "PIPELINE RÉUSSI" if global_ok else "PIPELINE AVEC ALERTES"

        # ── KPIs ──────────────────────────────────────────────────────────────
        avg_trust  = float(df_clean["trust_score"].mean())     if "trust_score"      in df_clean.columns else 0.0
        suspect_ct = int((df_clean["trust_score"] < 0.5).sum()) if "trust_score"     in df_clean.columns else 0
        high_legal = int((df_clean["legal_risk_score"] >= 0.6).sum()) if "legal_risk_score" in df_clean.columns else 0
        n_gov      = df_clean["governorate"].nunique() if "governorate" in df_clean.columns else 0
        price_med  = df_clean["price"].median() if "price" in df_clean.columns else 0

        # ── Source distribution ───────────────────────────────────────────────
        src_dist   = df_clean["source"].value_counts().to_dict() if "source" in df_clean.columns else {}
        src_rows   = ""
        for src, cnt in src_dist.items():
            pct = cnt / max(rows_out, 1) * 100
            src_rows += f"""<tr>
              <td style="padding:10px 16px">{src}</td>
              <td style="padding:10px 16px">{cnt:,}</td>
              <td style="padding:10px 16px">{_bar(cnt, rows_out, 140)}</td>
              <td style="padding:10px 16px;color:#666">{pct:.1f}%</td>
            </tr>"""

        # ── Top suspects ──────────────────────────────────────────────────────
        suspect_rows = ""
        if "trust_score" in df_clean.columns:
            top_sus = df_clean.nsmallest(5, "trust_score")[["title","city","price","trust_score","source"]]
            for _, r in top_sus.iterrows():
                tc = _trust_color(r["trust_score"])
                suspect_rows += f"""<tr>
                  <td style="padding:9px 14px;font-size:12px">{str(r.get('title',''))[:55]}</td>
                  <td style="padding:9px 14px;font-size:12px">{r.get('city','—')}</td>
                  <td style="padding:9px 14px;font-size:12px">{f"{r['price']:,.0f} TND" if pd.notna(r.get('price')) else '—'}</td>
                  <td style="padding:9px 14px"><span style="color:{tc};font-weight:600">{r['trust_score']:.3f}</span></td>
                  <td style="padding:9px 14px;font-size:11px;color:#888">{r.get('source','')}</td>
                </tr>"""

        # ── Drift résumé ──────────────────────────────────────────────────────
        drift_rows = ""
        if drift_report and hasattr(drift_report, "columns"):
            for col, info in drift_report.columns.items():
                icon  = "❌" if info.drifted else "✅"
                shift = f"{info.mean_shift_pct*100:+.1f}%" if info.mean_shift_pct else "—"
                drift_rows += f"""<tr>
                  <td style="padding:9px 14px">{icon}</td>
                  <td style="padding:9px 14px;font-family:monospace">{col}</td>
                  <td style="padding:9px 14px">{info.ks_statistic:.4f}</td>
                  <td style="padding:9px 14px">{info.p_value:.4f}</td>
                  <td style="padding:9px 14px;color:{'#E24B4A' if info.drifted else '#1D9E75'}">{shift}</td>
                </tr>"""

        # ── Health résumé ─────────────────────────────────────────────────────
        health_rows = ""
        if health_report and hasattr(health_report, "sources"):
            for src, status in health_report.sources.items():
                icon  = "✅" if status.healthy else "❌"
                issue = status.issue or "OK"
                health_rows += f"""<tr>
                  <td style="padding:9px 14px">{icon}</td>
                  <td style="padding:9px 14px">{src}</td>
                  <td style="padding:9px 14px">{status.rows:,}</td>
                  <td style="padding:9px 14px;color:#888;font-size:11px">{issue}</td>
                </tr>"""

        # ── Validation summary ────────────────────────────────────────────────
        val_html = ""
        if validation_report:
            val_score = validation_report.score
            val_color = "#1D9E75" if val_score >= 85 else ("#E8A84C" if val_score >= 60 else "#E24B4A")
            val_html  = f"""
            <div class="section">
              <div class="section-title">Validation des données — {validation_report.n_passed}/{validation_report.n_total} règles passées</div>
              <div style="padding:16px 20px">
                <div style="font-size:28px;font-weight:700;color:{val_color};font-family:Georgia,serif">{val_score}%</div>
                <div class="bar-bg" style="margin:8px 0;max-width:300px">
                  <div style="height:100%;width:{val_score}%;background:{val_color};border-radius:3px"></div>
                </div>
                <div style="font-size:12px;color:#666">{validation_report.summary}</div>
              </div>
            </div>"""

        # ── Alertes ───────────────────────────────────────────────────────────
        alerts = []
        if has_drift:        alerts.append(("🔴 Drift détecté", drift.get("recommendation",""), "#E24B4A"))
        if has_critical:     alerts.append(("🔴 Source(s) critique(s)", f"{health.get('n_critical')} source(s) hors service", "#E24B4A"))
        if val_failed:       alerts.append(("⚠️ Validation échouée", f"{validation_report.n_critical_failed} règle(s) critique(s)", "#E8A84C"))
        if suspect_ct > rows_out * 0.15:
            alerts.append(("⚠️ Taux de suspects élevé", f"{suspect_ct} annonces suspects ({suspect_ct/max(rows_out,1)*100:.0f}%)", "#E8A84C"))

        alerts_html = ""
        for title, msg, color in alerts:
            alerts_html += f"""<div style="background:{color}14;border-left:3px solid {color};
              border-radius:0 6px 6px 0;padding:12px 16px;margin-bottom:10px">
              <div style="font-weight:600;font-size:13px;color:{color}">{title}</div>
              <div style="font-size:12px;color:#555;margin-top:3px">{msg}</div>
            </div>"""
        if not alerts_html:
            alerts_html = '<div style="color:#1D9E75;font-size:13px">Aucune alerte — tout est nominal.</div>'

        # ── Sauvegarde état pour comparaison future ───────────────────────────
        current_state = {
            "run_id": run_id, "ts": ts,
            "rows_out": rows_out, "avg_trust": avg_trust,
            "quality_score": quality.get("global_quality_score"),
            "suspect_count": suspect_ct,
        }
        _save_state(current_state)

        # ── HTML final ────────────────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Estate Mind — Pipeline Report {ts}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f5f5f2;color:#1a1a18;line-height:1.5}}
    .wrap{{max-width:1050px;margin:0 auto;padding:32px 20px}}
    .header{{background:#09090B;color:#F2F0EC;padding:36px 44px;border-radius:14px;margin-bottom:24px}}
    .header h1{{font-size:20px;font-weight:600;margin-bottom:4px}}
    .header p{{color:#888;font-size:13px}}
    .status-badge{{display:inline-flex;align-items:center;gap:8px;background:{status_color};
      color:#fff;padding:8px 20px;border-radius:999px;font-size:13px;font-weight:600;margin-top:16px}}
    .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}}
    .kpi{{background:#fff;border:1px solid #e5e5e2;border-radius:10px;padding:20px 22px}}
    .kpi .val{{font-size:24px;font-weight:700;font-family:Georgia,serif}}
    .kpi .lbl{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-top:4px}}
    .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
    .section{{background:#fff;border:1px solid #e5e5e2;border-radius:10px;margin-bottom:16px;overflow:hidden}}
    .section-title{{padding:14px 20px;font-weight:600;font-size:13px;border-bottom:1px solid #eeede9;background:#faf9f6}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{padding:9px 14px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;
        letter-spacing:.05em;background:#faf9f6;border-bottom:1px solid #eeede9}}
    td{{border-bottom:1px solid #f2f1ee}}
    .bar-bg{{height:6px;background:#eeede9;border-radius:3px;overflow:hidden}}
    .footer{{color:#aaa;font-size:11px;text-align:center;padding:24px 0}}
    .chip{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:500}}
  </style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div class="header">
    <h1>Estate Mind — Pipeline Report</h1>
    <p>Run ID : {run_id} &nbsp;|&nbsp; {datetime.now().strftime("%d %B %Y à %H:%M")} &nbsp;|&nbsp; Durée : {elapsed:.1f}s</p>
    <div class="status-badge">{status_label}</div>
  </div>

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi">
      <div class="val">{rows_out:,}{_delta_badge(rows_out, last.get('rows_out'), True)}</div>
      <div class="lbl">Annonces nettoyées</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:{_trust_color(avg_trust)}">{avg_trust:.3f}{_delta_badge(avg_trust, last.get('avg_trust'), True)}</div>
      <div class="lbl">Trust score moyen</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:{'#1D9E75' if quality.get('global_quality_score',0)>=80 else '#E8A84C'}">{quality.get('global_quality_score','—')}{_delta_badge(quality.get('global_quality_score',0), last.get('quality_score'), True)}</div>
      <div class="lbl">Score qualité / 100</div>
    </div>
    <div class="kpi">
      <div class="val">{n_gov}/24</div>
      <div class="lbl">Gouvernorats couverts</div>
    </div>
  </div>

  <div class="grid2">
    <!-- Alertes -->
    <div class="section">
      <div class="section-title">Alertes actives</div>
      <div style="padding:16px 20px">{alerts_html}</div>
    </div>

    <!-- PostgreSQL -->
    <div class="section">
      <div class="section-title">PostgreSQL — upsert stats</div>
      <div style="padding:16px 20px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;text-align:center">
        <div><div style="font-size:22px;font-weight:700;color:#1D9E75;font-family:Georgia,serif">{upsert.get('inserted',0):,}</div><div style="font-size:11px;color:#888">Insérées</div></div>
        <div><div style="font-size:22px;font-weight:700;color:#7F77DD;font-family:Georgia,serif">{upsert.get('updated',0):,}</div><div style="font-size:11px;color:#888">Mises à jour</div></div>
        <div><div style="font-size:22px;font-weight:700;color:#888;font-family:Georgia,serif">{upsert.get('skipped',0):,}</div><div style="font-size:11px;color:#888">Ignorées</div></div>
      </div>
    </div>
  </div>

  {val_html}

  <!-- Sources -->
  <div class="section">
    <div class="section-title">Distribution par source</div>
    <table><thead><tr><th>Source</th><th>Annonces</th><th>Part</th><th>%</th></tr></thead>
    <tbody>{src_rows}</tbody></table>
  </div>

  <div class="grid2">
    <!-- Drift -->
    <div class="section">
      <div class="section-title">Data Drift (KS test)</div>
      <table><thead><tr><th></th><th>Colonne</th><th>KS stat</th><th>p-value</th><th>Shift</th></tr></thead>
      <tbody>{drift_rows or '<tr><td colspan="5" style="padding:14px;color:#888;text-align:center">Aucune donnée drift</td></tr>'}</tbody></table>
    </div>

    <!-- Health -->
    <div class="section">
      <div class="section-title">Source Health Monitor</div>
      <table><thead><tr><th></th><th>Source</th><th>Lignes</th><th>Statut</th></tr></thead>
      <tbody>{health_rows or '<tr><td colspan="4" style="padding:14px;color:#888;text-align:center">Aucun check effectué</td></tr>'}</tbody></table>
    </div>
  </div>

  <!-- Top suspects -->
  <div class="section">
    <div class="section-title">Top 5 — Annonces les plus suspectes</div>
    <table><thead><tr><th>Titre</th><th>Ville</th><th>Prix</th><th>Trust score</th><th>Source</th></tr></thead>
    <tbody>{suspect_rows or '<tr><td colspan="5" style="padding:14px;color:#888;text-align:center">Aucune annonce suspecte</td></tr>'}</tbody></table>
  </div>

  <!-- Pipeline info -->
  <div class="section">
    <div class="section-title">Informations pipeline</div>
    <div style="padding:16px 20px;display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px">
      <div><span style="color:#888">Annonces brutes ingérées</span> : {run_result.get('rows_in',0):,}</div>
      <div><span style="color:#888">Fuzzy dups supprimés</span> : {run_result.get('fuzzy_dups',0):,}</div>
      <div><span style="color:#888">NLP enrichies</span> : {run_result.get('nlp_enriched',0):,}</div>
      <div><span style="color:#888">Prix médian</span> : {f"{price_med:,.0f} TND" if price_med else "—"}</div>
      <div><span style="color:#888">Annonces suspectes</span> : <span style="color:#E24B4A">{suspect_ct:,}</span></div>
      <div><span style="color:#888">Risque légal élevé</span> : <span style="color:#E24B4A">{high_legal:,}</span></div>
    </div>
  </div>

  <div class="footer">Estate Mind PropTech — Pipeline v3 — BO1 Automated Report &nbsp;|&nbsp; {ts}</div>
</div>
</body>
</html>"""

        path.write_text(html, encoding="utf-8")
        logger.info(f"[PipelineReporter] Rapport HTML généré : {path}")
        return path
