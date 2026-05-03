"""
generate_report.py
─────────────────────────────────────────────────────────────────
Génération de rapport PDF juridique TuniState
Utilise reportlab pour créer un PDF professionnel
"""
import json
from pathlib import Path
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

ORANGE = HexColor("#F7941D") if HAS_REPORTLAB else None
DARK   = HexColor("#1E1E1E") if HAS_REPORTLAB else None
GRAY   = HexColor("#888888") if HAS_REPORTLAB else None
GREEN  = HexColor("#22C55E") if HAS_REPORTLAB else None
RED    = HexColor("#E24B4A") if HAS_REPORTLAB else None
AMBER  = HexColor("#F59E0B") if HAS_REPORTLAB else None
LGRAY  = HexColor("#F5F5F5") if HAS_REPORTLAB else None


def generate_pdf(
    situation: str,
    compliance_result: dict,
    destinataire: str = "Usage personnel",
    output_path: str = None,
) -> str:
    """
    Génère un rapport PDF juridique complet.

    Args:
        situation        : situation juridique analysée
        compliance_result: résultat de check_compliance()
        destinataire     : "Banque" / "Notaire" / "Usage personnel"
        output_path      : chemin de sortie (défaut: reports/rapport_YYYYMMDD_HHMMSS.pdf)

    Returns:
        Chemin du PDF généré
    """
    if not HAS_REPORTLAB:
        raise ImportError("reportlab requis : pip install reportlab")

    # Dossier de sortie
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(reports_dir / f"rapport_juridique_{ts}.pdf")
    # Sécurité : si output_path est une liste, prendre le premier élément
    if isinstance(output_path, list):
        output_path = output_path[0] if output_path else str(reports_dir / "rapport_juridique.pdf")
    output_path = str(output_path)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story  = []

    # ── Styles ────────────────────────────────────────────────────
    title_style = ParagraphStyle("title",
        fontSize=22, textColor=DARK, fontName="Helvetica-Bold",
        spaceAfter=4, alignment=TA_LEFT)
    sub_style = ParagraphStyle("sub",
        fontSize=11, textColor=GRAY, fontName="Helvetica",
        spaceAfter=16, alignment=TA_LEFT)
    h2_style = ParagraphStyle("h2",
        fontSize=14, textColor=ORANGE, fontName="Helvetica-Bold",
        spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle("body",
        fontSize=11, textColor=DARK, fontName="Helvetica",
        spaceAfter=8, leading=16)
    small_style = ParagraphStyle("small",
        fontSize=9, textColor=GRAY, fontName="Helvetica",
        spaceAfter=4)

    # ── En-tête ────────────────────────────────────────────────────
    header_data = [[
        Paragraph("<b>ESTATE MIND</b>", ParagraphStyle("brand",
            fontSize=18, textColor=ORANGE, fontName="Helvetica-Bold")),
        Paragraph(f"Rapport juridique<br/><font size='9' color='#888888'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
            ParagraphStyle("date", fontSize=11, textColor=DARK,
                fontName="Helvetica", alignment=2))
    ]]
    header_table = Table(header_data, colWidths=[9*cm, 8*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 1, ORANGE),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    # ── Titre ─────────────────────────────────────────────────────
    story.append(Paragraph("Rapport de Conformité Juridique", title_style))
    story.append(Paragraph(
        f"Destinataire : {destinataire} · Code des Droits Réels tunisien + Code de l'Urbanisme 2011",
        sub_style))

    # ── Situation analysée ─────────────────────────────────────────
    story.append(Paragraph("Situation analysée", h2_style))
    sit_data = [[Paragraph(f'"{situation}"', ParagraphStyle("sit",
        fontSize=12, textColor=DARK, fontName="Helvetica-Oblique",
        leading=18))]]
    sit_table = Table(sit_data, colWidths=[17*cm])
    sit_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LGRAY),
        ('BOX', (0,0), (-1,-1), 0.5, HexColor("#DDDDDD")),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [LGRAY]),
    ]))
    story.append(sit_table)
    story.append(Spacer(1, 12))

    # ── Verdict global ─────────────────────────────────────────────
    status    = compliance_result.get("global_status", "UNKNOWN")
    risk      = compliance_result.get("risk_score", 0)
    rag       = compliance_result.get("rag_fallback") or {}

    status_colors = {
        "VIOLATION":    RED,
        "WARNING":      AMBER,
        "COMPLIANT":    GREEN,
        "UNKNOWN":      GRAY,
        "OUT_OF_DOMAIN": GRAY,
    }
    status_labels = {
        "VIOLATION":    "VIOLATION DÉTECTÉE",
        "WARNING":      "AVERTISSEMENT — CONDITIONS À VÉRIFIER",
        "COMPLIANT":    "CONFORME",
        "UNKNOWN":      "INDÉTERMINÉ",
        "OUT_OF_DOMAIN": "HORS DOMAINE",
    }
    sc = status_colors.get(status, GRAY)
    sl = status_labels.get(status, status)

    story.append(Paragraph("Verdict juridique", h2_style))
    verdict_data = [
        [Paragraph(f"<b>{sl}</b>", ParagraphStyle("verdict",
            fontSize=14, textColor=white, fontName="Helvetica-Bold",
            alignment=TA_CENTER)),
         Paragraph(f"<b>{risk} / 100</b>", ParagraphStyle("score",
            fontSize=20, textColor=white, fontName="Helvetica-Bold",
            alignment=TA_CENTER))],
        [Paragraph("Statut de conformité", ParagraphStyle("vl",
            fontSize=9, textColor=white, fontName="Helvetica",
            alignment=TA_CENTER)),
         Paragraph("Score de risque réglementaire", ParagraphStyle("vl2",
            fontSize=9, textColor=white, fontName="Helvetica",
            alignment=TA_CENTER))]
    ]
    verdict_table = Table(verdict_data, colWidths=[10*cm, 7*cm], rowHeights=[30, 18])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), sc),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEAFTER', (0,0), (0,-1), 0.5, white),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 12))

    # ── Violations / Warnings ──────────────────────────────────────
    violations = compliance_result.get("violations", [])
    warnings   = compliance_result.get("warnings",   [])

    if violations:
        story.append(Paragraph("Violations identifiées", h2_style))
        for v in violations[:5]:
            rule = v.get("rule", {})
            story.append(Paragraph(
                f"• <b>Art.{v.get('article','?')}</b> — {rule.get('action','?')} "
                f"({rule.get('status','?').upper()}) — Risque : {v.get('risk_score',0)}/100",
                body_style))
        story.append(Spacer(1, 8))

    if warnings:
        story.append(Paragraph("Avertissements", h2_style))
        for w in warnings[:5]:
            story.append(Paragraph(
                f"• <b>Art.{w.get('article','?')}</b> — {w.get('message','')[:120]}",
                body_style))
        story.append(Spacer(1, 8))

    # ── RAG Urbanisme ──────────────────────────────────────────────
    if rag and rag.get("used"):
        story.append(Paragraph("Analyse Code de l'Urbanisme", h2_style))
        _law = rag.get("law", "Code de l'Amenagement du Territoire 2011")
        story.append(Paragraph("Source : " + _law, small_style))
        arts = rag.get("articles", [])
        if arts:
            story.append(Paragraph(
                "Articles référencés : " + " · ".join(arts),
                small_style))
        if rag.get("explanation"):
            story.append(Paragraph(rag["explanation"], body_style))
        story.append(Spacer(1, 8))

    # ── Recommandations ────────────────────────────────────────────
    story.append(Paragraph("Recommandations", h2_style))
    recs = {
        "VIOLATION":    [
            "Cessez immédiatement l'action concernée.",
            "Consultez un notaire ou juriste spécialisé en droit immobilier tunisien.",
            "Obtenez les autorisations nécessaires avant de reprendre.",
        ],
        "WARNING":      [
            "Vérifiez que toutes les conditions légales sont remplies.",
            "Consultez un notaire pour valider les conditions manquantes.",
            "Documentez toutes les démarches entreprises.",
        ],
        "COMPLIANT":    [
            "Conservez les documents justificatifs de conformité.",
            "Effectuez une vérification périodique avec les mises à jour du code.",
        ],
        "UNKNOWN":      [
            "Consultez un notaire ou juriste spécialisé en droit réel tunisien.",
            "Cette situation n'est pas couverte par notre base de règles actuelle.",
        ],
    }
    for rec in recs.get(status, recs["UNKNOWN"]):
        story.append(Paragraph(f"• {rec}", body_style))

    # ── Sources juridiques ─────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=HexColor("#DDDDDD")))
    story.append(Spacer(1, 8))
    sources_data = [
        ["Source", "Référence", "Statut"],
        ["Code des Droits Réels", "Loi n°65-5 du 12 février 1965", "Actif"],
        ["Code de l'Urbanisme", "CATU — Edition 2011", "Actif"],
    ]
    src_table = Table(sources_data, colWidths=[6*cm, 7*cm, 4*cm])
    src_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, LGRAY]),
        ('GRID', (0,0), (-1,-1), 0.3, HexColor("#DDDDDD")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(Paragraph("Sources juridiques", h2_style))
    story.append(src_table)

    # ── Pied de page ───────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", color=ORANGE))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Ce rapport est généré automatiquement par Estate Mind Legal Agent (BO5). "
        "Il est fourni à titre informatif et ne remplace pas l'avis d'un juriste qualifié. "
        "Pour toute question, consultez un notaire spécialisé en droit immobilier tunisien.",
        ParagraphStyle("footer", fontSize=8, textColor=GRAY,
            fontName="Helvetica", alignment=TA_CENTER, leading=12)))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    result = {
        "global_status": "VIOLATION",
        "risk_score": 64,
        "violations": [{
            "article": "23",
            "risk_score": 64,
            "rule": {"action": "construire sans permis", "status": "interdit"}
        }],
        "warnings": [],
        "rag_fallback": {
            "used": True,
            "law": "Code de l'Aménagement du Territoire 2011",
            "articles": ["Art.23 CATU", "Art.2 CATU"],
            "explanation": "Toute construction nécessite une autorisation administrative préalable selon l'article 23 du Code de l'Urbanisme tunisien.",
            "risk_score": 64
        }
    }
    path = generate_pdf(
        situation="je veux construire sans permis",
        compliance_result=result,
        destinataire="Banque Zitouna",
    )
    print(f"✅ Rapport généré : {path}")
    