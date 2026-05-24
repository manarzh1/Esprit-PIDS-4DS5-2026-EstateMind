"""
compliance.py
─────────────────────────────────────────────────────────────────
DS04 — Moteur de conformité
DS02 — Détection de changements (simulation)
Alertes — console + log fichier + webhook optionnel

BO5 — Code des Droits Réels tunisien
"""

import json, re, hashlib, logging
from datetime import date, datetime
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter
from typing import Optional

# Matching sémantique avec MiniLM (déjà téléchargé par le pipeline)
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    _HAS_SEMANTIC = True
except ImportError:
    _HAS_SEMANTIC = False

from config import (
    RULES_CLEAN, LOG_DIR, DOMAIN_KW,
    ALERT_THRESHOLD, WEBHOOK_URL, SOURCE_NAME,
    COMPLIANCE_THRESHOLD,
)

TODAY = str(date.today())

# ── Mots-clés Urbanisme ───────────────────────────────────────────────────────
# Si la requête contient ces mots → consulter le RAG Urbanisme
URBANISME_KW = {
    "construire", "construction", "permis de construire",
    "autorisation de construire", "démolir", "démolition",
    "lotissement", "morcellement", "zone constructible",
    "zone non constructible", "alignement", "voirie",
    "permis d occuper", "recolement", "infraction",
    "edifier", "edifice", "batir", "bâtir",
    "clôture", "cloture", "mur de cloture",
}


def is_urbanisme_question(user_case: dict) -> bool:
    """Détecte si la question concerne le Code de l'Urbanisme."""
    bag = " ".join([
        user_case.get("actor",  ""),
        user_case.get("action", ""),
        user_case.get("target", ""),
        " ".join(user_case.get("conditions", [])),
    ]).lower()
    return any(kw in bag for kw in URBANISME_KW)


def compute_urbanisme_risk(rag_results: list, user_case: dict) -> dict:
    """
    Calcule un risk score depuis les résultats RAG Urbanisme.
    Prend en compte le contexte utilisateur (conditions) + le texte RAG.
    """
    if not rag_results:
        return {"risk_score": 0, "status": "UNKNOWN", "articles": []}

    # Analyser TOUS les résultats RAG, pas seulement le premier
    all_txt = " ".join(r["text"].lower() for r in rag_results)
    best      = rag_results[0]
    relevance = best["score"]

    # Contexte utilisateur
    action = user_case.get("action", "").lower()
    conds  = " ".join(user_case.get("conditions", [])).lower()
    target = user_case.get("target", "").lower()
    full_context = f"{action} {conds} {target}"

    # PRIORITÉ 1 : conditions utilisateur "sans permis" → interdit direct
    if any(w in full_context for w in [
        "sans permis", "sans autorisation", "sans accord",
        "illegalement", "clandestinement"
    ]):
        base   = 60
        status = "interdit"

    # PRIORITÉ 2 : zone non constructible → interdit
    elif any(w in full_context for w in [
        "zone non constructible", "zone interdite", "zone protegee",
        "non constructible"
    ]):
        base   = 60
        status = "interdit"

    # PRIORITÉ 3 : détecter depuis le texte RAG
    elif any(w in all_txt for w in [
        "est interdite", "sont interdites", "il est interdit",
        "infraction", "sanction", "ne peut pas", "ne peuvent pas"
    ]):
        base   = 60
        status = "interdit"

    elif any(w in all_txt for w in [
        "est tenu d'obtenir", "doit obtenir", "est obligatoire",
        "doit etre", "il est necessaire", "tenu de"
    ]):
        base   = 40
        status = "obligation"

    else:
        base   = 15
        status = "permis"

    # Bonus action à haut risque UNIQUEMENT si conditions négatives présentes
    # Sans "sans permis" ou "sans autorisation" → pas de bonus
    has_negative_cond = any(w in full_context for w in [
        "sans permis", "sans autorisation", "sans accord",
        "illegalement", "non constructible", "zone interdite"
    ])
    bonus = 10 if (has_negative_cond and any(v in action for v in [
        "démolir", "construire", "lotir", "morceler", "édifier", "batir"
    ])) else 0

    # Malus si conditions favorables
    malus = -15 if any(w in full_context for w in [
        "avec autorisation", "avec permis", "avec accord"
    ]) else 0

    # Score final
    raw   = base + bonus + malus
    score = int(min(100, max(0, raw * max(relevance * 1.5, 0.8))))

    articles = [
        f"Art.{r['article']} — {r.get('source_label', 'CATU')}"
        for r in rag_results[:3]
    ]

    return {
        "risk_score": score,
        "status":     status,
        "articles":   articles,
        "source":     "URBANISME",
        "law":        "Code de l'Aménagement du Territoire — 2011",
        "relevance":  round(relevance, 3),
    }

_fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
log = logging.getLogger("compliance")
log.setLevel(logging.INFO)
if not log.handlers:
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "compliance.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)


# ══════════════════════════════════════════════════════════════════════════════
# DS04 — MOTEUR DE CONFORMITÉ
# ══════════════════════════════════════════════════════════════════════════════

_STOP = {
    "le","la","les","un","une","des","de","du","en","et","ou",
    "sur","dans","par","pour","au","aux","son","sa","ses",
    "leur","leurs","ce","cet","cette","ces","à","se","ne","pas",
}

# ── Groupes d'acteurs sémantiquement proches ──────────────────────────────────
# Un acteur ne peut matcher que des règles de son groupe ou d'un groupe parent.
# Cela empêche "locataire" de matcher les règles de "vendeur".
_ACTOR_GROUPS: dict[str, set[str]] = {
    # Propriétaires / droits réels directs
    "proprietaire":   {"proprietaire", "particulier", "personne", "citoyen"},
    "copropriétaire": {"copropriétaire", "coindivisaire", "proprietaire", "particulier"},
    "coindivisaire":  {"coindivisaire", "copropriétaire", "proprietaire", "particulier"},
    "possesseur":     {"possesseur", "particulier", "personne"},
    "usufruitier":    {"usufruitier", "particulier", "personne"},
    "emphytéote":     {"emphytéote", "preneur", "particulier"},
    "superficiaire":  {"superficiaire", "particulier"},
    # Bail
    "locataire":      {"locataire", "preneur", "particulier", "personne"},
    "bailleur":       {"bailleur", "proprietaire", "particulier"},
    "preneur":        {"preneur", "locataire", "emphytéote", "particulier"},
    # Transactions
    "acquéreur":      {"acquéreur", "particulier", "personne"},
    "vendeur":        {"vendeur", "proprietaire", "particulier"},
    "héritier":       {"héritier", "particulier", "personne"},
    "légataire":      {"légataire", "héritier", "particulier"},
    # Crédit / sûretés
    "créancier":      {"créancier", "particulier", "personne"},
    "débiteur":       {"débiteur", "particulier", "personne"},
    # Autorités
    "etat":           {"etat", "autorite_locale"},
    "autorite_locale":{"autorite_locale", "etat"},
    "tribunal":       {"tribunal"},
    "notaire":        {"notaire"},
    "conservateur":   {"conservateur"},
    # Génériques (matchent tout)
    "particulier":    None,   # None = pas de restriction
    "personne":       None,
    "citoyen":        None,
    "tiers":          None,
}

# Seuil minimal que doit atteindre le score acteur seul pour qu'une règle soit
# considérée (évite qu'une action à 0.87 compense un acteur à 0.12)
_ACTOR_MIN_SIM  = 0.35

# Seuil minimal de similarité action — évite qu'un actor=1.0 compense
# une action différente (ex: "vendre" != "peindre", "vendre" != "déposer")
_ACTION_MIN_SIM = 0.35


def _sim(a: str, b: str) -> float:
    """Similarité sémantique hybride [0..1]."""
    if not a or not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.87
    base = SequenceMatcher(None, a, b).ratio()
    wa   = set(a.split()) - _STOP
    wb   = set(b.split()) - _STOP
    if wa and wb:
        base = min(1.0, base + (len(wa & wb) / max(len(wa), len(wb))) * 0.3)
    return round(base, 3)


