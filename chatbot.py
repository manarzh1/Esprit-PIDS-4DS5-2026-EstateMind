"""
chatbot.py
─────────────────────────────────────────────────────────────────
Chatbot juridique TuniState — BO5
Utilise Mistral local (Ollama) pour répondre aux questions
juridiques en français naturel, en s'appuyant sur :
  1. Les 66 règles CDR extraites (rules_clean.json)
  2. Le RAG sur le texte brut du CDR et du Code de l'Urbanisme

Prompt dynamique selon la source détectée :
  - CDR       → Code des Droits Réels — Loi n°65-5
  - URBANISME → Code de l'Aménagement du Territoire — 2011
  - MIXTE     → Les deux codes cités
"""

import json, logging, urllib.request, urllib.error
from pathlib import Path
from config  import OLLAMA_URL, LLM_MODEL, LOG_DIR, RULES_CLEAN

log = logging.getLogger("chatbot")
log.setLevel(logging.INFO)
if not log.handlers:
    _fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "chatbot.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)


# ══════════════════════════════════════════════════════════════════
# CHARGEMENT DES RÈGLES
# ══════════════════════════════════════════════════════════════════

def _load_rules() -> list[dict]:
    if RULES_CLEAN.exists():
        with open(RULES_CLEAN, encoding="utf-8") as f:
            return json.load(f)
    return []


def _find_relevant_rules(question: str, rules: list[dict], top_k: int = 5) -> list[dict]:
    """Trouve les règles CDR les plus pertinentes pour la question."""
    q = question.lower()
    scored = []

    for r in rules:
        score  = 0
        actor  = r.get("actor",  "").lower()
        action = r.get("action", "").lower()
        target = r.get("target", "").lower()

        words = [w for w in q.split() if len(w) > 3]
        for w in words:
            if w in actor:  score += 3
            if w in action: score += 4
            if w in target: score += 2

        legal_kw = {
            "sous-louer": ["sous-louer", "sous-location"],
            "hypothèque": ["hypothèque", "hypotheque", "hypothéquer"],
            "exproprier": ["exproprier", "expropriation"],
            "usufruit":   ["usufruit", "usufruitier"],
            "gage":       ["gage", "nantissement"],
            "bail":       ["bail", "locataire", "bailleur"],
            "vendre":     ["vendre", "vente", "céder"],
            "démolir":    ["démolir", "détruire", "destruction"],
        }
        for kw, variants in legal_kw.items():
            if any(v in q for v in variants):
                if any(v in action or v in actor for v in variants):
                    score += 5

        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:top_k]]


def _format_rules_context(rules: list[dict]) -> str:
    """Formate les règles CDR en contexte lisible pour Mistral."""
    if not rules:
        return ""
    lines = ["Règles du Code des Droits Réels tunisien (Loi n°65-5) :"]
    for i, r in enumerate(rules, 1):
        line = (
            f"{i}. [Art.{r.get('article','?')}] "
            f"{r.get('actor','?')} → {r.get('action','?')}"
        )
        if r.get("target"):
            line += f" ({r['target']})"
        line += f" | {r.get('status','?').upper()}"
        if r.get("risk_score"):
            line += f" | Risque: {r['risk_score']}/100"
        if r.get("conditions"):
            line += f" | Conditions: {', '.join(r['conditions'])}"
        lines.append(line)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# PROMPTS DYNAMIQUES SELON LA SOURCE
# ══════════════════════════════════════════════════════════════════

_PROMPT_CDR = """Tu es TuniState, un assistant juridique expert en droit immobilier tunisien.
Tu te bases sur le Code des Droits Réels tunisien (CDR — Loi n°65-5 du 12 février 1965).

RÈGLES :
- Réponds TOUJOURS en français
- Cite les articles du CDR (ex: "Selon l'article 14 du CDR")
- Mentionne le score de risque si disponible (0-100)
- Si tu n'es pas sûr, recommande un notaire
- Sois concis : 3-5 phrases maximum
- Termine par une recommandation pratique"""

_PROMPT_URBANISME = """Tu es TuniState, un assistant juridique expert en droit immobilier tunisien.
Tu te bases sur le Code de l'Aménagement du Territoire et de l'Urbanisme tunisien (CATU — 2011).

RÈGLES :
- Réponds TOUJOURS en français
- Cite les articles du CATU (ex: "Selon l'article 23 du Code de l'Urbanisme")
- Ne confonds PAS avec le droit français — tu parles du droit TUNISIEN uniquement
- Si tu n'es pas sûr, recommande un architecte ou un notaire
- Sois concis : 3-5 phrases maximum
- Termine par une recommandation pratique"""

_PROMPT_MIXTE = """Tu es TuniState, un assistant juridique expert en droit immobilier tunisien.
Tu te bases sur deux codes juridiques tunisiens :
  1. Le Code des Droits Réels (CDR — Loi n°65-5 du 12 février 1965)
  2. Le Code de l'Aménagement du Territoire et de l'Urbanisme (CATU — 2011)

RÈGLES :
- Réponds TOUJOURS en français
- Cite le bon article et le bon code pour chaque information
- Ne confonds PAS avec le droit français
- Sois concis : 3-5 phrases maximum
- Termine par une recommandation pratique"""


def _detect_sources(rag_context: str) -> str:
    """Détecte quelle(s) source(s) sont dans le contexte RAG."""
    has_catu = "Amenagement" in rag_context or "URBANISME" in rag_context or "CATU" in rag_context
    has_cdr  = "Droits Reels" in rag_context or "CDR" in rag_context or "65-5" in rag_context
    if has_catu and has_cdr:
        return "MIXTE"
    if has_catu:
        return "URBANISME"
    return "CDR"


