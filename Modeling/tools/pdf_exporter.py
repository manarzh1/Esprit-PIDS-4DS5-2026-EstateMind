"""
Estate Mind — PDF Exporter
Convertit les rapports HTML en PDF avec weasyprint.
pip install weasyprint
"""
from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

REPORTS_DIR = Path("data/reports")

try:
    from weasyprint import HTML as WeasyHTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("[PDFExporter] weasyprint non installé — pip install weasyprint")

PDF_CSS = """
@page { size: A4; margin: 20mm 18mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, sans-serif; color: #1a1a18; font-size: 11pt; line-height: 1.6; }
.header { background: #09090B; color: #F2F0EC; padding: 18px 22px; border-radius: 8px; margin-bottom: 18px; }
.header h1 { font-size: 15pt; font-weight: 600; margin: 6px 0 0; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 18px; }
.kpi { background: #f8f8f6; border: 1px solid #e5e5e2; border-radius: 8px; padding: 10px 12px; }
.kpi .val { font-size: 18pt; font-weight: 700; }
.kpi .lbl { font-size: 8pt; color: #888; text-transform: uppercase; margin-top: 2px; }
.stitle { font-size: 12pt; font-weight: 600; border-bottom: 2px solid #C8A96E; padding-bottom: 5px; margin: 14px 0 10px; }
table { width: 100%; border-collapse: collapse; font-size: 10pt; }
th { background: #f0f0ee; padding: 7px 10px; text-align: left; font-size: 9pt; border-bottom: 1px solid #e5e5e2; }
td { padding: 8px 10px; border-bottom: 1px solid #f0f0ee; }
.card { border: 1px solid #e5e5e2; border-radius: 7px; padding: 11px 13px; margin-bottom: 9px; }
.card.critical { border-color: #E24B4A; }
.card.high     { border-color: #E8A84C; }
.reco { background: #fffbf5; border-left: 3px solid #C8A96E; padding: 9px 11px; margin-top: 7px; font-size: 10pt; }
.footer { border-top: 1px solid #e5e5e2; padding-top: 10px; margin-top: 20px; font-size: 9pt; color: #888; text-align: center; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 8.5pt; font-weight: 500; }
.bc { background: #FCEBEB; color: #A32D2D; }
.bw { background: #FAEEDA; color: #854F0B; }
.bo { background: #E1F5EE; color: #0F6E56; }
"""

def _header(title, sub=""):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<div class="header">
      <span style="color:#C8A96E;font-size:13pt;font-weight:700">🏛 Estate Mind</span>
      <span style="color:#888;font-size:9pt;margin-left:8px">PropTech Tunisienne</span>
      <h1>{title}</h1>
      {"<div style='font-size:9pt;color:#888;margin-top:3px'>" + sub + "</div>" if sub else ""}
      <div style="font-size:9pt;color:#888;float:right;margin-top:-16px">Généré le {ts}</div>
    </div>"""

def build_territorial_html(alerts, spatial=None, run_id=""):
    nc = sum(1 for a in alerts if a.get("severity")=="critical")
    nh = sum(1 for a in alerts if a.get("severity")=="high")
    ne = sum(1 for a in alerts if a.get("alert_type") in ("emerging","price_surge","volume_surge"))
    nd = sum(1 for a in alerts if a.get("alert_type")=="declining")
    kpis = f"""<div class="kpis">
      <div class="kpi"><div class="val" style="color:#E24B4A">{nc}</div><div class="lbl">Critiques</div></div>
      <div class="kpi"><div class="val" style="color:#E8A84C">{nh}</div><div class="lbl">Importantes</div></div>
      <div class="kpi"><div class="val" style="color:#1D9E75">{ne}</div><div class="lbl">Émergentes</div></div>
      <div class="kpi"><div class="val" style="color:#888">{nd}</div><div class="lbl">En déclin</div></div>
    </div>"""
    ICONS = {"emerging":"🚀","price_surge":"📈","volume_surge":"📊","declining":"📉"}
    alerts_html = ""
    for a in alerts[:15]:
        sev  = a.get("severity","medium")
        zone = a.get("zone","")
        msg  = a.get("message","")
        reco = a.get("recommendation","")
        pg   = a.get("price_growth")
        price= a.get("median_price_recent")
        icon = ICONS.get(a.get("alert_type",""),"📌")
        pg_s = f"+{pg*100:.1f}%" if pg and pg>0 else (f"{pg*100:.1f}%" if pg else "—")
        bc   = "bc" if sev=="critical" else "bw" if sev=="high" else "bo"
        alerts_html += f"""<div class="card {sev}">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong>{icon} {zone}</strong>
            <span class="badge {bc}">{sev.upper()}</span>
          </div>
          <div style="font-size:10pt;color:#444;margin:4px 0">{msg}</div>
          <div style="font-size:9pt;color:#888">Prix: <b>{pg_s}</b>{" &nbsp;·&nbsp; Médian: <b>" + f"{price:,.0f} TND</b>" if price else ""}</div>
          {"<div class='reco'><b>Recommandation :</b> " + reco + "</div>" if reco else ""}
        </div>"""
    cities_html = ""
    if spatial and spatial.get("by_city"):
        top = sorted(spatial["by_city"].items(), key=lambda x: x[1].get("median_ppm2") or 0, reverse=True)[:10]
        rows = "".join(f"<tr><td>{c}</td><td>{d.get('median_ppm2',0):,.0f} TND</td><td>{d.get('n_listings',0):,}</td></tr>" for c,d in top)
        cities_html = f"""<div class="stitle">Top villes — Prix/m²</div>
          <table><tr><th>Ville</th><th>Prix/m² médian</th><th>Annonces</th></tr>{rows}</table>"""
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{PDF_CSS}</style></head><body>
    {_header("Rapport d'Analyse Territoriale", f"Run ID : {run_id}")}
    {kpis}
    <div class="stitle">Alertes territoriales ({len(alerts)})</div>
    {alerts_html or "<p style='color:#888'>Aucune alerte.</p>"}
    {cities_html}
    <div class="footer">Estate Mind PropTech · {datetime.now().strftime("%d/%m/%Y")}</div>
    </body></html>"""

