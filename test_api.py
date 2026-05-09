"""
test_api.py
─────────────────────────────────────────────────────────────────
Tests complets de l'API BO5.
Lance l'API dans un thread séparé, exécute tous les tests, affiche les résultats.

USAGE :
  python test_api.py
  python test_api.py --port 8001

Prérequis : rules_clean.json doit exister dans data/
"""

import json, time, threading, urllib.request, urllib.error
from pathlib import Path
import argparse
from typing import Any

BASE = "http://localhost:8000"


# ──────────────────────────────────────────────────────────────
# Helpers HTTP
# ──────────────────────────────────────────────────────────────

def _get(path: str) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}


def _post(path: str, body: dict) -> tuple[int, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}


# ──────────────────────────────────────────────────────────────
# Affichage
# ──────────────────────────────────────────────────────────────

def _ok(label: str, detail: str = "") -> None:
    print(f"  ✅ {label}" + (f" — {detail}" if detail else ""))


def _fail(label: str, detail: str = "") -> None:
    print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))


def _section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ──────────────────────────────────────────────────────────────
# Suites de tests
# ──────────────────────────────────────────────────────────────

def test_health():
    _section("GET /health")
    code, resp = _get("/health")
    if code == 200 and resp.get("status") == "ok":
        rules_count = resp.get("components", {}).get("rules_clean", {}).get("count", 0)
        _ok("Statut OK", f"{rules_count} règles chargées")
    else:
        _fail("Health check échoué", f"code={code} status={resp.get('status')}")
    return code == 200


def test_risk_summary():
    _section("GET /risk-summary")
    code, resp = _get("/risk-summary")
    if code == 200:
        rs = resp.get("risk_stats", {})
        _ok("Risk Summary", f"total={resp.get('total_rules')} avg={rs.get('avg')} max={rs.get('max')}")
        _ok("Distribution", str(rs.get("distribution", {})))
        _ok("Top acteurs",  str(dict(list(resp.get("top_actors", {}).items())[:3])))
    else:
        _fail("Risk Summary échoué", f"code={code}")
    return code == 200


def test_top_risks():
    _section("GET /top-risks")

    # Tous statuts
    code, resp = _get("/top-risks?n=5")
    if code == 200 and resp.get("top_risks"):
        top = resp["top_risks"]
        _ok(f"Top 5 global", f"max risk={top[0]['risk_score']}")
        for r in top[:3]:
            print(f"     [{r['risk_score']:>3}/100] {r['actor']:>15} → {r['action'][:45]}")
    else:
        _fail("Top risks global", f"code={code}")

    # Filtre status
    code2, resp2 = _get("/top-risks?n=3&status=interdit")
    if code2 == 200:
        _ok(f"Filtre status=interdit", f"{resp2.get('count')} règles")
    else:
        _fail("Filtre status", f"code={code2}")

    # Filtre acteur
    code3, resp3 = _get("/top-risks?n=3&actor=proprietaire")
    if code3 == 200:
        _ok(f"Filtre actor=proprietaire", f"{resp3.get('count')} règles")
    else:
        _fail("Filtre actor", f"code={code3}")

    return code == 200


def test_rules():
    _section("GET /rules")

    # Liste paginée
    code, resp = _get("/rules?limit=5&offset=0")
    if code == 200:
        _ok(f"Liste paginée", f"total={resp.get('total')} | page={len(resp.get('rules',[]))}")
    else:
        _fail("Liste paginée", f"code={code}")

    # Filtre actor
    code2, resp2 = _get("/rules?actor=locataire&limit=10")
    if code2 == 200:
        _ok(f"Filtre actor=locataire", f"{resp2.get('total')} règles")
        for r in resp2.get("rules", [])[:2]:
            print(f"     {r['action'][:60]} ({r['status']})")
    else:
        _fail("Filtre actor", f"code={code2}")

    # Filtre status interdit
    code3, resp3 = _get("/rules?status=interdit")
    if code3 == 200:
        _ok(f"Filtre status=interdit", f"{resp3.get('total')} règles")
    else:
        _fail("Filtre status", f"code={code3}")

    return code == 200


