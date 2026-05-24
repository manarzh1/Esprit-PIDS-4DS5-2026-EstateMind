"""
hallucination_eval.py
─────────────────────────────────────────────────────────────────
Module d'évaluation de la qualité des règles extraites par le LLM.
Mesure le taux de hallucination, les doublons, la couverture du domaine.

USAGE :
  python hallucination_eval.py
  python hallucination_eval.py --rules data/rules_clean.json
  python hallucination_eval.py --compare data/rules_v1.json data/rules_clean.json

BO5 — Code des Droits Réels tunisien
"""

import json, re, argparse
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher
from datetime import date
from config import SEMANTIC_DEDUP_THRESHOLD, SEMANTIC_DEDUP_ENABLED

# ── Chemins par défaut ────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
DATA_DIR  = ROOT / "data"
RULES_PATH = DATA_DIR / "rules_clean.json"

# ── Patterns d'articles appartenant à des codes étrangers (pas au CDR tunisien)
# Le CDR tunisien utilise des numéros simples : Article 1, Article 85, Article 230...
# Le LLM hallucine des références du droit français
FRENCH_ARTICLE_PATTERNS = {
    "code de l'urbanisme",
    "code de la construction",
    "code civil français",
    "r142", "r.162", "r143",
    "l. 132", "l.162", "l145",
    "169-1 du code",
    "1423 du code",
    "1643 du code",
    "1458 du code",
    "1726 du code",
    "836 du code civil",
    "837-1",
    "172-4 du code",
    "1642-1",
    "143-1 al",
    "142-6 du code",
    "132-4 du code",
    "540-1 du code",
    "145-3 du code",
    "514-2 du code",
    "513-2 du code",
    "431-1 du code",
    "article r.",
    "article l. 1",
}

# ── Mots en langue étrangère dans les actions
FOREIGN_WORDS = ["sublet", "rental agreement", "buy property", "lease out", "mortgage"]

# ── Vraies références du CDR tunisien (articles simples)
CDR_ARTICLE_RE = re.compile(r"^article\s+\d+|^\d+\s+du\s+code|^art\.\s*\d+", re.IGNORECASE)


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION
# ══════════════════════════════════════════════════════════════════════════════

def is_hallucinated(rule: dict) -> tuple[bool, str]:
    """
    Détermine si une règle est une hallucination et retourne la raison.
    Retourne (True, raison) ou (False, "").
    """
    article = rule.get("article", "").lower()
    action  = rule.get("action", "").lower()

    # Test 1 : référence à un code juridique étranger
    for pattern in FRENCH_ARTICLE_PATTERNS:
        if pattern in article:
            return True, f"Article de code étranger : '{rule.get('article', '')}'"

    # Test 2 : action en langue étrangère
    for word in FOREIGN_WORDS:
        if word in action:
            return True, f"Action en langue étrangère : '{rule.get('action', '')}'"

    # Test 3 : article contient des lettres-chiffres typiques du code français (L.xxx, R.xxx)
    if re.search(r'\b[LR]\.\s*\d{3}', rule.get("article", ""), re.IGNORECASE):
        return True, f"Format article code français (L./R.) : '{rule.get('article', '')}'"

    return False, ""