def build_analysis_html(analysis, listing_info):
    title  = listing_info.get("title","Annonce")
    city   = listing_info.get("city","—")
    price  = listing_info.get("price",0) or 0
    surf   = listing_info.get("surface",0) or 0
    ptype  = listing_info.get("property_type","autre").replace("_"," ")
    ts_    = analysis.get("trust_score",0)
    ls_    = analysis.get("legal_risk_score",0)
    verdict= analysis.get("verdict","ATTENTION")
    reco   = analysis.get("recommendation","")
    pa     = analysis.get("price_analysis","")
    flags  = analysis.get("fraud_flags",[])
    laws   = analysis.get("relevant_laws",[])
    vc     = {"FAVORABLE":"#1D9E75","ATTENTION":"#854F0B","DANGER":"#A32D2D"}.get(verdict,"#888")
    tc     = "#1D9E75" if ts_>=.75 else "#854F0B" if ts_>=.5 else "#A32D2D"
    lc     = "#1D9E75" if ls_<.3  else "#854F0B" if ls_<.6 else "#A32D2D"
    ppm2   = round(price/surf) if surf and price else None
    flags_h= "".join(f"<div>⚠️ {f}</div>" for f in flags) or "<div style='color:#888'>Aucun flag</div>"
    laws_h = "".join(f"<div style='margin-bottom:7px'><b>{l.get('article','')}</b> — {l.get('source','')}<br><span style='font-size:9pt;color:#555'>{l.get('summary','')}</span></div>" for l in laws[:3]) or "<div style='color:#888'>Aucune règle identifiée</div>"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{PDF_CSS}</style></head><body>
    {_header("Analyse d'Annonce Immobilière", f"{title} · {city}")}
    <div class="kpis">
      <div class="kpi"><div class="val" style="color:{vc}">{verdict}</div><div class="lbl">Verdict</div></div>
      <div class="kpi"><div class="val" style="color:{tc}">{ts_:.3f}</div><div class="lbl">Trust score</div></div>
      <div class="kpi"><div class="val" style="color:{lc}">{ls_:.3f}</div><div class="lbl">Risque légal</div></div>
      <div class="kpi"><div class="val" style="color:#C8A96E">{price:,.0f}</div><div class="lbl">Prix TND</div></div>
    </div>
    <div class="stitle">Détails du bien</div>
    <table>
      <tr><td><b>Type</b></td><td style="text-transform:capitalize">{ptype}</td></tr>
      <tr><td><b>Ville</b></td><td>{city}</td></tr>
      <tr><td><b>Surface</b></td><td>{str(surf)+" m²" if surf else "—"}</td></tr>
      {"<tr><td><b>Prix/m²</b></td><td>" + str(ppm2) + " TND</td></tr>" if ppm2 else ""}
    </table>
    <div class="stitle">Analyse du prix</div><p>{pa}</p>
    <div class="stitle">Recommandation</div><div class="reco">{reco}</div>
    <div class="stitle">Flags</div>{flags_h}
    <div class="stitle">Références juridiques</div>{laws_h}
    <div class="footer">Estate Mind PropTech · {datetime.now().strftime("%d/%m/%Y %H:%M")}</div>
    </body></html>"""


class PDFExporter:
    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _save(self, html: str, filename: str) -> Path:
        path = REPORTS_DIR / filename
        if WEASYPRINT_AVAILABLE:
            try:
                WeasyHTML(string=html).write_pdf(str(path))
                logger.info(f"[PDFExporter] PDF : {path}")
                return path
            except Exception as e:
                logger.warning(f"[PDFExporter] WeasyPrint : {e} → fallback HTML")
        html_path = REPORTS_DIR / filename.replace(".pdf",".html")
        html_path.write_text(html, encoding="utf-8")
        logger.info(f"[PDFExporter] HTML fallback : {html_path}")
        return html_path

    def export_territorial_report(self, alerts, spatial=None, ts_data=None, run_id="unknown") -> Path:
        html = build_territorial_html(alerts, spatial, run_id)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._save(html, f"territorial_{ts}.pdf")

    def export_listing_analysis(self, analysis, listing_info) -> Path:
        html = build_analysis_html(analysis, listing_info)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        city = listing_info.get("city","x").lower().replace(" ","_")
        return self._save(html, f"analysis_{city}_{ts}.pdf")