def test_check_compliance():
    _section("POST /check-compliance")

    test_cases = [
        {
            "label":    "Construction sans permis → VIOLATION attendue",
            "payload":  {
                "actor":  "proprietaire",
                "action": "construire",
                "target": "immeuble",
            },
            "expected": "VIOLATION",
        },
        {
            "label":    "Construction avec permis → COMPLIANT ou WARNING",
            "payload":  {
                "actor":      "proprietaire",
                "action":     "construire",
                "target":     "immeuble",
                "conditions": ["avec permis de construire", "normes locales respectées"],
            },
            "expected": None,  # pas de violation strictement requise
        },
        {
            "label":    "Démolition sans autorisation → VIOLATION critique",
            "payload":  {
                "actor":  "proprietaire",
                "action": "démolir",
                "target": "bâtiment",
            },
            "expected": "VIOLATION",
        },
        {
            "label":    "Vente immobilière avec notaire",
            "payload":  {
                "actor":      "particulier",
                "action":     "vendre un bien immobilier",
                "target":     "bien immobilier",
                "conditions": ["devant une notaire"],
            },
            "expected": None,
        },
        {
            "label":    "Hors domaine → OUT_OF_DOMAIN",
            "payload":  {
                "actor":  "employeur",
                "action": "licencier",
                "target": "employé",
            },
            "expected": "OUT_OF_DOMAIN",
        },
    ]

    all_ok = True
    for tc in test_cases:
        code, resp = _post("/check-compliance", tc["payload"])
        gs   = resp.get("global_status", "?")
        risk = resp.get("risk_score", 0)
        nv   = len(resp.get("violations", []))
        nw   = len(resp.get("warnings",   []))
        nc   = len(resp.get("compliant_rules", []))

        if code != 200:
            _fail(tc["label"], f"HTTP {code}")
            all_ok = False
            continue

        if tc["expected"] and gs != tc["expected"]:
            _fail(tc["label"],
                  f"attendu={tc['expected']} obtenu={gs} risk={risk}")
            all_ok = False
        else:
            _ok(tc["label"],
                f"status={gs} risk={risk} V={nv} W={nw} C={nc}")

        # Afficher le top résultat
        for v in resp.get("violations", [])[:1]:
            print(f"       🚨 [{v['risk_score']:>3}] {v['message'][:80]}")
        for w in resp.get("warnings", [])[:1]:
            print(f"       ⚠️  [{w['risk_score']:>3}] {w['message'][:80]}")

    return all_ok


