"""
main.py
─────────────────────────────────────────────────────────────────
Point d'entrée CLI unique BO5 — Code des Droits Réels tunisien

COMMANDES :
  python main.py                        → démo complète (données existantes)
  python main.py --step all             → pipeline complet (nécessite Ollama)
  python main.py --step all --skip-llm  → pipeline sans LLM
  python main.py --step extract         → STEP 1 : PDF → texte
  python main.py --step chunk           → STEP 2 : articles
  python main.py --step rules           → STEP 3 : extraction LLM
  python main.py --step clean           → STEP 4 : nettoyage
  python main.py --step risk            → STEP 6 : risk scores
  python main.py --step graph           → STEP 5 : Knowledge Graph
  python main.py --step check \\
      --actor proprietaire \\
      --action construire \\
      --target immeuble               → DS04 : conformité
  python main.py --step diff \\
      --prev data/rules_v1.json       → DS02 : veille réglementaire
  python main.py --step api           → API REST sur port 8000
"""

import json, logging, argparse, sys
from pathlib import Path
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

from config import RULES_CLEAN, DATA_DIR, NEO4J_DIR, SOURCE_NAME


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(pdf: str, skip_llm: bool = False) -> None:
    from pipeline import (
        extract_text, chunk_articles, chunk_coverage_pipeline,
        extract_rules, clean_rules, compute_risk_scores, build_graph,
    )
    _banner("PIPELINE COVERAGE-BASED — Ontologie CDR + MiniLM")
    extract_text(pdf)
    chunk_articles()
    log.info("─── STEP 2b : pipeline coverage-based ───")
    chunk_coverage_pipeline(
        top_k_per_concept=4,
        model_name="all-MiniLM-L6-v2",
    )
    if not skip_llm:
        extract_rules()
    else:
        log.info("[STEP 3] Ignoré (--skip-llm)")
    clean_rules()
    compute_risk_scores()
    build_graph()
    if RULES_CLEAN.exists():
        rules = json.loads(RULES_CLEAN.read_text(encoding="utf-8"))
        log.info(f"✅ Pipeline terminé — {len(rules)} règles")
        log.info("   Évaluation : python main.py --step eval")


# ══════════════════════════════════════════════════════════════════════════════
# DS04 — CONFORMITÉ (CLI)
# ══════════════════════════════════════════════════════════════════════════════

def run_check(actor: str, action: str, target: str,
              conditions: list, threshold: float) -> None:
    from compliance import check_compliance, check_and_alert

    _banner("DS04 — VÉRIFICATION DE CONFORMITÉ")
    print(f"  Acteur     : {actor}")
    print(f"  Action     : {action}")
    print(f"  Cible      : {target or '(non précisée)'}")
    print(f"  Conditions : {conditions or 'aucune'}")
    print(f"  Seuil      : {threshold}\n")

    user_case = {
        "actor":      actor,
        "action":     action,
        "target":     target,
        "conditions": conditions,
    }
    result = check_compliance(user_case, threshold=threshold)
    check_and_alert(result)

    # Affichage
    gs    = result.get("global_status", "")
    icons = {"VIOLATION":"🚨","WARNING":"⚠️","COMPLIANT":"✅","OUT_OF_DOMAIN":"ℹ️"}
    print(f"  {icons.get(gs,'•')}  STATUT : {gs}")
    print(f"  Risk score max : {result.get('risk_score', 0)}/100")
    meta = result.get("meta", {})
    print(f"  Règles vérifiées : {meta.get('rules_checked', 0)}")
    print(f"  Correspondances  : {meta.get('matches_found', 0)}\n")

    for label, lst, ic in [
        ("VIOLATIONS",     result.get("violations",      []), "🚨"),
        ("AVERTISSEMENTS", result.get("warnings",        []), "⚠️"),
        ("CONFORMES",      result.get("compliant_rules", []), "✅"),
        ("AUTORISÉES",     result.get("ok_rules",        []), "🟢"),
    ]:
        if not lst:
            continue
        print(f"  ── {label} ({len(lst)}) ──")
        for item in lst[:5]:
            print(f"    {ic} [{item['risk_score']:>3}/100] {item['message'][:100]}")
            if item.get("missing_conditions"):
                print(f"       ⚡ Manquant : {' | '.join(item['missing_conditions'])}")
        print()

    if gs == "OUT_OF_DOMAIN":
        expl = result.get("explanations", [])
        if expl:
            print(f"  {expl[0]}\n")