def _actor_sim(user_actor: str, rule_actor: str) -> float:
    """
    CORRECTION 1 — Similarité acteur avec vérification de groupe.

    Si l'acteur utilisateur appartient à un groupe défini ET que l'acteur
    de la règle n'est pas dans ce groupe (ni générique), retourne 0.
    Cela empêche "locataire→vendre" de matcher "vendeur→vendre".
    """
    ua = user_actor.lower().strip()
    ra = rule_actor.lower().strip()

    base = _sim(ua, ra)

    # Récupérer le groupe de l'acteur utilisateur
    group = _ACTOR_GROUPS.get(ua)

    if group is None:
        # Acteur générique (particulier, personne…) : pas de restriction
        return base

    # L'acteur de la règle est-il dans le groupe autorisé ?
    if ra in group:
        return base   # OK, score normal

    # L'acteur de la règle est-il générique (None = pas de restriction) ?
    if _ACTOR_GROUPS.get(ra) is None:
        return base   # OK, règle générique

    # Acteur hors groupe → similarité plafonnée à 0.20 (signal faible, jamais bloquant)
    return min(base, 0.20)



# ══════════════════════════════════════════════════════════════════════════════
# MATCHING SÉMANTIQUE — utilise MiniLM pour comprendre le SENS
# ══════════════════════════════════════════════════════════════════════════════

_SEM_MODEL = None
_RULES_EMBEDDINGS = None
_RULES_HASH = None


def _get_semantic_model():
    """Charge MiniLM une seule fois (lazy-loading)."""
    global _SEM_MODEL
    if _SEM_MODEL is None and _HAS_SEMANTIC:
        log.info("Chargement du modèle sémantique (1re fois)...")
        _SEM_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _SEM_MODEL


def _encode_rules(rules: list) -> "np.ndarray":
    """
    Encode toutes les règles en vecteurs sémantiques (une fois par session).
    Cache invalidé si les règles changent (hash).
    """
    global _RULES_EMBEDDINGS, _RULES_HASH

    # Hash des règles pour détecter les changements
    h = hash(tuple((r.get("actor",""), r.get("action",""), r.get("target",""))
                   for r in rules))
    if _RULES_EMBEDDINGS is not None and _RULES_HASH == h:
        return _RULES_EMBEDDINGS

    model = _get_semantic_model()
    if model is None:
        return None

    # Construire une phrase descriptive par règle
    texts = [
        f"{r.get('actor','')} {r.get('action','')} {r.get('target','')}".strip()
        for r in rules
    ]
    log.info(f"Encodage sémantique de {len(texts)} règles...")
    _RULES_EMBEDDINGS = model.encode(
        texts, batch_size=32, show_progress_bar=False,
        convert_to_numpy=True, normalize_embeddings=True,
    )
    _RULES_HASH = h
    return _RULES_EMBEDDINGS


def _semantic_match(user: dict, rules: list) -> list:
    """
    Calcule la similarité sémantique entre la question utilisateur
    et chaque règle. Retourne les scores cosinus (entre 0 et 1).
    """
    if not _HAS_SEMANTIC:
        return [0.0] * len(rules)

    model = _get_semantic_model()
    if model is None:
        return [0.0] * len(rules)

    rules_embs = _encode_rules(rules)
    if rules_embs is None:
        return [0.0] * len(rules)

    # Encoder la question utilisateur
    user_text = (
        f"{user.get('actor','')} {user.get('action','')} "
        f"{user.get('target','')}".strip()
    )
    user_emb = model.encode(
        [user_text], convert_to_numpy=True, normalize_embeddings=True,
    )[0]

    # Similarité cosinus (embeddings normalisés → produit scalaire = cosinus)
    scores = (rules_embs @ user_emb).tolist()
    return [max(0.0, float(s)) for s in scores]


def _match_scores(user: dict, rule: dict,
                  semantic_score: float = 0.0) -> tuple[float, float, float, float]:
    """
    Matching HYBRIDE = 50% lexical + 50% sémantique.

    Lexical  : actor (40%) + action (45%) + target (15%)
               Détecte les correspondances mot-à-mot exactes.
    Sémantique : MiniLM comprend "construire"≈"bâtir", "vendre"≈"céder"
                 Détecte les paraphrases et synonymes juridiques.

    Retourne (total_hybride, actor_sim, action_sim, target_sim).
    """
    a_s  = _actor_sim(user.get("actor",  ""), rule.get("actor",  ""))
    ac_s = _sim(user.get("action", ""), rule.get("action", ""))

    # Target vide dans la règle = 0.5 (neutre)
    if rule.get("target"):
        t_s = _sim(user.get("target", ""), rule.get("target", ""))
    else:
        t_s = 0.5

    # Score lexical (méthode originale)
    lexical = a_s * 0.40 + ac_s * 0.45 + t_s * 0.15

    # Score HYBRIDE : 50% lexical + 50% sémantique
    # Le sémantique apporte la compréhension du sens,
    # le lexical garde la précision sur les noms propres et acteurs
    if semantic_score > 0:
        total = round(0.5 * lexical + 0.5 * semantic_score, 3)
    else:
        total = round(lexical, 3)

    return total, a_s, ac_s, t_s


