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
from compliance  import (check_compliance, detect_changes, check_and_alert,
                         is_urbanisme_question, compute_urbanisme_risk)
from nlp_parser  import parse_natural

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


def _h_analyze_text(body: dict) -> tuple[int, dict]:
    """
    POST /analyze-text
    ──────────────────
    Architecture hybride CDR + Urbanisme :
      NIVEAU 1 — CDR (66 règles structurées + risk score DS03)
      NIVEAU 2 — Urbanisme (RAG + risk score dynamique)
      NIVEAU 3 — Fallback RAG CDR si toujours INDÉTERMINÉ
    """
    text = body.get("text", "").strip()
    if not text:
        return 400, {"error": "Champ requis : 'text'"}

    # STEP 1 : NLP Parser
    parsed = parse_natural(text, use_llm=body.get("use_llm", True))
    if "error" in parsed:
        return 400, parsed

    if not parsed.get("actor") or not parsed.get("action"):
        return 200, {
            "parsed":     parsed,
            "compliance": {
                "global_status": "UNPARSEABLE",
                "explanations":  ["Précisez qui fait quoi."],
            },
        }

    user_case = {
        "actor":      parsed["actor"],
        "action":     parsed["action"],
        "target":     parsed.get("target", ""),
        "conditions": parsed.get("conditions", []),
    }

    # STEP 2 : CDR — moteur de conformité
    compliance = check_compliance(
        user_case, _load_rules(),
        threshold   = float(body.get("threshold",   0.45)),
        max_results = int(body.get("max_results",   10)),
    )
    check_and_alert(compliance)

    rag_fallback = None

    # STEP 3 : RAG Urbanisme si mots construction détectés
    # UNIQUEMENT si pas HORS DOMAINE et pas déjà CONFORME via CDR
    status_needs_rag = compliance.get("global_status") == "UNKNOWN"
    urbanisme_needed = is_urbanisme_question(user_case)
    cdr_already_answered = compliance.get("global_status") in ("COMPLIANT", "VIOLATION", "WARNING")

    # Ne pas déclencher RAG si :
    # - Complètement hors domaine
    # - CDR a déjà trouvé une réponse claire ET pas de conditions négatives
    conds_str = " ".join(user_case.get("conditions", [])).lower()
    has_negative = any(w in conds_str for w in [
        "sans permis", "sans autorisation", "sans accord",
        "illegalement", "non constructible"
    ])
    skip_rag = (
        (compliance.get("global_status") == "OUT_OF_DOMAIN" and not urbanisme_needed)
        or (cdr_already_answered and not has_negative)
    )

    if skip_rag:
        pass
    elif status_needs_rag or urbanisme_needed:
        try:
            from rag     import search, format_context
            from chatbot import chat as chatbot_chat

            # Détecter la source appropriée
            if is_urbanisme_question(user_case):
                sources   = ["URBANISME"]
                law_label = "Code de l'Amenagement du Territoire 2011"
            else:
                sources   = ["CDR"]
                law_label = "Code des Droits Reels - Loi n65-5"

            # Recherche RAG
            query       = f"{user_case['actor']} {user_case['action']} {user_case.get('target','')}"
            rag_results = search(query, sources=sources, top_k=3)
            rag_context = format_context(rag_results, max_chars=800)

            if rag_results:
                # Calculer risk score
                if sources == ["URBANISME"]:
                    risk_data = compute_urbanisme_risk(rag_results, user_case)
                else:
                    risk_data = {
                        "risk_score": 0,
                        "status":     "UNKNOWN",
                        "articles":   [],
                        "source":     "CDR",
                        "law":        law_label,
                    }

                # Explication naturelle via chatbot
                question = (
                    f"Selon le droit tunisien, est-ce que {user_case['actor']} "
                    f"peut {user_case['action']}"
                    + (f" {user_case['target']}" if user_case.get('target') else "")
                    + " ?"
                )
                chat_result = chatbot_chat(question, rag_context=rag_context)

                # Niveau de risque
                rs = risk_data["risk_score"]
                if rs >= 70:   lvl, emoji = "HIGH",   "rouge"
                elif rs >= 40: lvl, emoji = "MEDIUM", "jaune"
                else:          lvl, emoji = "LOW",    "vert"

                rag_fallback = {
                    "used":        True,
                    "source":      risk_data.get("source", ""),
                    "law":         risk_data.get("law",    law_label),
                    "risk_score":  rs,
                    "risk_level":  lvl,
                    "risk_emoji":  emoji,
                    "articles":    risk_data.get("articles", []),
                    "explanation": chat_result.get("answer", ""),
                }

                # Mettre à jour statut global
                if risk_data["status"] == "interdit":
                    compliance["global_status"] = "VIOLATION"
                elif risk_data["status"] == "obligation":
                    compliance["global_status"] = "WARNING"
                elif risk_data["status"] == "permis":
                    compliance["global_status"] = "COMPLIANT"
                compliance["risk_score"] = rs

        except Exception as e:
            log.warning(f"RAG fallback echoue : {e}")

    return 200, {
        "parsed":       parsed,
        "compliance":   compliance,
        "rag_fallback": rag_fallback,
    }


