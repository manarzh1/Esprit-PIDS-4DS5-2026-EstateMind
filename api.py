"""
api.py
─────────────────────────────────────────────────────────────────
API REST BO5 — http.server, zéro dépendance externe.

ENDPOINTS :
  POST /check-compliance  → DS04
  POST /diff              → DS02
  GET  /risk-summary      → DS03
  GET  /top-risks         → DS03
  GET  /rules             → exploration filtrée + paginée
  GET  /graph-stats       → DS01
  GET  /health            → état du système

USAGE :
  python api.py
  python api.py --port 9000
"""

import json, logging
from http.server    import HTTPServer, BaseHTTPRequestHandler
from urllib.parse   import urlparse, parse_qs
from pathlib        import Path
from collections    import Counter
from typing         import Optional
import argparse

from config import (
    RULES_CLEAN, NEO4J_DIR, LOG_DIR,
    API_HOST, API_PORT, SOURCE_NAME,
)
from compliance import (check_compliance, detect_changes, check_and_alert,
                        is_urbanisme_question, compute_urbanisme_risk)
from nlp_parser import parse_natural
from chatbot    import chat as chatbot_chat
try:
    from generate_report import generate_pdf
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False
from alerts import load_alerts_config, save_alerts_config, get_alerts_history

_fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
log = logging.getLogger("api")
log.setLevel(logging.INFO)
if not log.handlers:
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "api.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)

# ── Cache en mémoire ───────────────────────────────────────────────────────────
_RULES: Optional[list[dict]] = None
_GRAPH: Optional[dict]       = None


def _load_rules() -> list[dict]:
    global _RULES
    if _RULES is None and RULES_CLEAN.exists():
        with open(RULES_CLEAN, encoding="utf-8") as f:
            _RULES = json.load(f)
    return _RULES or []


def _load_graph() -> dict:
    global _GRAPH
    if _GRAPH is None:
        p = NEO4J_DIR / "graph_report.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                _GRAPH = json.load(f)
    return _GRAPH or {}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

def _h_check_compliance(body: dict) -> tuple[int, dict]:
    """
    POST /check-compliance
    ─────────────────────
    Input:
        {
            "actor":       "proprietaire",
            "action":      "construire",
            "target":      "immeuble",
            "conditions":  ["avec permis de construire"],
            "threshold":   0.45,
            "max_results": 10
        }
    """
    if not body.get("actor") or not body.get("action"):
        return 400, {"error": "Champs requis : 'actor' et 'action'"}

    user_case = {
        "actor":      str(body["actor"]).strip().lower(),
        "action":     str(body["action"]).strip().lower(),
        "target":     str(body.get("target", "")).strip().lower(),
        "conditions": body.get("conditions", []),
    }
    result = check_compliance(
        user_case, _load_rules(),
        threshold   = float(body.get("threshold",   0.45)),
        max_results = int(body.get("max_results",   10)),
    )
    check_and_alert(result)
    return 200, result


def _h_diff(body: dict) -> tuple[int, dict]:
    """
    POST /diff
    ──────────
    Input: { "current_path": "...", "previous_path": "...", "out_path": "..." }
    """
    current  = body.get("current_path",  str(RULES_CLEAN))
    previous = body.get("previous_path", "")
    if not previous:
        return 400, {"error": "Champ requis : 'previous_path'"}
    for p, label in [(current, "current_path"), (previous, "previous_path")]:
        if not Path(p).exists():
            return 400, {"error": f"Fichier introuvable : {label} = {p}"}
    return 200, detect_changes(current, previous, body.get("out_path"))