def _actor_ok(user_actor: str, rule_actor: str) -> bool:
    """
    CORRECTION 1 (gate dure) — L'acteur doit atteindre le seuil minimal.
    Si la similarité acteur < _ACTOR_MIN_SIM, la règle est rejetée
    même si l'action matche parfaitement.
    """
    return _actor_sim(user_actor, rule_actor) >= _ACTOR_MIN_SIM


# ── Paires contradictoires conditions ────────────────────────────────────────
# Si l'utilisateur fournit une condition A et la règle exige ~A → skip la règle
_CONDITION_CONTRADICTIONS = [
    # (mots de l'utilisateur, mots interdits dans la règle)
    ({"autorisation", "permis", "autorisé", "autorisée"},
     {"sans autorisation", "sans permis"}),
    ({"notaire", "authentique", "acte authentique"},
     {"sans notaire", "sans acte"}),
    ({"accord", "consentement", "permission"},
     {"sans accord", "sans consentement"}),
]


def _rule_contradicts_user(user: dict, rule: dict) -> bool:
    """
    Retourne True si les conditions de la règle contredisent
    explicitement les conditions fournies par l'utilisateur.

    Exemple :
        user conditions = ["avec autorisation"]
        rule action     = "construire sans autorisation"
        → True  (la règle s'applique au cas SANS autorisation, pas au cas avec)
    """
    user_conds = " ".join(user.get("conditions", [])).lower()
    if not user_conds:
        return False

    # Vérifier aussi l'action de la règle (ex: "construire sans autorisation")
    rule_action = rule.get("action", "").lower()
    rule_conds  = " ".join(rule.get("conditions", [])).lower()
    rule_text   = rule_action + " " + rule_conds

    for user_signals, rule_negations in _CONDITION_CONTRADICTIONS:
        # L'utilisateur a fourni une condition positive (ex: "avec autorisation")
        user_has_positive = any(sig in user_conds for sig in user_signals)
        # La règle parle d'une situation négative (ex: "sans autorisation")
        rule_has_negation = any(neg in rule_text for neg in rule_negations)
        if user_has_positive and rule_has_negation:
            return True

    return False


def _missing_conditions(user: dict, rule: dict) -> list[str]:
    """Conditions de la règle non satisfaites par le cas utilisateur."""
    rule_conds = rule.get("conditions", [])
    if not rule_conds:
        return []
    user_bag = " ".join(user.get("conditions", [])).lower()
    missing  = []
    for cond in rule_conds:
        words = [w for w in re.findall(r"\w{4,}", cond.lower()) if w not in _STOP]
        if not words:
            continue
        matched = sum(1 for w in words if w in user_bag)
        if matched / len(words) < 0.40:
            missing.append(cond)
    return missing