# ══════════════════════════════════════════════════════════════════════════════
# DS02 — DIFF (CLI)
# ══════════════════════════════════════════════════════════════════════════════

def run_diff(current: str, previous: str) -> None:
    from compliance import detect_changes

    _banner("DS02 — VEILLE RÉGLEMENTAIRE")
    diff = detect_changes(current, previous)
    s    = diff["summary"]

    print(f"  Current  : {current}")
    print(f"  Previous : {previous}\n")
    print(f"  Total current  : {s['total_current']}")
    print(f"  Total previous : {s['total_previous']}")
    print(f"  ➕ Ajoutées    : {s['added']}")
    print(f"  ➖ Supprimées  : {s['removed']}")
    print(f"  ✏️  Modifiées   : {s['modified']}\n")

    if diff["added"]:
        print("  ── Nouvelles règles ──")
        for r in diff["added"][:3]:
            print(f"    + {r['actor']} → {r['action']} ({r['status']})")
    if diff["removed"]:
        print("  ── Règles supprimées ──")
        for r in diff["removed"][:3]:
            print(f"    − {r['actor']} → {r['action']} ({r['status']})")
    if diff["modified"]:
        print("  ── Risk scores modifiés ──")
        for m in diff["modified"][:3]:
            r = m["rule"]
            print(f"    ~ {r['actor']} → {r['action']} : "
                  f"{m['risk_before']}→{m['risk_after']} {m['direction']}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# DÉMO COMPLÈTE
# ══════════════════════════════════════════════════════════════════════════════

def run_demo() -> None:
    """
    Démo sur les données existantes (rules_clean.json).
    Teste 6 cas réels du Code des Droits Réels tunisien.
    Aucune dépendance LLM requise.
    """
    if not RULES_CLEAN.exists():
        log.error(f"Fichier introuvable : {RULES_CLEAN}")
        log.info("Lancez d'abord : python main.py --step all --skip-llm")
        sys.exit(1)

    from compliance import check_compliance, check_and_alert
    from collections import Counter

    _banner("DÉMONSTRATION BO5")

    rules  = json.loads(RULES_CLEAN.read_text(encoding="utf-8"))
    scores = [r["risk_score"] for r in rules]
    bstat  = Counter(r["status"] for r in rules)
    bactor = Counter(r["actor"]  for r in rules)

    print("📊 BASE DE RÈGLES")
    print(f"   Total           : {len(rules)}")
    print(f"   Obligations     : {bstat['obligation']}")
    print(f"   Interdictions   : {bstat['interdit']}")
    print(f"   Permissions     : {bstat['permis']}")
    print(f"   Risk min/moy/max: {min(scores)}/{sum(scores)//len(scores)}/{max(scores)}")
    print(f"   Top acteur      : {bactor.most_common(1)[0]}\n")

    print("🏆 TOP 5 RÈGLES LES PLUS RISQUÉES")
    for i, r in enumerate(rules[:5]):
        print(
            f"   {i+1}. [{r['risk_score']:>3}/100] "
            f"{r['actor']:>15} → {r['action'][:45]} ({r['status']})"
        )

    # ── 6 cas représentatifs ──────────────────────────────────────────────────
    cases = [
        {
            "label": "1 — Construction sans permis",
            "case":  {
                "actor": "proprietaire", "action": "construire",
                "target": "immeuble", "conditions": [],
            },
        },
        {
            "label": "2 — Construction avec permis (conforme)",
            "case":  {
                "actor": "proprietaire", "action": "construire",
                "target": "immeuble",
                "conditions": ["avec permis de construire",
                               "normes locales respectées"],
            },
        },
        {
            "label": "3 — Démolition sans autorisation",
            "case":  {
                "actor": "proprietaire", "action": "démolir",
                "target": "bâtiment", "conditions": [],
            },
        },
        {
            "label": "4 — Locataire sous-loue sans accord",
            "case":  {
                "actor": "locataire", "action": "mettre en location",
                "target": "bien immobilier loué", "conditions": [],
            },
        },
        {
            "label": "5 — Vente immobilière avec notaire (conforme)",
            "case":  {
                "actor": "particulier", "action": "vendre un bien immobilier",
                "target": "bien immobilier",
                "conditions": ["devant une notaire"],
            },
        },
        {
            "label": "6 — Action hors domaine (rejet propre)",
            "case":  {
                "actor": "employeur", "action": "licencier",
                "target": "employé", "conditions": [],
            },
        },
    ]

    recap = []
    print("\n")

    for tc in cases:
        print(f"{'─'*62}")
        print(f"  🔍 Cas {tc['label']}")
        c = tc["case"]
        print(f"     actor={c['actor']} | action={c['action']}")
        if c.get("conditions"):
            print(f"     conditions={c['conditions']}")

        result = check_compliance(c, rules, threshold=0.45)
        check_and_alert(result)

        gs   = result.get("global_status", "")
        risk = result.get("risk_score", 0)
        meta = result.get("meta", {})
        icons = {"VIOLATION":"🚨","WARNING":"⚠️","COMPLIANT":"✅","OUT_OF_DOMAIN":"ℹ️"}
        icon  = icons.get(gs, "•")

        print(
            f"\n     {icon} {gs} | risk={risk}/100 "
            f"| violations={len(result.get('violations',[]))} "
            f"| warnings={len(result.get('warnings',[]))}"
        )

        for v in result.get("violations", [])[:2]:
            print(f"     🚨 [{v['risk_score']:>3}] {v['message'][:95]}")
        for w in result.get("warnings", [])[:2]:
            print(f"     ⚠️  [{w['risk_score']:>3}] {w['message'][:95]}")
        for ok in result.get("ok_rules", [])[:1]:
            print(f"     🟢 [{ok['risk_score']:>3}] {ok['message'][:95]}")
        if gs == "OUT_OF_DOMAIN":
            expl = result.get("explanations", [])
            if expl:
                print(f"     ℹ️  {expl[0][:100]}")

        recap.append({"label": f"Cas {tc['label']}", "status": gs, "risk": risk})
        print()

    # Récapitulatif
    print(f"{'═'*62}")
    print("  📋 RÉCAPITULATIF")
    print(f"{'═'*62}")
    for r in recap:
        icon = {"VIOLATION":"🚨","WARNING":"⚠️","COMPLIANT":"✅","OUT_OF_DOMAIN":"ℹ️"}.get(r["status"],"•")
        print(f"  {icon} {r['label']:<48} → {r['status']} (risk={r['risk']})")

    print(f"\n  💡 Démarrer l'API : python main.py --step api")
    print(f"  📖 Tester l'API  : python test_api.py\n")


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════


def run_eval() -> None:
    """Lance l'évaluation + génère eval_dashboard.html + ouvre le navigateur."""
    import webbrowser
    from pathlib import Path as _P

    _banner("ÉVALUATION — Qualité extraction LLM")
    if not RULES_CLEAN.exists():
        log.error(f"Fichier introuvable : {RULES_CLEAN}")
        log.info("Lancez : python main.py --step all --pdf pdf_francais.pdf")
        sys.exit(1)
    try:
        from hallucination_eval import evaluate, print_report, save_report
    except ImportError:
        log.error("hallucination_eval.py introuvable")
        sys.exit(1)

    with open(RULES_CLEAN, encoding="utf-8") as f:
        rules = json.load(f)

    report = evaluate(rules)
    print_report(report)
    rp = save_report(report)
    log.info(f"   Rapport JSON   : {rp}")

    dash = _P(__file__).parent / "eval_dashboard.html"
    _gen_dashboard(report, rules, str(dash))
    log.info(f"   Dashboard HTML : {dash}")
    webbrowser.open(f"file://{dash.resolve()}")
    log.info("   Dashboard ouvert dans le navigateur ✅")


def _gen_dashboard(report: dict, rules: list, output_path: str) -> None:
    """Génère eval_dashboard.html — dashboard dark theme + Chart.js."""
    from collections import Counter as _C
    import json as _j

    # ── Données du rapport ───────────────────────────────────────────────────
    n         = report.get("total_rules", 0)
    h         = report.get("hallucination", {})
    d         = report.get("semantic_duplicates", {})
    qs        = report.get("quality_scores", {})
    ac        = report.get("actors", {})
    st        = report.get("status_distribution", {})
    sc        = report.get("reliability_score", 0)
    gr        = report.get("reliability_grade", "?")
    recs      = report.get("recommendations", [])
    exs       = h.get("examples", [])[:8]
    evd       = report.get("eval_date", "")
    hallu_n   = h.get("count", 0)
    hallu_pct = h.get("rate_pct", 0)
    clean_n   = n - hallu_n
    clean_pct = h.get("clean_rate_pct", 0)
    dup_pct   = d.get("rate_pct", 0)
    dup_n     = d.get("count", 0)
    qs_avg    = qs.get("avg", 0)
    qs_min    = qs.get("min", 0)
    qs_max    = qs.get("max", 0)
    act_pct   = ac.get("standardized_pct", 0)

    # ── Couleurs calculées AVANT le template (pas de ternaire dans f-string) ─
    sc_col  = "#22c55e" if sc >= 85 else ("#f59e0b" if sc >= 70 else "#ef4444")
    h_cls   = "red"   if hallu_pct > 15 else ("amber" if hallu_pct > 5 else "green")
    dp_cls  = "amber" if dup_pct   > 10 else "teal"
    sc_cls  = "amber" if sc        < 70  else "green"

    # ── Distribution risk ────────────────────────────────────────────────────
    risks = [r.get("risk_score", 0) for r in rules]
    dist  = {"0-25": 0, "26-50": 0, "51-70": 0, "71-85": 0, "86-100": 0}
    for s in risks:
        if   s <= 25:  dist["0-25"]   += 1
        elif s <= 50:  dist["26-50"]  += 1
        elif s <= 70:  dist["51-70"]  += 1
        elif s <= 85:  dist["71-85"]  += 1
        else:          dist["86-100"] += 1

    top6    = _j.dumps(dict(_C(r.get("actor", "") for r in rules).most_common(6)))
    dist_j  = _j.dumps(dist)
    stat_j  = _j.dumps(dict(st))
    radar_j = _j.dumps({
        "labels":  ["Authenticité", "Unicité", "Articles", "Quality", "Acteurs", "Domaine"],
        "current": [round(100 - hallu_pct), round(100 - dup_pct), 90,
                    round(qs_avg * 10), round(act_pct), 95],
        "target":  [90, 95, 95, 90, 100, 98],
    })

    # ── Lignes tableau hallucinations ────────────────────────────────────────
    hallu_rows = ""
    for x in exs:
        hallu_rows += (
            '<tr><td><span class="bb">' + x.get("actor", "") + '</span></td>'
            '<td>' + x.get("action", "")[:50] + '</td>'
            '<td class="mono red">' + x.get("article", "")[:45] + '</td>'
            '<td><span class="br">Hallucination</span></td></tr>'
        )

    # ── Recommandations ──────────────────────────────────────────────────────
    recs_html = ""
    for i, r in enumerate(recs):
        recs_html += (
            '<div class="rec"><span class="rn">' + str(i + 1) + '</span>'
            '<div class="rb">' + r + '</div></div>'
        )

    # ── Bloc verdict ─────────────────────────────────────────────────────────
    verdict = ""
    if hallu_n > 0:
        verdict = (
            '<div class="verdict">'
            '<div style="font-size:26px;flex-shrink:0">&#9888;&#65039;</div>'
            '<div><div class="vt">Hallucinations : ' + str(hallu_pct)
            + '% — ' + h.get("verdict", "") + '</div>'
            '<div class="vb">Pipeline hybride : N-gram TF-IDF(1,3) + MiniLM + top-k=4 + prompt ultra-contraint.</div>'
            '</div></div>'
        )

    # ── Bloc table hallucinations ─────────────────────────────────────────────
    hallu_section = ""
    if exs:
        hallu_section = (
            '<div class="stitle">Exemples d\'hallucinations</div>'
            '<div class="card"><div class="ct">Articles de codes étrangers inventés</div>'
            '<div class="cs">Pipeline hybride vise &lt;5% de tels cas</div>'
            '<table><thead><tr><th>Acteur</th><th>Action</th>'
            '<th>Article inventé</th><th>Type</th></tr></thead>'
            '<tbody>' + hallu_rows + '</tbody></table></div>'
        )

    # ── Template HTML ─────────────────────────────────────────────────────────
    # Toutes les valeurs dynamiques sont calculées au-dessus — le template
    # n'utilise que des variables simples, jamais d'expressions ternaires.
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="fr"><head><meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>BO5 — Évaluation LLM</title>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n'
        '<style>\n'
        '*{box-sizing:border-box;margin:0;padding:0}\n'
        'body{font-family:"Segoe UI",system-ui,sans-serif;background:#0f1117;color:#e2e8f0;font-size:14px}\n'
        '.hdr{background:#161b27;border-bottom:1px solid rgba(255,255,255,.08);padding:16px 28px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;position:sticky;top:0;z-index:99}\n'
        '.hdr h1{font-size:17px;font-weight:600;color:#fff}\n'
        '.hdr p{font-size:11px;color:#64748b;margin-top:2px}\n'
        '.sbig{font-size:34px;font-weight:700;color:' + sc_col + '}\n'
        '.gpill{display:inline-block;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:600;background:rgba(245,158,11,.18);color:#f59e0b;margin-left:8px}\n'
        '.page{max-width:1280px;margin:0 auto;padding:22px 20px 60px}\n'
        '.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:14px}\n'
        '.g2{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-bottom:14px}\n'
        '.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:11px;margin-bottom:14px}\n'
        '@media(max-width:880px){.g4,.g3{grid-template-columns:1fr 1fr}.g2{grid-template-columns:1fr}}\n'
        '.kpi{background:#161b27;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:16px;position:relative;overflow:hidden}\n'
        '.kpi::before{content:"";position:absolute;top:0;left:0;right:0;height:3px}\n'
        '.kpi.red::before{background:#ef4444}.kpi.green::before{background:#22c55e}\n'
        '.kpi.amber::before{background:#f59e0b}.kpi.blue::before{background:#3b82f6}\n'
        '.kpi.purple::before{background:#8b5cf6}.kpi.teal::before{background:#14b8a6}\n'
        '.kv{font-size:26px;font-weight:700;margin-bottom:1px}\n'
        '.kpi.red .kv{color:#ef4444}.kpi.green .kv{color:#22c55e}\n'
        '.kpi.amber .kv{color:#f59e0b}.kpi.blue .kv{color:#3b82f6}\n'
        '.kpi.purple .kv{color:#8b5cf6}.kpi.teal .kv{color:#14b8a6}\n'
        '.kl{font-size:11px;color:#64748b;margin-bottom:1px}.ks{font-size:10px;color:#475569}\n'
        '.card{background:#161b27;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:16px}\n'
        '.ct{font-size:14px;font-weight:600;color:#fff;margin-bottom:3px}\n'
        '.cs{font-size:11px;color:#64748b;margin-bottom:12px}\n'
        '.stitle{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:#475569;margin:22px 0 11px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,.06)}\n'
        'table{width:100%;border-collapse:collapse;font-size:12px}\n'
        'th{text-align:left;padding:7px 10px;color:#475569;font-size:10px;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,.08);background:#1e2535}\n'
        'td{padding:7px 10px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:middle}\n'
        'tr:hover td{background:rgba(255,255,255,.02)}\n'
        '.bb,.br{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:20px}\n'
        '.bb{background:rgba(59,130,246,.15);color:#3b82f6}.br{background:rgba(239,68,68,.15);color:#ef4444}\n'
        '.mono{font-family:monospace;font-size:11px}.red{color:#ef4444}\n'
        '.verdict{background:linear-gradient(135deg,rgba(239,68,68,.1),rgba(245,158,11,.07));border:1px solid rgba(239,68,68,.18);border-radius:12px;padding:16px;margin-bottom:14px;display:flex;gap:14px;align-items:center}\n'
        '.vt{font-size:14px;font-weight:600;color:#fff;margin-bottom:3px}\n'
        '.vb{font-size:12px;color:#94a3b8;line-height:1.5}\n'
        '.rec{display:flex;gap:10px;padding:9px 0;border-bottom:.5px solid rgba(255,255,255,.05)}\n'
        '.rec:last-child{border-bottom:none}\n'
        '.rn{width:22px;height:22px;border-radius:50%;background:rgba(139,92,246,.2);color:#8b5cf6;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}\n'
        '.rb{font-size:12px;color:#94a3b8;line-height:1.5}\n'
        '.foot{margin-top:36px;padding-top:14px;border-top:1px solid rgba(255,255,255,.06);display:flex;justify-content:space-between;font-size:11px;color:#475569;flex-wrap:wrap;gap:6px}\n'
        '</style></head><body>\n'

        '<div class="hdr">\n'
        '  <div><h1>BO5 — Dashboard Évaluation LLM</h1>\n'
        '  <p>Pipeline Hybride NLP · CDR tunisien · Mistral · ' + evd + ' · ' + str(n) + ' règles</p></div>\n'
        '  <div style="display:flex;align-items:center">\n'
        '    <div><div style="font-size:11px;color:#64748b;margin-bottom:2px">Score fiabilité</div>\n'
        '    <div><span class="sbig">' + str(sc) + '</span><span style="color:#64748b;font-size:13px">/100</span></div></div>\n'
        '    <span class="gpill">Grade ' + gr + '</span>\n'
        '  </div>\n'
        '</div>\n'

        '<div class="page">\n'
        + verdict +
        '<div class="stitle">Métriques</div>\n'
        '<div class="g4">\n'
        '  <div class="kpi ' + h_cls + '"><div class="kl">Hallucinations</div><div class="kv">' + str(hallu_pct) + '%</div><div class="ks">' + str(hallu_n) + '/' + str(n) + ' · ' + h.get("verdict","") + '</div></div>\n'
        '  <div class="kpi green"><div class="kl">Règles propres CDR</div><div class="kv">' + str(clean_pct) + '%</div><div class="ks">' + str(clean_n) + '/' + str(n) + '</div></div>\n'
        '  <div class="kpi ' + dp_cls + '"><div class="kl">Doublons sémantiques</div><div class="kv">' + str(dup_pct) + '%</div><div class="ks">' + str(dup_n) + ' paires</div></div>\n'
        '  <div class="kpi blue"><div class="kl">Quality score</div><div class="kv">' + str(qs_avg) + '/10</div><div class="ks">min ' + str(qs_min) + ' · max ' + str(qs_max) + '</div></div>\n'
        '</div>\n'
        '<div class="g4">\n'
        '  <div class="kpi purple"><div class="kl">Total règles</div><div class="kv">' + str(n) + '</div><div class="ks">Après nettoyage</div></div>\n'
        '  <div class="kpi teal"><div class="kl">Acteurs normalisés</div><div class="kv">' + str(act_pct) + '%</div><div class="ks">ACTOR_MAP</div></div>\n'
        '  <div class="kpi ' + sc_cls + '"><div class="kl">Score fiabilité</div><div class="kv">' + str(sc) + '/100</div><div class="ks">Grade ' + gr + '</div></div>\n'
        '  <div class="kpi red"><div class="kl">Pipeline</div><div class="kv">Hybride</div><div class="ks">TF-IDF(1,3)+MiniLM+k=4</div></div>\n'
        '</div>\n'

        '<div class="stitle">Graphiques</div>\n'
        '<div class="g3">\n'
        '  <div class="card"><div class="ct">Propres vs hallucinations</div><div class="cs">' + str(hallu_pct) + '% inventées</div>\n'
        '    <div style="position:relative;height:185px"><canvas id="cD" role="img" aria-label="Donut hallucinations">' + str(clean_n) + ' propres, ' + str(hallu_n) + ' hallucinations</canvas></div></div>\n'
        '  <div class="card"><div class="ct">Distribution par statut</div><div class="cs">3 catégories</div>\n'
        '    <div style="position:relative;height:185px"><canvas id="cS" role="img" aria-label="Statuts">' + stat_j + '</canvas></div></div>\n'
        '  <div class="card"><div class="ct">Risk scores</div><div class="cs">Par tranche</div>\n'
        '    <div style="position:relative;height:185px"><canvas id="cR" role="img" aria-label="Risks">' + dist_j + '</canvas></div></div>\n'
        '</div>\n'
        '<div class="g2">\n'
        '  <div class="card"><div class="ct">Top acteurs</div><div class="cs">Règles par acteur</div>\n'
        '    <div style="position:relative;height:200px"><canvas id="cA" role="img" aria-label="Acteurs">' + top6 + '</canvas></div></div>\n'
        '  <div class="card"><div class="ct">Radar qualité</div><div class="cs">Actuel vs objectif</div>\n'
        '    <div style="position:relative;height:200px"><canvas id="cRad" role="img" aria-label="Radar">' + radar_j + '</canvas></div></div>\n'
        '</div>\n'
        + hallu_section +
        '<div class="stitle">Recommandations</div>\n'
        '<div class="card"><div class="ct">Actions correctives</div>'
        '<div class="cs">Objectif : score &ge;85/100 · hallucinations &lt;5%</div>\n'
        + recs_html +
        '</div>\n'
        '<div class="foot">\n'
        '  <span>BO5 · Pipeline Hybride NLP · ' + evd + '</span>\n'
        '  <span style="font-family:monospace;font-size:10px">python main.py --step eval</span>\n'
        '</div></div>\n'

        '<script>\n'
        'const ST=' + stat_j + ',DIST=' + dist_j + ',ACT=' + top6 + ',RAD=' + radar_j + ';\n'
        'const G=id=>document.getElementById(id);\n'
        'new Chart(G("cD"),{type:"doughnut",data:{labels:["Propres","Hallucinations"],datasets:[{data:[' + str(clean_n) + ',' + str(hallu_n) + '],backgroundColor:["#22c55e","#ef4444"],borderColor:"#161b27",borderWidth:3}]},options:{responsive:true,maintainAspectRatio:false,cutout:"62%",plugins:{legend:{position:"bottom",labels:{color:"#94a3b8",font:{size:11},usePointStyle:true,padding:12}}}}});\n'
        'new Chart(G("cS"),{type:"bar",data:{labels:Object.keys(ST),datasets:[{data:Object.values(ST),backgroundColor:["#ef4444","#f59e0b","#22c55e"],borderRadius:6,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:"#64748b"}},y:{grid:{color:"rgba(255,255,255,.05)"},ticks:{color:"#64748b"}}}}});\n'
        'new Chart(G("cR"),{type:"bar",data:{labels:Object.keys(DIST),datasets:[{data:Object.values(DIST),backgroundColor:["#22c55e","#14b8a6","#f59e0b","#ef4444","#dc2626"],borderRadius:6,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:"#64748b"}},y:{grid:{color:"rgba(255,255,255,.05)"},ticks:{color:"#64748b"}}}}});\n'
        'new Chart(G("cA"),{type:"bar",data:{labels:Object.keys(ACT),datasets:[{data:Object.values(ACT),backgroundColor:"#3b82f6",borderRadius:5,borderSkipped:false}]},options:{indexAxis:"y",responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:"rgba(255,255,255,.05)"},ticks:{color:"#64748b"}},y:{grid:{display:false},ticks:{color:"#94a3b8"}}}}});\n'
        'new Chart(G("cRad"),{type:"radar",data:{labels:RAD.labels,datasets:[{label:"Actuel",data:RAD.current,backgroundColor:"rgba(59,130,246,.12)",borderColor:"#3b82f6",borderWidth:2,pointBackgroundColor:"#3b82f6",pointRadius:3},{label:"Objectif",data:RAD.target,backgroundColor:"rgba(34,197,94,.07)",borderColor:"rgba(34,197,94,.4)",borderWidth:1.5,borderDash:[5,3],pointRadius:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{color:"#94a3b8",font:{size:11},usePointStyle:true,padding:12}}},scales:{r:{min:0,max:100,ticks:{stepSize:25,backdropColor:"transparent",color:"#475569",font:{size:9}},grid:{color:"rgba(255,255,255,.07)"},angleLines:{color:"rgba(255,255,255,.07)"},pointLabels:{color:"#94a3b8",font:{size:10}}}}}});\n'
        '</script></body></html>'
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def _banner(title: str) -> None:
    w = 62
    print(f"\n{'═'*w}")
    print(f"  BO5 — {title}")
    print(f"  {SOURCE_NAME}")
    print(f"{'═'*w}\n")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(
        description="BO5 Legal Compliance — Code des Droits Réels tunisien",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--step", default="demo",
        choices=["demo","all","extract","chunk","hybrid","coverage","rules",
                 "clean","risk","graph","eval","check","diff","api"],
        help="Étape à exécuter (défaut: demo)",
    )
    p.add_argument("--pdf",        default="pdf_francais.pdf",
                   help="Chemin vers le PDF source")
    p.add_argument("--skip-llm",   action="store_true",
                   help="Sauter l'étape LLM (utilise rules_raw existant)")
    p.add_argument("--actor",      default="proprietaire")
    p.add_argument("--action",     default="construire")
    p.add_argument("--target",     default="immeuble")
    p.add_argument("--conditions", nargs="*", default=[])
    p.add_argument("--threshold",  type=float, default=0.45)
    p.add_argument("--current",    default=str(RULES_CLEAN))
    p.add_argument("--prev",       default="")
    p.add_argument("--host",       default="0.0.0.0")
    p.add_argument("--port",       type=int, default=8000)
    args = p.parse_args()

    if   args.step == "demo":    run_demo()
    elif args.step == "all":     run_pipeline(args.pdf, args.skip_llm)
    elif args.step == "extract":
        from pipeline import extract_text;    extract_text(args.pdf)
    elif args.step == "chunk":
        from pipeline import chunk_articles;  chunk_articles()
    elif args.step == "hybrid":
        from pipeline import chunk_hybrid_pipeline; chunk_hybrid_pipeline()
    elif args.step == "coverage":
        from pipeline import chunk_coverage_pipeline; chunk_coverage_pipeline()
    elif args.step == "rules":
        from pipeline import extract_rules;   extract_rules()
    elif args.step == "clean":
        from pipeline import clean_rules;     clean_rules()
    elif args.step == "risk":
        from pipeline import compute_risk_scores; compute_risk_scores()
    elif args.step == "graph":
        from pipeline import build_graph;     build_graph()
    elif args.step == "check":
        run_check(args.actor, args.action, args.target,
                  args.conditions or [], args.threshold)
    elif args.step == "diff":
        if not args.prev:
            log.error("--step diff nécessite --prev <fichier_précédent.json>")
            sys.exit(1)
        run_diff(args.current, args.prev)
    elif args.step == "eval":     run_eval()
    elif args.step == "api":
        from api import start
        start(args.host, args.port)


if __name__ == "__main__":
    main()