def _h_legal_risk(body: dict) -> tuple[int, dict]:
    """
    POST /legal-risk
    ────────────────
    Endpoint structuré pour le Decision Copilot (Chapitre 8).
    Retourne un résumé juridique complet consommable par les autres agents.

    Input:
        {
            "actor":      "proprietaire",
            "action":     "construire",
            "target":     "immeuble",
            "conditions": ["sans permis"],
            "zone":       "Hammamet Nord"   ← optionnel
        }

    Output:
        {
            "legal_risk_score": 65,
            "status":           "VIOLATION",
            "risk_level":       "HIGH",
            "main_issues":      [...],
            "articles":         [...],
            "recommendation":   "...",
            "copilot_summary":  "...",
            "details":          {...}
        }
    """
    # Valider les champs
    if not body.get("actor") or not body.get("action"):
        return 400, {"error": "Champs requis : 'actor' et 'action'"}

    # Lancer la vérification de conformité
    rules    = _load_rules()
    result   = check_compliance(body, rules)
    check_and_alert(result)

    status     = result.get("global_status", "UNKNOWN")
    risk_score = result.get("risk_score", 0)

    # Niveau de risque
    if risk_score >= 70:
        risk_level = "HIGH"
        risk_emoji = "🔴"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
        risk_emoji = "🟡"
    else:
        risk_level = "LOW"
        risk_emoji = "🟢"

    # Extraire les problèmes principaux
    main_issues = []
    articles    = []

    for v in result.get("violations", []):
        main_issues.append(v.get("message", ""))
        art = v.get("article", "")
        if art and art not in articles:
            articles.append(f"Art.{art} CDR")

    for w in result.get("warnings", []):
        main_issues.append(w.get("message", ""))
        art = w.get("article", "")
        if art and art not in articles:
            articles.append(f"Art.{art} CDR")

    # Recommandation automatique selon le statut
    recommendations = {
        "VIOLATION":   "Action illégale selon le CDR tunisien. Arrêtez immédiatement et consultez un notaire.",
        "WARNING":     "Conditions incomplètes. Vérifiez les prérequis légaux avant de procéder.",
        "COMPLIANT":   "Action conforme au CDR. Conservez les documents justificatifs.",
        "UNKNOWN":     "Situation non couverte par nos règles. Consultez un juriste spécialisé.",
        "OUT_OF_DOMAIN": "Hors périmètre du Code des Droits Réels tunisien.",
    }
    recommendation = recommendations.get(status, "Consultez un juriste spécialisé.")

    # Résumé court pour le Copilot
    actor  = body.get("actor",  "")
    action = body.get("action", "")
    zone   = body.get("zone",   "")

    copilot_summary = (
        f"{risk_emoji} Risque juridique {risk_level} ({risk_score}/100). "
        f"Situation : {actor} → {action}"
    )
    if zone:
        copilot_summary += f" dans la zone {zone}"
    copilot_summary += f". Statut : {status}."
    if main_issues:
        copilot_summary += f" Problème principal : {main_issues[0][:100]}"

    # Vérification zonage via RAG si zone fournie
    zone_info = None
    if zone:
        try:
            from rag import search, format_context
            rag_results = search(
                f"zone constructible {zone} autorisation",
                sources=["URBANISME"],
                top_k=2
            )
            if rag_results:
                zone_info = {
                    "zone":    zone,
                    "context": format_context(rag_results, max_chars=400),
                    "articles": [f"Art.{r['article']} CATU" for r in rag_results],
                }
                # Ajouter les articles urbanisme
                for r in rag_results:
                    art_ref = f"Art.{r['article']} CATU"
                    if art_ref not in articles:
                        articles.append(art_ref)
        except Exception:
            pass

    return 200, {
        "legal_risk_score": risk_score,
        "status":           status,
        "risk_level":       risk_level,
        "risk_emoji":       risk_emoji,
        "main_issues":      main_issues[:3],
        "articles":         articles[:5],
        "recommendation":   recommendation,
        "copilot_summary":  copilot_summary,
        "zone_info":        zone_info,
        "details": {
            "violations":      len(result.get("violations", [])),
            "warnings":        len(result.get("warnings",   [])),
            "compliant_rules": len(result.get("compliant_rules", [])),
            "user_case":       body,
        },
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

def _h_chat(body: dict) -> tuple[int, dict]:
    """POST /chat — Chatbot juridique via Mistral + RAG."""
    question = body.get("question", "").strip()
    if not question:
        return 400, {"error": "Champ requis : 'question'"}
    try:
        from chatbot import chat as chatbot_chat
        from rag     import search, format_context
        use_rag  = body.get("use_rag", True)
        rag_ctx  = ""
        if use_rag:
            sources = body.get("sources", None)
            results = search(question, sources=sources, top_k=3)
            rag_ctx = format_context(results)
        result = chatbot_chat(question, rag_context=rag_ctx)
        return 200, result
    except Exception as e:
        return 500, {"error": str(e)}


def _h_rag_search(body: dict) -> tuple[int, dict]:
    """POST /rag-search — Recherche sémantique dans les textes juridiques."""
    query = body.get("query", "").strip()
    if not query:
        return 400, {"error": "Champ requis : 'query'"}
    try:
        from rag import search, available_sources
        sources = body.get("sources", None)
        top_k   = int(body.get("top_k", 3))
        results = search(query, sources=sources, top_k=top_k)
        return 200, {
            "results":           results,
            "sources_available": available_sources(),
            "count":             len(results),
        }
    except Exception as e:
        return 500, {"error": str(e)}


def _h_index_pdf(body: dict) -> tuple[int, dict]:
    """POST /index-pdf — Indexe un nouveau PDF pour le RAG."""
    pdf_path   = body.get("pdf_path",   "").strip()
    source_key = body.get("source_key", "").strip().upper()
    if not pdf_path or not source_key:
        return 400, {"error": "Champs requis : 'pdf_path' et 'source_key'"}
    try:
        from rag import index_pdf
        result = index_pdf(pdf_path, source_key)
        if "error" in result:
            return 500, result
        return 200, result
    except Exception as e:
        return 500, {"error": str(e)}


_ROUTES = {
    ("POST", "/check-compliance"): _h_check_compliance,
    ("POST", "/analyze-text"):     _h_analyze_text,
    ("POST", "/legal-risk"):       _h_legal_risk,
    ("POST", "/chat"):             _h_chat,
    ("POST", "/rag-search"):       _h_rag_search,
    ("POST", "/index-pdf"):        _h_index_pdf,
    ("POST", "/diff"):             _h_diff,
    ("GET",  "/risk-summary"):     _h_risk_summary,
    ("GET",  "/top-risks"):        _h_top_risks,
    ("GET",  "/rules"):            _h_rules,
    ("GET",  "/graph-stats"):      _h_graph_stats,
    ("GET",  "/health"):           _h_health,
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
    log.info("║  POST /check-compliance                          ║")
    log.info("║  POST /diff                                      ║")
    log.info("║  GET  /risk-summary                              ║")
    log.info("║  GET  /top-risks?n=10&status=interdit            ║")
    log.info("║  GET  /rules?actor=proprietaire&limit=20         ║")
    log.info("║  GET  /graph-stats                               ║")
    log.info("║  GET  /health                                    ║")
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