def _h_risk_summary(params: dict) -> tuple[int, dict]:
    """GET /risk-summary"""
    rules = _load_rules()
    if not rules:
        return 503, {"error": "Données non disponibles. Lancez le pipeline."}

    scores   = [r.get("risk_score", 0) for r in rules]
    by_stat  = Counter(r["status"]           for r in rules)
    by_prio  = Counter(r.get("priority", "") for r in rules)
    by_actor = Counter(r["actor"]            for r in rules)

    dist = {"0-25": 0, "26-50": 0, "51-70": 0, "71-85": 0, "86-100": 0}
    for s in scores:
        if   s <= 25:  dist["0-25"]   += 1
        elif s <= 50:  dist["26-50"]  += 1
        elif s <= 70:  dist["51-70"]  += 1
        elif s <= 85:  dist["71-85"]  += 1
        else:          dist["86-100"] += 1

    return 200, {
        "source":      SOURCE_NAME,
        "total_rules": len(rules),
        "by_status":   dict(by_stat),
        "by_priority": dict(by_prio),
        "top_actors":  dict(by_actor.most_common(8)),
        "risk_stats": {
            "min":             min(scores),
            "max":             max(scores),
            "avg":             round(sum(scores) / len(scores), 1),
            "high_risk_count": sum(1 for s in scores if s >= 70),
            "distribution":    dist,
        },
    }


def _h_top_risks(params: dict) -> tuple[int, dict]:
    """GET /top-risks?n=10&status=interdit&actor=proprietaire"""
    rules  = _load_rules()
    n      = int(params.get("n",      ["10"])[0])
    status = params.get("status", [None])[0]
    actor  = params.get("actor",  [None])[0]

    filtered = [
        r for r in rules
        if (not status or r["status"] == status)
        and (not actor  or actor.lower() in r["actor"].lower())
    ]
    top = sorted(filtered, key=lambda r: -r.get("risk_score", 0))[:n]

    return 200, {
        "filters":   {"n": n, "status": status, "actor": actor},
        "count":     len(top),
        "top_risks": [
            {
                "rank":          i + 1,
                "risk_score":    r.get("risk_score",    0),
                "quality_score": r.get("quality_score", 0),
                "priority":      r.get("priority",      "medium"),
                "actor":         r["actor"],
                "action":        r["action"],
                "target":        r.get("target", ""),
                "status":        r["status"],
                "conditions":    r.get("conditions", []),
                "article":       r.get("article", ""),
            }
            for i, r in enumerate(top)
        ],
    }


def _h_rules(params: dict) -> tuple[int, dict]:
    """GET /rules?actor=&status=&action=&limit=20&offset=0"""
    rules  = _load_rules()
    actor  = params.get("actor",  [None])[0]
    status = params.get("status", [None])[0]
    action = params.get("action", [None])[0]
    limit  = int(params.get("limit",  ["20"])[0])
    offset = int(params.get("offset", ["0"])[0])

    filtered = [
        r for r in rules
        if (not actor  or actor.lower()  in r["actor"].lower())
        and (not status or r["status"]   == status)
        and (not action or action.lower() in r["action"].lower())
    ]
    page = filtered[offset: offset + limit]

    return 200, {
        "total":  len(filtered),
        "limit":  limit,
        "offset": offset,
        "rules": [
            {
                "actor":         r["actor"],
                "action":        r["action"],
                "target":        r.get("target", ""),
                "status":        r["status"],
                "conditions":    r.get("conditions", []),
                "article":       r.get("article", ""),
                "risk_score":    r.get("risk_score",    0),
                "quality_score": r.get("quality_score", 0),
                "priority":      r.get("priority",      "medium"),
            }
            for r in page
        ],
    }


def _h_graph_stats(params: dict) -> tuple[int, dict]:
    """GET /graph-stats"""
    g = _load_graph()
    if not g:
        return 503, {
            "error": "Graph non construit.",
            "hint":  "Lancez : python main.py --step graph",
        }
    csv_counts: dict[str, int] = {}
    for name in ["actors", "actions", "targets", "conditions", "articles"]:
        p = NEO4J_DIR / f"{name}.csv"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                csv_counts[name] = max(0, sum(1 for _ in f) - 1)

    return 200, {
        "source":        SOURCE_NAME,
        "build_date":    g.get("build_date", ""),
        "nodes":         g.get("nodes", {}),
        "relationships": g.get("relationships", {}),
        "csv_counts":    csv_counts,
        "cypher_file":   str(NEO4J_DIR / "graph_import.cypher"),
        "tip": "Importez graph_import.cypher dans Neo4j Browser.",
    }