def test_diff():
    _section("POST /diff")
    import tempfile, os
    from pathlib import Path

    # Créer une version "précédente" modifiée (simulation)
    rules_path = str(Path(__file__).parent / "data" / "rules_clean.json")
    if not Path(rules_path).exists():
        _fail("rules_clean.json introuvable")
        return False

    rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))

    # Version simulée : modifier 2 risk_scores, supprimer 1 règle
    prev_rules = [r.copy() for r in rules]
    if len(prev_rules) >= 3:
        prev_rules[0]["risk_score"] = max(0, prev_rules[0]["risk_score"] - 15)
        prev_rules[1]["risk_score"] = min(100, prev_rules[1]["risk_score"] + 10)
        prev_rules.pop(2)  # simuler suppression

    tmp = tempfile.mktemp(suffix=".json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prev_rules, f, ensure_ascii=False)

    code, resp = _post("/diff", {
        "current_path":  rules_path,
        "previous_path": tmp,
    })
    os.unlink(tmp)

    if code == 200:
        s = resp.get("summary", {})
        _ok("Diff exécuté",
            f"added={s.get('added')} removed={s.get('removed')} "
            f"modified={s.get('modified')}")
        for m in resp.get("modified", [])[:2]:
            r = m["rule"]
            print(f"       ~ {r['actor']} → {r['action'][:40]} : "
                  f"{m['risk_before']}→{m['risk_after']} {m['direction']}")
        for r in resp.get("removed", [])[:1]:
            print(f"       − {r['actor']} → {r['action'][:40]}")
    else:
        _fail("Diff échoué", f"code={code}")
    return code == 200


def test_graph_stats():
    _section("GET /graph-stats")
    code, resp = _get("/graph-stats")
    if code == 200:
        nodes = resp.get("nodes", {})
        rels  = resp.get("relationships", {})
        _ok("Graph Stats",
            f"nœuds={nodes.get('total',0)} "
            f"MUST={rels.get('MUST',0)} "
            f"CAN={rels.get('CAN',0)} "
            f"CANNOT={rels.get('CANNOT',0)}")
        csv_c = resp.get("csv_counts", {})
        if csv_c:
            _ok("CSV disponibles", str(csv_c))
    elif code == 503:
        print("  ⚠️  Graph non encore construit (normal si --step graph n'a pas été lancé)")
    else:
        _fail("Graph Stats", f"code={code}")
    return code in (200, 503)


def test_error_handling():
    _section("Gestion des erreurs")

    # Route inconnue
    code, _ = _get("/unknown-endpoint")
    _ok("404 sur route inconnue", f"code={code}") if code == 404 else \
    _fail("404 attendu", f"code={code}")

    # POST sans champs requis
    code2, resp2 = _post("/check-compliance", {})
    _ok("400 sur body vide", f"code={code2} error={resp2.get('error','')[:50]}") \
    if code2 == 400 else _fail("400 attendu", f"code={code2}")

    # POST diff sans previous_path
    code3, _ = _post("/diff", {"current_path": "x.json"})
    _ok("400 sans previous_path", f"code={code3}") if code3 == 400 else \
    _fail("400 attendu", f"code={code3}")


# ──────────────────────────────────────────────────────────────
# Runner principal
# ──────────────────────────────────────────────────────────────

def wait_for_server(max_wait: int = 10) -> bool:
    for _ in range(max_wait * 2):
        try:
            code, _ = _get("/health")
            if code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    global BASE

    parser = argparse.ArgumentParser(description="Tests API BO5")
    parser.add_argument("--port",       type=int,  default=8000)
    parser.add_argument("--no-server",  action="store_true",
                        help="Ne pas démarrer le serveur (déjà lancé)")
    args = parser.parse_args()

    BASE = f"http://localhost:{args.port}"

    print(f"\n{'═'*62}")
    print(f"  BO5 — Tests API")
    print(f"  Cible : {BASE}")
    print(f"{'═'*62}")

    # Démarrer le serveur en thread si nécessaire
    if not args.no_server:
        print("\n  Démarrage du serveur de test…")
        import sys, os
        sys.path.insert(0, str(Path(__file__).parent))

        from api import start
        t = threading.Thread(
            target=lambda: start("127.0.0.1", args.port), daemon=True
        )
        t.start()
        if not wait_for_server():
            print("  ❌ Serveur non disponible après 10s.")
            sys.exit(1)
        print("  ✅ Serveur prêt\n")

    # Exécuter les tests
    results = []
    for fn in [
        test_health,
        test_risk_summary,
        test_top_risks,
        test_rules,
        test_check_compliance,
        test_diff,
        test_graph_stats,
        test_error_handling,
    ]:
        try:
            ok = fn()
            results.append((fn.__name__, ok if ok is not None else True))
        except Exception as e:
            print(f"  ❌ Exception dans {fn.__name__} : {e}")
            results.append((fn.__name__, False))

    # Résumé
    print(f"\n{'═'*62}")
    print("  RÉSUMÉ DES TESTS")
    print(f"{'═'*62}")
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
    print(f"\n  {passed}/{len(results)} tests réussis\n")


if __name__ == "__main__":
    main()