def _sim(a: str, b: str) -> float:
    """Similarité textuelle simple."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_semantic_duplicates(rules: list[dict], threshold: float = None) -> list[tuple]:
    """
    Détecte les règles sémantiquement trop proches (doublons sémantiques).
    
    Stratégie hybride :
      1. Si sentence-transformers disponible → embeddings cosine similarity
      2. Sinon → similarité textuelle SequenceMatcher (fallback)
    
    Comparaison sur la combinaison actor + action + target pour une
    détection plus précise des vrais doublons.

    Returns:
        Liste de tuples (i, j, similarité) triée par score décroissant.
    """
    if not SEMANTIC_DEDUP_ENABLED:
        return []

    thr = threshold or SEMANTIC_DEDUP_THRESHOLD

    # Tentative avec embeddings (meilleure précision)
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")

        # Créer des représentations textuelles complètes des règles
        texts = [
            f"{r.get('actor','')} {r.get('action','')} {r.get('target','')}".strip()
            for r in rules
        ]
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        dups = []
        for i in range(len(rules)):
            for j in range(i + 1, len(rules)):
                # Même statut requis pour être un doublon pertinent
                if rules[i].get("status") != rules[j].get("status"):
                    continue
                sim = float(embeddings[i] @ embeddings[j])
                if sim >= thr:
                    dups.append((i, j, round(sim, 3)))

        return sorted(dups, key=lambda x: -x[2])

    except ImportError:
        pass  # Fallback vers SequenceMatcher

    # Fallback : similarité textuelle avec champ élargi
    dups = []
    for i in range(len(rules)):
        for j in range(i + 1, len(rules)):
            ri, rj = rules[i], rules[j]
            if ri.get("status") != rj.get("status"):
                continue
            # Comparer sur actor + action + target combinés
            text_i = f"{ri.get('actor','')} {ri.get('action','')} {ri.get('target','')}".lower()
            text_j = f"{rj.get('actor','')} {rj.get('action','')} {rj.get('target','')}".lower()
            sim = _sim(text_i, text_j)
            if sim >= thr:
                dups.append((i, j, round(sim, 3)))

    return sorted(dups, key=lambda x: -x[2])


# ══════════════════════════════════════════════════════════════════════════════
# ÉVALUATION COMPLÈTE
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(rules: list[dict]) -> dict:
    """
    Évalue la qualité de l'extraction LLM.

    Métriques calculées :
    - Taux de hallucination (articles codes étrangers, actions en anglais)
    - Taux de doublons sémantiques
    - Couverture du domaine juridique tunisien
    - Distribution des quality_scores
    - Distribution des statuts
    - Acteurs normalisés vs non-normalisés
    """
    n = len(rules)
    if n == 0:
        return {"error": "Aucune règle à évaluer"}

    # ── Hallucinations ────────────────────────────────────────────────────────
    hallucinations = []
    for i, rule in enumerate(rules):
        is_h, reason = is_hallucinated(rule)
        if is_h:
            hallucinations.append({
                "index":  i,
                "actor":  rule.get("actor", ""),
                "action": rule.get("action", ""),
                "article": rule.get("article", ""),
                "reason": reason,
            })

    hallu_rate = len(hallucinations) / n

    # ── Doublons sémantiques ─────────────────────────────────────────────────
    semantic_dups = find_semantic_duplicates(rules, threshold=SEMANTIC_DEDUP_THRESHOLD)
    dup_rules_idx = set()
    for i, j, _ in semantic_dups:
        dup_rules_idx.add(j)   # le "j" est le doublon du "i"
    dup_rate = len(dup_rules_idx) / n

    # ── Qualité des articles de référence ────────────────────────────────────
    no_article   = [r for r in rules if not r.get("article", "").strip()]
    vague_article = [r for r in rules if r.get("article", "").lower().strip()
                     in ("loi sur l'urbanisme", "loi sur la location immobilière",
                         "code de l'urbanisme", "")]

    # ── Quality scores ────────────────────────────────────────────────────────
    qs = [r.get("quality_score", 0) for r in rules]
    low_quality = [r for r in rules if r.get("quality_score", 10) < 6]

    # ── Acteurs ───────────────────────────────────────────────────────────────
    actor_std = sum(1 for r in rules if r.get("actor_standard", False))

    # ── Statuts ───────────────────────────────────────────────────────────────
    statuts = Counter(r.get("status", "?") for r in rules)

    # ── Actions dupliquées exactes ────────────────────────────────────────────
    action_counts = Counter(r.get("action", "") for r in rules)
    exact_dups = {a: n for a, n in action_counts.items() if n > 1}

    # ── Score global de fiabilité ─────────────────────────────────────────────
    # Formule : 100 - (hallu_rate*50) - (dup_rate*20) - (low_quality_rate*15) - (no_article_rate*15)
    no_article_rate = len(no_article) / n
    low_quality_rate = len(low_quality) / n
    reliability_score = max(0, round(
        100
        - (hallu_rate * 50)
        - (dup_rate * 20)
        - (low_quality_rate * 15)
        - (no_article_rate * 15)
    ))

    return {
        "eval_date":          str(date.today()),
        "total_rules":        n,

        # ── Hallucinations ──────────────────────────────────────────────────
        "hallucination": {
            "count":          len(hallucinations),
            "rate_pct":       round(hallu_rate * 100, 1),
            "clean_count":    n - len(hallucinations),
            "clean_rate_pct": round((1 - hallu_rate) * 100, 1),
            "examples":       hallucinations[:5],
            "verdict": (
                "CRITIQUE"  if hallu_rate > 0.30 else
                "ÉLEVÉ"     if hallu_rate > 0.15 else
                "ACCEPTABLE" if hallu_rate > 0.05 else
                "BON"
            ),
        },

        # ── Doublons sémantiques ─────────────────────────────────────────────
        "semantic_duplicates": {
            "count":        len(semantic_dups),
            "rate_pct":     round(dup_rate * 100, 1),
            "examples":     [
                {
                    "rule_a": rules[i].get("action", "")[:50],
                    "rule_b": rules[j].get("action", "")[:50],
                    "actor":  rules[i].get("actor", ""),
                    "sim":    s,
                }
                for i, j, s in semantic_dups[:5]
            ],
            "exact_dups":   {a: c for a, c in sorted(exact_dups.items(), key=lambda x: -x[1])[:10]},
        },

        # ── Qualité articles ─────────────────────────────────────────────────
        "article_quality": {
            "no_article":     len(no_article),
            "vague_article":  len(vague_article),
            "quality_rate_pct": round((n - len(no_article) - len(vague_article)) / n * 100, 1),
        },

        # ── Quality scores ───────────────────────────────────────────────────
        "quality_scores": {
            "min":   min(qs),
            "max":   max(qs),
            "avg":   round(sum(qs) / n, 1),
            "low_quality_count": len(low_quality),
        },

        # ── Normalisation acteurs ────────────────────────────────────────────
        "actors": {
            "standardized":     actor_std,
            "standardized_pct": round(actor_std / n * 100, 1),
            "top_actors":       dict(Counter(r.get("actor", "") for r in rules).most_common(6)),
        },

        # ── Statuts ─────────────────────────────────────────────────────────
        "status_distribution": {
            "interdit":   statuts.get("interdit", 0),
            "obligation": statuts.get("obligation", 0),
            "permis":     statuts.get("permis", 0),
        },

        # ── Score global ─────────────────────────────────────────────────────
        "reliability_score": reliability_score,
        "reliability_grade": (
            "A" if reliability_score >= 85 else
            "B" if reliability_score >= 70 else
            "C" if reliability_score >= 55 else
            "D"
        ),

        # ── Recommandations ──────────────────────────────────────────────────
        "recommendations": _build_recommendations(hallu_rate, dup_rate, low_quality_rate),
    }


def _build_recommendations(hallu_rate, dup_rate, low_quality_rate) -> list[str]:
    recs = []
    if hallu_rate > 0.15:
        recs.append(
            f"CRITIQUE — Taux hallucination {hallu_rate*100:.0f}% : "
            "passer LLM_TEMP de 0 à 0.3, renforcer le prompt avec instructions "
            "explicites 'NE PAS citer de codes étrangers', ajouter filtre post-extraction."
        )
    if hallu_rate > 0.30:
        recs.append(
            "Envisager le chunking sémantique (TF-IDF ou sentence-transformers) "
            "pour créer des chunks thématiques cohérents plutôt qu'article par article."
        )
    if dup_rate > 0.10:
        recs.append(
            f"Doublons sémantiques élevés ({dup_rate*100:.0f}%) : "
            "ajouter une étape de déduplication vectorielle après extraction."
        )
    if low_quality_rate > 0.10:
        recs.append(
            "Qualité faible sur plusieurs règles : améliorer le filtrage "
            "post-extraction avec quality_score ≥ 7."
        )
    if not recs:
        recs.append("Qualité satisfaisante. Continuer à surveiller à chaque nouvelle extraction.")
    return recs


# ══════════════════════════════════════════════════════════════════════════════
# AFFICHAGE
# ══════════════════════════════════════════════════════════════════════════════

def print_report(report: dict) -> None:
    """Affiche le rapport d'évaluation de façon lisible."""
    W = 65
    sep = "═" * W

    print(f"\n{sep}")
    print(f"  RAPPORT D'ÉVALUATION — Extraction LLM BO5")
    print(f"  Date : {report['eval_date']}  |  {report['total_rules']} règles analysées")
    print(f"{sep}\n")

    # Score global
    score = report["reliability_score"]
    grade = report["reliability_grade"]
    bar   = "█" * (score // 5) + "░" * (20 - score // 5)
    print(f"  SCORE DE FIABILITÉ GLOBAL : {score}/100  [{grade}]")
    print(f"  [{bar}] {score}%\n")

    # Hallucinations
    h = report["hallucination"]
    icon = {"BON": "✅", "ACCEPTABLE": "⚠️", "ÉLEVÉ": "🔴", "CRITIQUE": "🚨"}.get(h["verdict"], "?")
    print(f"  {icon} HALLUCINATIONS")
    print(f"     Détectées  : {h['count']}/{report['total_rules']} ({h['rate_pct']}%)")
    print(f"     Propres    : {h['clean_count']} ({h['clean_rate_pct']}%)")
    print(f"     Verdict    : {h['verdict']}")
    if h["examples"]:
        print(f"     Exemples :")
        for ex in h["examples"][:3]:
            print(f"       • {ex['actor']:>12} → {ex['action'][:40]}")
            print(f"         ↳ {ex['reason'][:60]}")
    print()

    # Doublons
    d = report["semantic_duplicates"]
    print(f"  ♻️  DOUBLONS SÉMANTIQUES (sim ≥ 85%)")
    print(f"     Paires trouvées : {d['count']} ({d['rate_pct']}%)")
    if d["examples"]:
        for ex in d["examples"][:3]:
            print(f"       • [{ex['sim']:.2f}] {ex['actor']:>10} | {ex['rule_a'][:35]}")
            print(f"              ≈ {ex['rule_b'][:35]}")
    print()

    # Qualité articles
    a = report["article_quality"]
    print(f"  📄 QUALITÉ DES RÉFÉRENCES D'ARTICLES")
    print(f"     Sans référence     : {a['no_article']}")
    print(f"     Référence vague    : {a['vague_article']}")
    print(f"     Taux qualité       : {a['quality_rate_pct']}%")
    print()

    # Quality scores
    q = report["quality_scores"]
    print(f"  ⭐ QUALITY SCORES (extraction LLM)")
    print(f"     Min / Moy / Max    : {q['min']} / {q['avg']} / {q['max']}")
    print(f"     Règles qualité < 6 : {q['low_quality_count']}")
    print()

    # Acteurs
    ac = report["actors"]
    print(f"  👤 ACTEURS")
    print(f"     Normalisés : {ac['standardized']}/{report['total_rules']} ({ac['standardized_pct']}%)")
    print(f"     Top : {dict(list(ac['top_actors'].items())[:4])}")
    print()

    # Statuts
    st = report["status_distribution"]
    total_s = sum(st.values())
    print(f"  📊 DISTRIBUTION STATUTS")
    for s, n in st.items():
        bar_s = "█" * round(n / total_s * 20) if total_s else ""
        print(f"     {s:>12} : {n:>3} ({n/total_s*100:.1f}%)  {bar_s}")
    print()

    # Recommandations
    print(f"  💡 RECOMMANDATIONS")
    for i, rec in enumerate(report["recommendations"], 1):
        # Wrap à 60 chars
        words = rec.split()
        line = ""
        lines = []
        for w in words:
            if len(line) + len(w) + 1 > 58:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            lines.append(line)
        print(f"     {i}. {lines[0]}")
        for l in lines[1:]:
            print(f"        {l}")
    print()
    print(sep + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# COMPARAISON DEUX VERSIONS
# ══════════════════════════════════════════════════════════════════════════════

def compare_versions(path_v1: str, path_v2: str) -> None:
    """Compare le taux de hallucination entre deux versions d'extraction."""
    with open(path_v1, encoding="utf-8") as f:
        rules_v1 = json.load(f)
    with open(path_v2, encoding="utf-8") as f:
        rules_v2 = json.load(f)

    r1 = evaluate(rules_v1)
    r2 = evaluate(rules_v2)

    print(f"\n{'═'*65}")
    print(f"  COMPARAISON VERSIONS")
    print(f"{'═'*65}")
    print(f"  {'Métrique':<35} {'V1':>8}  {'V2':>8}  {'Delta':>8}")
    print(f"  {'-'*60}")

    metrics = [
        ("Règles totales",         r1['total_rules'],                     r2['total_rules']),
        ("Hallucinations (%)",     r1['hallucination']['rate_pct'],       r2['hallucination']['rate_pct']),
        ("Règles propres (%)",     r1['hallucination']['clean_rate_pct'], r2['hallucination']['clean_rate_pct']),
        ("Doublons (%)",           r1['semantic_duplicates']['rate_pct'], r2['semantic_duplicates']['rate_pct']),
        ("Quality score moy.",     r1['quality_scores']['avg'],           r2['quality_scores']['avg']),
        ("Acteurs normalisés (%)", r1['actors']['standardized_pct'],      r2['actors']['standardized_pct']),
        ("Score fiabilité",        r1['reliability_score'],               r2['reliability_score']),
    ]

    for label, v1, v2 in metrics:
        delta = v2 - v1 if isinstance(v1, (int, float)) else "—"
        icon  = "↑" if delta > 0 else ("↓" if delta < 0 else "=") if isinstance(delta, (int, float)) else "—"
        print(f"  {label:<35} {str(v1):>8}  {str(v2):>8}  {icon}{abs(delta) if isinstance(delta, (int, float)) else '':>7}")

    print(f"\n  Grade V1 : {r1['reliability_grade']} ({r1['reliability_score']}/100)")
    print(f"  Grade V2 : {r2['reliability_grade']} ({r2['reliability_score']}/100)")
    print(f"{'═'*65}\n")


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT JSON
# ══════════════════════════════════════════════════════════════════════════════

def save_report(report: dict, output_path: str = None) -> str:
    """Sauvegarde le rapport en JSON."""
    if not output_path:
        output_path = str(DATA_DIR / f"eval_report_{report['eval_date']}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        description="Évaluation de la qualité d'extraction LLM — BO5"
    )
    p.add_argument("--rules",   default=str(RULES_PATH),
                   help=f"Chemin vers rules_clean.json (défaut: {RULES_PATH})")
    p.add_argument("--compare", nargs=2, metavar=("V1", "V2"),
                   help="Comparer deux versions : --compare rules_v1.json rules_v2.json")
    p.add_argument("--save",    action="store_true",
                   help="Sauvegarder le rapport en JSON dans data/")
    p.add_argument("--quiet",   action="store_true",
                   help="Afficher seulement le score global")
    args = p.parse_args()

    if args.compare:
        compare_versions(args.compare[0], args.compare[1])
        return

    rules_path = Path(args.rules)
    if not rules_path.exists():
        print(f"❌ Fichier introuvable : {rules_path}")
        print(f"   Lancez d'abord : python main.py --step all")
        return

    with open(rules_path, encoding="utf-8") as f:
        rules = json.load(f)

    report = evaluate(rules)

    if args.quiet:
        h = report["hallucination"]
        print(f"Fiabilité: {report['reliability_score']}/100 [{report['reliability_grade']}] "
              f"| Hallucinations: {h['rate_pct']}% | Propres: {h['clean_rate_pct']}%")
        return

    print_report(report)

    if args.save:
        out = save_report(report)
        print(f"  Rapport sauvegardé : {out}")


if __name__ == "__main__":
    main()