def _h_health(params: dict) -> tuple[int, dict]:
    """GET /health"""
    rules = _load_rules()
    g     = _load_graph()
    ok    = bool(rules)
    return (200 if ok else 503), {
        "status":  "ok" if ok else "degraded",
        "source":  SOURCE_NAME,
        "version": "1.0.0",
        "components": {
            "rules_clean":     {"ok": RULES_CLEAN.exists(), "count": len(rules)},
            "knowledge_graph": {"ok": bool(g)},
            "neo4j_export":    {"ok": NEO4J_DIR.exists()},
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTEUR HTTP
# ══════════════════════════════════════════════════════════════════════════════


def _h_analyze_text(body: dict) -> tuple[int, dict]:
    """POST /analyze-text — NLP + conformite + RAG hybride"""
    text = body.get("text", "").strip()
    if not text:
        return 400, {"error": "Champ requis : text"}
    use_llm   = body.get("use_llm", True)
    threshold = float(body.get("threshold", 0.45))
    parsed = parse_natural(text, use_llm=use_llm)
    user_case = {
        "actor":      parsed.get("actor", ""),
        "action":     parsed.get("action", ""),
        "target":     parsed.get("target", ""),
        "conditions": parsed.get("conditions", []),
    }
    compliance = check_compliance(user_case, _load_rules(), threshold=threshold)
    rag_fallback = None
    status_needs_rag = compliance.get("global_status") == "UNKNOWN"
    urbanisme_needed = is_urbanisme_question(user_case)
    cdr_answered = compliance.get("global_status") in ("COMPLIANT","VIOLATION","WARNING")
    conds_str = " ".join(user_case.get("conditions", [])).lower()
    has_negative = any(w in conds_str for w in ["sans permis","sans autorisation","non constructible"])
    skip_rag = (compliance.get("global_status") == "OUT_OF_DOMAIN" and not urbanisme_needed)                or (cdr_answered and not has_negative)
    if not skip_rag and (status_needs_rag or urbanisme_needed):
        try:
            from rag import search, format_context
            sources = ["URBANISME"] if urbanisme_needed else ["CDR"]
            rag_res = search(f"{user_case['actor']} {user_case['action']} {user_case['target']}", sources=sources, top_k=3)
            if rag_res:
                risk_data = compute_urbanisme_risk(rag_res, user_case)
                expl = format_context(rag_res, max_chars=500)
                rag_fallback = {
                    "used": True, "source": risk_data.get("source","URBANISME"),
                    "law": risk_data.get("law",""), "articles": risk_data.get("articles",[]),
                    "risk_score": risk_data.get("risk_score",0), "explanation": expl,
                }
                if risk_data.get("risk_score",0) > compliance.get("risk_score",0):
                    compliance["risk_score"]    = risk_data["risk_score"]
                    compliance["global_status"] = (
                        "VIOLATION" if risk_data["status"]=="interdit"
                        else "WARNING" if risk_data["status"]=="obligation"
                        else compliance["global_status"])
        except Exception as e:
            log.warning(f"RAG erreur : {e}")
    check_and_alert(compliance)
    try:
        answer = chatbot_chat(text, rag_context=rag_fallback.get("explanation","") if rag_fallback else "")
        expl = answer.get("answer","")
    except Exception:
        expl = ""
    return 200, {
        "parsed": parsed, "compliance": compliance,
        "rag_fallback": rag_fallback, "explanations": [expl] if expl else [],
    }


def _h_legal_risk(body: dict) -> tuple[int, dict]:
    """POST /legal-risk — score pour Decision Copilot"""
    text = body.get("text","")
    if not text:
        actor  = body.get("actor","")
        action = body.get("action","")
        target = body.get("target","")
        text   = f"{actor} {action} {target}".strip()
    if not text:
        return 400, {"error": "Champ requis : text ou actor+action+target"}
    _, result = _h_analyze_text({"text": text, "use_llm": True})
    c    = result.get("compliance", {})
    risk = c.get("risk_score", 0)
    st   = c.get("global_status","UNKNOWN")
    level = "HIGH" if risk>=70 else "MEDIUM" if risk>=40 else "LOW"
    return 200, {
        "legal_risk_score": risk, "status": st, "risk_level": level,
        "copilot_summary": f"Risque juridique {level} ({risk}/100) — {st}",
        "articles": [v.get("article","") for v in c.get("violations",[])],
        "recommendation": "Consultez un notaire." if risk>=70 else "Situation à surveiller." if risk>=40 else "Situation conforme.",
    }


def _h_chat(body: dict) -> tuple[int, dict]:
    """POST /chat — chatbot juridique"""
    question = body.get("question","").strip()
    if not question:
        return 400, {"error": "Champ requis : question"}
    rag_ctx = ""
    if body.get("use_rag", True):
        try:
            from rag import search, format_context
            res = search(question, sources=["CDR","URBANISME"], top_k=3)
            if res: rag_ctx = format_context(res, max_chars=600)
        except Exception:
            pass
    result = chatbot_chat(question, rag_context=rag_ctx)
    return 200, result


def _h_rag_search(body: dict) -> tuple[int, dict]:
    """POST /rag-search"""
    query = body.get("query","").strip()
    if not query: return 400, {"error": "Champ requis : query"}
    try:
        from rag import search, format_context
        sources = body.get("sources", ["CDR","URBANISME"])
        top_k   = int(body.get("top_k", 5))
        results = search(query, sources=sources, top_k=top_k)
        return 200, {"query": query, "results": results, "context": format_context(results)}
    except Exception as e:
        return 500, {"error": str(e)}


def _h_generate_report(body: dict) -> tuple[int, dict]:
    """POST /generate-report"""
    situation    = body.get("situation","").strip()
    destinataire = body.get("destinataire","Usage personnel")
    email        = body.get("email","")
    if not situation: return 400, {"error": "Champ requis : situation"}
    if not _HAS_REPORTLAB: return 500, {"error": "pip install reportlab"}
    try:
        _, res = _h_analyze_text({"text": situation, "use_llm": True})
        compliance = res.get("compliance", {"global_status":"UNKNOWN","risk_score":0,"violations":[],"warnings":[]})
        rag = res.get("rag_fallback")
        if rag: compliance["rag_fallback"] = rag
        pdf_path = generate_pdf(situation=situation, compliance_result=compliance, destinataire=destinataire)
        if isinstance(pdf_path, list): pdf_path = pdf_path[0] if pdf_path else "reports/rapport.pdf"
        pdf_path = str(pdf_path)
        filename = Path(pdf_path).name
        return 200, {"success": True, "pdf_path": pdf_path, "filename": filename,
                     "status": compliance.get("global_status"), "risk": compliance.get("risk_score",0)}
    except Exception as e:
        log.exception(f"generate_report: {e}")
        return 500, {"error": str(e)}


def _h_send_email(body: dict) -> tuple[int, dict]:
    """POST /send-email"""
    import smtplib, ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    from email.mime.base      import MIMEBase
    from email                import encoders
    to      = body.get("to","").strip()
    subject = body.get("subject","Rapport juridique Estate Mind")
    txt     = body.get("body","Votre rapport est disponible.")
    fname   = body.get("attachment","")
    if not to or "@" not in to: return 400, {"error": "Email invalide"}
    try:
        import config as cfg
        SMTP_HOST  = getattr(cfg,"SMTP_HOST","smtp.gmail.com")
        SMTP_PORT  = getattr(cfg,"SMTP_PORT",587)
        SMTP_USER  = getattr(cfg,"SMTP_USER","")
        SMTP_PASS  = getattr(cfg,"SMTP_PASS","")
        FROM_EMAIL = getattr(cfg,"FROM_EMAIL",SMTP_USER)
    except Exception:
        return 500, {"error": "config.py manquant"}
    if not SMTP_USER or not SMTP_PASS:
        return 200, {"success": True, "simulated": True, "to": to}
    try:
        msg = MIMEMultipart()
        msg["From"] = FROM_EMAIL; msg["To"] = to; msg["Subject"] = subject
        msg.attach(MIMEText(txt, "plain", "utf-8"))
        if fname:
            p = Path("reports") / Path(fname).name
            if p.exists():
                with open(p,"rb") as f:
                    part = MIMEBase("application","octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={p.name}")
                    msg.attach(part)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls(context=ctx); s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, to, msg.as_string())
        log.info(f"Email envoyé à {to}")
        return 200, {"success": True, "to": to}
    except Exception as e:
        log.warning(f"SMTP erreur : {e}")
        return 500, {"error": str(e)}


def _h_configure_alerts(body: dict) -> tuple[int, dict]:
    """POST /configure-alerts"""
    email = body.get("email","").strip()
    if not email: return 400, {"error": "Champ requis : email"}
    config = load_alerts_config()
    config["email"]        = email
    config["cdr_changes"]  = bool(body.get("cdr_changes",True))
    config["catu_changes"] = bool(body.get("catu_changes",True))
    config["high_risk"]    = bool(body.get("high_risk",True))
    config["new_rules"]    = bool(body.get("new_rules",False))
    saved = save_alerts_config(config)
    return 200, {"success": True, "config": saved}


def _h_get_alerts(params: dict) -> tuple[int, dict]:
    """GET /alerts"""
    return 200, {"config": load_alerts_config(), "history": get_alerts_history()}


def _h_download_report(params: dict) -> tuple[int, dict]:
    """GET /download-report"""
    import os
    raw = params.get("file","")
    if isinstance(raw, list): raw = raw[0] if raw else ""
    filename = os.path.basename(str(raw).strip())
    if not filename: return 400, {"error": "Parametre requis : file"}
    path = Path("reports") / filename
    if not path.exists(): return 404, {"error": f"Fichier non trouve : {filename}"}
    return 200, {"success": True, "filename": filename, "size": path.stat().st_size}


_ROUTES = {
    ("POST", "/check-compliance"): _h_check_compliance,
    ("POST", "/diff"):             _h_diff,
    ("GET",  "/risk-summary"):     _h_risk_summary,
    ("GET",  "/top-risks"):        _h_top_risks,
    ("GET",  "/rules"):            _h_rules,
    ("GET",  "/graph-stats"):      _h_graph_stats,
    ("GET",  "/health"):           _h_health,
    ("POST", "/analyze-text"):     _h_analyze_text,
    ("POST", "/legal-risk"):       _h_legal_risk,
    ("POST", "/chat"):             _h_chat,
    ("POST", "/rag-search"):       _h_rag_search,
    ("POST", "/generate-report"):  _h_generate_report,
    ("POST", "/send-email"):       _h_send_email,
    ("POST", "/configure-alerts"): _h_configure_alerts,
    ("GET",  "/alerts"):           _h_get_alerts,
    ("GET",  "/download-report"):  _h_download_report,
}


class _Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        log.info(f"{self.client_address[0]} {fmt % args}")

    def _respond(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n == 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide : {e}")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        handler = _ROUTES.get((method, path))
        if handler is None:
            self._respond(404, {
                "error":  f"Route inconnue : {method} {path}",
                "routes": [f"{m} {p}" for m, p in _ROUTES],
            })
            return

        try:
            if method == "POST":
                code, result = handler(self._read_body())
            else:
                code, result = handler(params)
            self._respond(code, result)
        except ValueError as e:
            self._respond(400, {"error": str(e)})
        except Exception as e:
            log.exception(f"Erreur : {e}")
            self._respond(500, {"error": str(e)})

    def do_GET(self):    self._dispatch("GET")
    def do_POST(self):   self._dispatch("POST")
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start(host: str = API_HOST, port: int = API_PORT) -> None:
    server = HTTPServer((host, port), _Handler)
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║  BO5 API — Code des Droits Réels tunisien        ║")
    log.info(f"║  http://{host}:{port:<39} ║")
    log.info("╠══════════════════════════════════════════════════╣")
    log.info("║  POST /analyze-text                              ║")
    log.info("║  POST /legal-risk                                ║")
    log.info("║  POST /chat                                      ║")
    log.info("║  POST /generate-report                           ║")
    log.info("║  POST /configure-alerts                          ║")
    log.info("║  POST /check-compliance                          ║")
    log.info("║  GET  /health                                    ║")
    log.info("║  GET  /alerts                                    ║")
    log.info("║  GET  /download-report                           ║")
    log.info("╚══════════════════════════════════════════════════╝")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Serveur arrêté.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=API_HOST)
    p.add_argument("--port", type=int, default=API_PORT)
    a = p.parse_args()
    start(a.host, a.port)