def _build_prompt(question: str, rules_context: str, rag_context: str = "") -> str:
    """Construit le prompt avec le bon système selon la source détectée."""

    # Choisir le prompt système selon la source
    if rag_context:
        source = _detect_sources(rag_context)
    else:
        source = "CDR"

    system_prompts = {
        "CDR":      _PROMPT_CDR,
        "URBANISME": _PROMPT_URBANISME,
        "MIXTE":    _PROMPT_MIXTE,
    }
    system = system_prompts.get(source, _PROMPT_CDR)

    # Construire le contexte
    context_parts = []
    if rules_context:
        context_parts.append(rules_context)
    if rag_context:
        context_parts.append(f"Extraits des textes juridiques officiels :\n{rag_context}")

    context = "\n\n".join(context_parts) if context_parts else "Aucun contexte spécifique disponible."

    return f"""{system}

CONTEXTE JURIDIQUE DISPONIBLE :
{context}

QUESTION DE L'UTILISATEUR :
{question}

RÉPONSE (en français, concise, basée sur le droit tunisien) :"""


# ══════════════════════════════════════════════════════════════════
# APPEL MISTRAL
# ══════════════════════════════════════════════════════════════════

def _call_mistral(prompt: str, timeout: int = 60) -> str:
    """Appelle Mistral via Ollama et retourne la réponse texte."""
    payload = {
        "model":  LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 300,
            "top_p":       0.9,
        },
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        log.warning(f"Mistral indisponible : {e}")
        return None
    except Exception as e:
        log.warning(f"Erreur Mistral : {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ══════════════════════════════════════════════════════════════════

def chat(question: str, rag_context: str = "") -> dict:
    """
    Répond à une question juridique en français naturel.

    Args:
        question    : question de l'utilisateur en français libre
        rag_context : contexte RAG optionnel (extraits du PDF CDR ou Urbanisme)

    Returns:
        {
            "answer":        str,
            "rules_used":    list,
            "source":        str,   # "CDR" / "URBANISME" / "MIXTE"
            "confidence":    str,
        }
    """
    question = question.strip()
    if not question:
        return {"error": "Question vide"}

    log.info(f"Question : '{question[:80]}'")

    # 1. Charger les règles CDR et trouver les pertinentes
    rules    = _load_rules()
    relevant = _find_relevant_rules(question, rules, top_k=5)
    rules_context = _format_rules_context(relevant)

    # 2. Détecter la source pour le prompt
    source = _detect_sources(rag_context) if rag_context else "CDR"

    # 3. Construire le prompt avec le bon système
    prompt = _build_prompt(question, rules_context, rag_context)

    # 4. Appeler Mistral
    answer = _call_mistral(prompt)

    if answer:
        log.info(f"Réponse {source} générée ({len(answer)} chars)")
        return {
            "answer":     answer,
            "rules_used": [
                {
                    "article": r.get("article", "?"),
                    "actor":   r.get("actor",   "?"),
                    "action":  r.get("action",  "?"),
                    "status":  r.get("status",  "?"),
                    "risk":    r.get("risk_score", 0),
                }
                for r in relevant
            ],
            "source":     source,
            "confidence": "high" if relevant or rag_context else "low",
        }

    # 5. Fallback si Mistral indisponible
    log.warning("Mistral indisponible — fallback règles")
    if relevant:
        r = relevant[0]
        fallback = (
            f"Selon l'article {r.get('article','?')} du Code des Droits Réels tunisien, "
            f"'{r.get('action','?')}' est {r.get('status','?')} "
            f"pour '{r.get('actor','?')}'. "
            f"Risque : {r.get('risk_score', 0)}/100. "
            f"Consultez un notaire spécialisé."
        )
    elif rag_context:
        fallback = (
            "D'après les textes juridiques tunisiens disponibles, "
            "cette situation nécessite une vérification auprès "
            "d'un notaire ou d'un juriste spécialisé."
        )
    else:
        fallback = (
            "Je n'ai pas trouvé de règle spécifique dans le droit "
            "immobilier tunisien pour votre question. "
            "Consultez un notaire ou juriste spécialisé."
        )

    return {
        "answer":     fallback,
        "rules_used": [
            {"article": r.get("article","?"), "actor": r.get("actor","?"),
             "action": r.get("action","?"), "status": r.get("status","?"),
             "risk": r.get("risk_score",0)} for r in relevant
        ],
        "source":     source,
        "confidence": "low",
    }


# ══════════════════════════════════════════════════════════════════
# TEST EN LIGNE DE COMMANDE
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    questions = sys.argv[1:] or [
        "Est-ce que je peux sous-louer mon appartement ?",
        "Puis-je construire sans permis de construire ?",
        "Quels sont mes droits en tant qu'usufruitier ?",
        "Comment fonctionne le gage en droit tunisien ?",
        "Qu'est-ce qu'une zone non constructible ?",
    ]

    print("\n" + "═"*60)
    print("CHATBOT JURIDIQUE TuniState — CDR + Urbanisme Tunisien")
    print("═"*60 + "\n")

    for q in questions:
        print(f"❓ {q}")
        # Simuler RAG Urbanisme pour les questions construction
        rag_ctx = ""
        if "construire" in q.lower() or "permis" in q.lower() or "zone" in q.lower():
            try:
                from rag import search, format_context
                results = search(q, sources=["URBANISME"], top_k=2)
                rag_ctx = format_context(results)
            except Exception:
                pass

        result = chat(q, rag_context=rag_ctx)
        print(f"🤖 [{result['source']}] {result['answer']}")
        print(f"   → Confiance : {result['confidence']}")
        print()