def check_compliance(
    user_case:   dict,
    rules:       Optional[list[dict]] = None,
    threshold:   float = 0.55,  # seuil relevé (0.45→0.55) pour réduire les faux positifs
    max_results: int   = 10,
) -> dict:
    """
    DS04 — Vérification de conformité d'un cas utilisateur.

    INPUT :
        {
            "actor":      "proprietaire",
            "action":     "construire",
            "target":     "immeuble",
            "conditions": ["avec permis de construire"]   ← optionnel
        }

    CORRECTIONS APPLIQUÉES :
        1. Gate acteur : si actor_sim < 0.35, la règle est ignorée
           → empêche "locataire" de matcher les règles de "vendeur"
        2. Groupes d'acteurs : chaque acteur ne peut matcher que
           son groupe sémantique (locataire ≠ vendeur ≠ propriétaire)
        3. Pondération 40/45/15 au lieu de 30/50/20
           → l'acteur pèse davantage, l'action ne peut plus tout compenser
        4. Target vide = 0.5 (neutre) au lieu de 1.0 (bonus injustifié)
        5. UNKNOWN → WARNING si action potentiellement sensible sans règle explicite

    LOGIQUE :
        interdit  + match ≥ threshold + actor_ok → violation  🚨
        obligation + conditions manquantes        → warning    ⚠️
        obligation + conditions OK               → compliant  ✅
        permis    + match ≥ threshold            → ok         🟢
        aucun match                              → unknown    ❓
        hors domaine                             → out_of_domain ℹ️

    OUTPUT :
        {
            "compliant":       bool,
            "violations":      [...],
            "warnings":        [...],
            "compliant_rules": [...],
            "ok_rules":        [...],
            "risk_score":      int,
            "global_status":   str,
            "explanations":    [...],
            "meta":            {...}
        }
    """
    if rules is None:
        if not RULES_CLEAN.exists():
            return {"error": "rules_clean.json introuvable — lancez le pipeline."}
        with open(RULES_CLEAN, encoding="utf-8") as f:
            rules = json.load(f)

    # Vérification domaine
    bag = " ".join([
        user_case.get("actor",  ""),
        user_case.get("action", ""),
        user_case.get("target", ""),
    ]).lower()
    if not any(kw in bag for kw in DOMAIN_KW):
        return {
            "compliant":       True,
            "violations":      [],
            "warnings":        [],
            "compliant_rules": [],
            "ok_rules":        [],
            "risk_score":      0,
            "global_status":   "OUT_OF_DOMAIN",
            "explanations": [
                "La situation ne relève pas du Code des Droits Réels tunisien. "
                "Domaines couverts : propriété, foncier, hypothèque, "
                "servitudes, usufruit, copropriété, immatriculation foncière."
            ],
            "meta": {"rules_checked": len(rules), "threshold": threshold},
        }

    violations:     list[dict] = []
    warnings:       list[dict] = []
    compliant_rules:list[dict] = []
    ok_rules:       list[dict] = []
    explanations:   list[str]  = []

    user_actor  = user_case.get("actor",  "").lower().strip()
    user_action = user_case.get("action", "").lower().strip()

    # Calculer les scores sémantiques pour TOUTES les règles (une seule fois)
    semantic_scores = _semantic_match(user_case, rules) if _HAS_SEMANTIC else []

    for i, rule in enumerate(rules):
        # GATE 1 : rejet immédiat si l'acteur est incompatible
        if not _actor_ok(user_actor, rule.get("actor", "")):
            continue

        # GATE 2 : pré-filtre action — avec boost sémantique
        # Le gate lexical est assoupli si le score sémantique est élevé
        sem_score = semantic_scores[i] if semantic_scores else 0.0
        action_lex = _sim(user_action, rule.get("action", "").lower())
        # Si sémantique fort (≥0.5), on accepte action_lex plus bas
        action_min = _ACTION_MIN_SIM * 0.5 if sem_score >= 0.5 else _ACTION_MIN_SIM
        if action_lex < action_min:
            continue

        total, a_s, ac_s, t_s = _match_scores(user_case, rule, sem_score)
        if total < threshold:
            continue

        # GATE 3 : si les conditions de l'utilisateur contredisent la règle
        # ex: user dit "avec autorisation" mais règle dit "sans autorisation"
        # → ignorer cette règle (ne s'applique pas à ce cas)
        if _rule_contradicts_user(user_case, rule):
            continue

        status  = rule["status"]
        risk    = rule.get("risk_score", 0)
        article = rule.get("article", "") or rule.get("article_ref", "")
        missing = _missing_conditions(user_case, rule)

        base_item = {
            "risk_score":   risk,
            "match_score":  total,
            "actor_sim":    a_s,
            "action_sim":   ac_s,
            "target_sim":   t_s,
            "article":      article,
            "rule": {
                "actor":      rule["actor"],
                "action":     rule["action"],
                "target":     rule.get("target", ""),
                "status":     status,
                "conditions": rule.get("conditions", []),
            },
        }

        if status == "interdit":
            msg = (
                f"VIOLATION : '{rule['action']}' est interdit pour "
                f"'{rule['actor']}'"
                + (f" sur '{rule['target']}'" if rule.get("target") else "")
                + f". → {article}"
            )
            violations.append({**base_item, "message": msg})
            explanations.append(f"🚨 [{risk}/100] {msg}")

        elif status == "obligation":
            if missing:
                msg = (
                    f"AVERTISSEMENT : '{rule['action']}' est obligatoire pour "
                    f"'{rule['actor']}' mais conditions manquantes : "
                    + " | ".join(missing)
                    + f". → {article}"
                )
                warnings.append({**base_item, "message": msg,
                                  "missing_conditions": missing})
                explanations.append(f"⚠️  [{risk}/100] {msg}")
            else:
                msg = (
                    f"CONFORME : '{rule['action']}' respecté "
                    f"par '{rule['actor']}'. → {article}"
                )
                compliant_rules.append({**base_item, "message": msg})
                explanations.append(f"✅ [{risk}/100] {msg}")

        elif status == "permis":
            msg = (
                f"AUTORISÉ : '{rule['action']}' est permis "
                f"pour '{rule['actor']}'. → {article}"
            )
            ok_rules.append({**base_item, "message": msg})
            explanations.append(f"🟢 [{risk}/100] {msg}")

    for lst in [violations, warnings, compliant_rules, ok_rules]:
        lst.sort(key=lambda x: -x["risk_score"])

    violations      = violations[:max_results]
    warnings        = warnings[:max_results]
    compliant_rules = compliant_rules[:max_results]
    ok_rules        = ok_rules[:max_results]

    max_risk = max(
        [v["risk_score"] for v in violations] +
        [w["risk_score"] for w in warnings] + [0]
    )

    # CORRECTION 5 — Si aucune règle ne matche, le résultat est UNKNOWN
    # (≠ COMPLIANT, qui signifie "conforme à une règle connue")
    has_any = bool(violations or warnings or compliant_rules or ok_rules)

    if violations:
        global_status = "VIOLATION"
    elif warnings:
        global_status = "WARNING"
    elif has_any:
        global_status = "COMPLIANT"
    else:
        # Aucune règle trouvée pour cet acteur+action → on ne peut pas dire conforme
        global_status = "UNKNOWN"
        explanations.append(
            f"❓ Aucune règle trouvée dans le Code des Droits Réels tunisien "
            f"pour '{user_actor}' → '{user_action}'. "
            f"Cela ne signifie pas que l'action est autorisée. "
            f"Consultez un juriste spécialisé."
        )

    return {
        "compliant":       global_status in ("COMPLIANT",),
        "violations":      violations,
        "warnings":        warnings,
        "compliant_rules": compliant_rules,
        "ok_rules":        ok_rules,
        "risk_score":      max_risk,
        "global_status":   global_status,
        "explanations":    explanations,
        "meta": {
            "user_case":     user_case,
            "rules_checked": len(rules),
            "matches_found": len(violations)+len(warnings)+len(compliant_rules)+len(ok_rules),
            "threshold":     threshold,
            "source":        SOURCE_NAME,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# DS02 — DÉTECTION DE CHANGEMENTS
# ══════════════════════════════════════════════════════════════════════════════

def detect_changes(
    current_path:  str,
    previous_path: str,
    out_path:      Optional[str] = None,
) -> dict:
    """
    DS02 — Compare deux versions de rules_clean.json.
    Clé : rule_hash (MD5 de actor|action|target|status).

    Retourne : { summary, added, removed, modified }
    Simule la veille réglementaire même avec un seul PDF.
    """
    log.info(f"[DS02] Diff : {current_path} ↔ {previous_path}")

    def _load(path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            rules = json.load(f)
        return {
            r.get("rule_hash") or hashlib.md5(
                f"{r['actor']}|{r['action']}|{r.get('target','')}|{r['status']}".encode()
            ).hexdigest(): r
            for r in rules
        }

    curr = _load(current_path)
    prev = _load(previous_path)

    added   = [v for k, v in curr.items() if k not in prev]
    removed = [v for k, v in prev.items() if k not in curr]
    modified = []
    for k in curr:
        if k in prev:
            rc = curr[k].get("risk_score", 0)
            rp = prev[k].get("risk_score", 0)
            sc = curr[k].get("status", "")
            sp = prev[k].get("status", "")
            if rc != rp or sc != sp:
                modified.append({
                    "rule":          curr[k],
                    "risk_before":   rp,
                    "risk_after":    rc,
                    "delta":         rc - rp,
                    "direction":     "↑" if rc > rp else "↓",
                    "status_before": sp,
                    "status_after":  sc,
                })
    modified.sort(key=lambda x: -abs(x["delta"]))

    diff = {
        "diff_date":      TODAY,
        "current_file":   current_path,
        "previous_file":  previous_path,
        "summary": {
            "total_current":  len(curr),
            "total_previous": len(prev),
            "added":          len(added),
            "removed":        len(removed),
            "modified":       len(modified),
        },
        "added":    added,
        "removed":  removed,
        "modified": modified,
    }

    dest = out_path or str(Path(current_path).parent / f"diff_{TODAY}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    log.info(
        f"       → ajoutées={len(added)} supprimées={len(removed)} "
        f"modifiées={len(modified)} → {dest}"
    )

    # Alertes sur changements critiques
    for item in modified:
        if item["risk_after"] >= ALERT_THRESHOLD:
            send_alert({
                "type":       "regulatory_change",
                "risk_score": item["risk_after"],
                "rule":       item["rule"],
                "message": (
                    f"Changement critique : '{item['rule']['action']}' "
                    f"risk {item['risk_before']}→{item['risk_after']} {item['direction']}"
                ),
            })

    return diff


# ══════════════════════════════════════════════════════════════════════════════
# ALERTES
# ══════════════════════════════════════════════════════════════════════════════

def send_alert(alert: dict) -> None:
    """Alerte multi-canal : log fichier + console + email SMTP + webhook optionnel."""
    risk = alert.get("risk_score", 0)
    sev  = ("CRITICAL" if risk >= 80 else "HIGH" if risk >= 70
            else "MEDIUM" if risk >= 50 else "LOW")

    payload = {
        "timestamp":  datetime.now().isoformat(),
        "alert_type": alert.get("type", ""),
        "severity":   sev,
        "risk_score": risk,
        "message":    alert.get("message", ""),
        "rule":       alert.get("rule", {}),
    }

    # Log fichier
    al = logging.getLogger("alerts")
    if not al.handlers:
        fh = logging.FileHandler(LOG_DIR / "alerts.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        al.addHandler(fh); al.setLevel(logging.WARNING)
    al.log(
        logging.CRITICAL if risk >= 80 else logging.WARNING,
        json.dumps(payload, ensure_ascii=False)
    )

    # Console
    icons = {"CRITICAL": "[CRITIQUE]", "HIGH": "[ELEVE]", "MEDIUM": "[MOYEN]", "LOW": "[INFO]"}
    print(f"\n{icons[sev]} ALERTE risk={risk}/100 : {alert.get('message','')}")
    rule = alert.get("rule", {})
    if isinstance(rule, dict) and rule.get("article"):
        print(f"   article : {rule['article']}")

    # Email via config alertes utilisateur
    try:
        from alerts import load_alerts_config, send_alert_notification
        config = load_alerts_config()
        if config.get("email") and risk >= config.get("risk_threshold", ALERT_THRESHOLD):
            send_alert_notification({**alert, "type": alert.get("type","compliance_violation")}, config)
    except Exception as e:
        log.warning(f"Alerte email echec : {e}")

    # Webhook optionnel
    if WEBHOOK_URL:
        try:
            import urllib.request
            data = json.dumps(payload, ensure_ascii=False).encode()
            req  = urllib.request.Request(
                WEBHOOK_URL, data=data,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            log.warning(f"Webhook echoue : {e}")


def check_and_alert(result: dict) -> None:
    """Déclenche les alertes pour les violations/warnings à haut risque."""
    for v in result.get("violations", []):
        if v["risk_score"] >= ALERT_THRESHOLD:
            send_alert({
                "type":       "compliance_violation",
                "risk_score": v["risk_score"],
                "rule":       v.get("rule", {}),
                "message":    v.get("message", ""),
            })
    for w in result.get("warnings", []):
        if w["risk_score"] >= ALERT_THRESHOLD:
            send_alert({
                "type":       "compliance_warning",
                "risk_score": w["risk_score"],
                "rule":       w.get("rule", {}),
                "message":    w.get("message", ""),
            })