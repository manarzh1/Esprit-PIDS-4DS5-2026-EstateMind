"""
nlp_parser.py
─────────────────────────────────────────────────────────────────
Parser NLP robuste pour TuniState — utilise Mistral (Ollama)
pour transformer une phrase en langage naturel en structure
juridique {actor, action, target, conditions}.

Exemples :
  "je veux démolir ma maison sans autorisation"
    → actor=proprietaire, action=démolir, target=batiment,
      conditions=["sans autorisation"]

  "mon locataire veut sous-louer mon appartement sans accord"
    → actor=locataire, action=sous-louer, target=appartement,
      conditions=["sans accord"]

FALLBACK : si Mistral échoue ou est indisponible, utilise
un parser par règles lexicales pour ne jamais bloquer.
"""

import json, re, logging
import urllib.request
import urllib.error
from typing import Optional

from config import OLLAMA_URL, LLM_MODEL, LOG_DIR

log = logging.getLogger("nlp_parser")
log.setLevel(logging.INFO)
if not log.handlers:
    _fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "nlp_parser.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)


# ══════════════════════════════════════════════════════════════════════════════
# DICTIONNAIRES DE NORMALISATION (utilisés par le fallback et pour enrichir)
# ══════════════════════════════════════════════════════════════════════════════

# Acteurs : formes possibles → acteur standard
ACTOR_SYNONYMS = {
    # Propriétaire
    "propriétaire": "proprietaire", "proprietaire": "proprietaire",
    "mon propriétaire": "proprietaire", "le propriétaire": "proprietaire",
    "je": "proprietaire", "nous": "proprietaire",
    "moi": "proprietaire", "j'ai": "proprietaire",
    # Locataire
    "locataire": "locataire", "mon locataire": "locataire",
    "le locataire": "locataire", "notre locataire": "locataire",
    # Preneur
    "preneur": "preneur", "le preneur": "preneur",
    # Créancier / banque
    "créancier": "créancier", "creancier": "créancier",
    "banque": "créancier", "la banque": "créancier",
    "établissement de crédit": "créancier", "etablissement de credit": "créancier",
    "prêteur": "créancier", "preteur": "créancier",
    # Débiteur / emprunteur
    "débiteur": "débiteur", "debiteur": "débiteur",
    "emprunteur": "débiteur", "l'emprunteur": "débiteur",
    # Acquéreur / acheteur
    "acquéreur": "acquéreur", "acquereur": "acquéreur",
    "acheteur": "acquéreur", "l'acheteur": "acquéreur",
    "nouveau propriétaire": "acquéreur",
    # Vendeur
    "vendeur": "vendeur", "le vendeur": "vendeur",
    # Héritier
    "héritier": "héritier", "heritier": "héritier",
    "les héritiers": "héritier", "mes héritiers": "héritier",
    # Copropriétaire
    "copropriétaire": "copropriétaire", "coproprietaire": "copropriétaire",
    "coindivisaire": "coindivisaire",
    # État
    "état": "etat", "etat": "etat", "l'état": "etat",
    "l'état tunisien": "etat", "la commune": "autorite_locale",
    "municipalité": "autorite_locale", "municipalite": "autorite_locale",
    "administration": "etat",
    # Autres
    "notaire": "notaire", "le notaire": "notaire",
    "tribunal": "tribunal", "le tribunal": "tribunal",
    "usufruitier": "usufruitier", "l'usufruitier": "usufruitier",
    "possesseur": "possesseur", "le possesseur": "possesseur",
    "bailleur": "bailleur", "le bailleur": "bailleur",
}

# Actions : synonymes → verbe canonique
ACTION_SYNONYMS = {
    # Construction
    "construire": "construire", "bâtir": "construire", "batir": "construire",
    "édifier": "construire", "edifier": "construire", "ériger": "construire",
    "faire construire": "construire", "construction": "construire",
    # Démolition
    "démolir": "démolir", "demolir": "démolir",
    "détruire": "démolir", "detruire": "démolir",
    "raser": "démolir", "abattre": "démolir",
    "démolition": "démolir", "demolition": "démolir",
    # Vente
    "vendre": "vendre", "vente": "vendre",
    "céder": "vendre", "ceder": "vendre",
    "aliéner": "vendre", "aliener": "vendre",
    "revendre": "vendre",
    # Achat
    "acheter": "acheter", "achat": "acheter",
    "acquérir": "acheter", "acquerir": "acheter",
    # Location / bail
    "louer": "louer", "location": "louer",
    "mettre en location": "louer", "donner à bail": "louer",
    # Sous-location
    "sous-louer": "sous-louer", "sous louer": "sous-louer",
    "sublouer": "sous-louer", "sous-location": "sous-louer",
    "relouer": "sous-louer",
    # Hypothèque
    "hypothéquer": "hypothéquer", "hypothequer": "hypothéquer",
    "mettre en hypothèque": "hypothéquer", "grever d'hypothèque": "hypothéquer",
    "inscrire une hypothèque": "inscrire", "inscrire hypothèque": "inscrire",
    # Inscription / registre
    "inscrire": "inscrire", "inscription": "inscrire",
    "enregistrer": "inscrire", "immatriculer": "immatriculer",
    # Saisie / expropriation
    "saisir": "saisir", "saisie": "saisir",
    "exproprier": "exproprier", "expropriation": "exproprier",
    # Résiliation
    "résilier": "résilier", "resilier": "résilier",
    "rompre": "résilier", "annuler": "résilier",
    # Héritage
    "hériter": "hériter", "heriter": "hériter",
    "succéder": "hériter", "succession": "hériter",
    "partager": "partager", "partage": "partager",
    # Divers
    "revendiquer": "revendiquer", "restituer": "restituer",
}

# Cibles : synonymes → cible standard
TARGET_SYNONYMS = {
    "maison": "batiment", "villa": "batiment", "immeuble": "batiment",
    "bâtiment": "batiment", "batiment": "batiment",
    "appartement": "appartement", "logement": "appartement",
    "studio": "appartement", "local": "appartement",
    "terrain": "terrain", "parcelle": "terrain", "lot": "terrain",
    "propriété": "bien immobilier", "propriete": "bien immobilier",
    "bien": "bien immobilier", "bien immobilier": "bien immobilier",
    "biens immobiliers": "bien immobilier",
    "hypothèque": "hypotheque", "hypotheque": "hypotheque",
    "titre foncier": "titre foncier", "acte de propriété": "titre foncier",
    "gage": "gage", "servitude": "servitude",
    "succession": "succession", "héritage": "succession",
    "bail": "bail", "contrat de bail": "bail", "location": "bail",
}

# Conditions : signaux textuels → condition canonique
CONDITION_PATTERNS = [
    # Sans autorisation
    (r"sans\s+(permis|autorisation|autoris)",    "sans autorisation"),
    (r"ill[ée]gal",                                "sans autorisation"),
    (r"clandestinement",                           "sans autorisation"),
    (r"non\s+autoris[ée]",                         "sans autorisation"),
    # Avec autorisation
    (r"avec\s+(permis|autorisation)",              "avec autorisation"),
    (r"permis\s+de\s+construire",                  "avec autorisation"),
    (r"l[ée]galement",                             "avec autorisation"),
    (r"autoris[ée]\s+par",                         "avec autorisation"),
    # Notaire
    (r"\bnotaire\b",                               "devant un notaire"),
    (r"acte\s+authentique",                        "devant un notaire"),
    (r"devant\s+(un\s+)?notaire",                  "devant un notaire"),
    # Accord
    (r"sans\s+(accord|consentement|permission)",   "sans accord"),
    (r"avec\s+(accord|consentement|permission)",   "avec accord"),
    (r"accord\s+du\s+bailleur",                    "avec accord"),
    (r"accord\s+du\s+propri[ée]taire",             "avec accord"),
    # Voie judiciaire
    (r"(voie|d[ée]cision)\s+judiciaire",           "par voie judiciaire"),
    (r"tribunal",                                  "par voie judiciaire"),
]


# ══════════════════════════════════════════════════════════════════════════════
# PARSER MISTRAL (voie principale)
# ══════════════════════════════════════════════════════════════════════════════

_MISTRAL_PROMPT = """Tu es un expert en droit immobilier tunisien (Code des Droits Réels - Loi 65-5).

Ta tâche : analyser la phrase suivante et extraire les informations juridiques au format JSON strict.

PHRASE À ANALYSER :
"{text}"

RÉPONDS UNIQUEMENT EN JSON VALIDE, sans texte avant ou après, dans ce format exact :
{{
  "actor": "<un seul de : proprietaire, locataire, preneur, créancier, débiteur, acquéreur, vendeur, héritier, copropriétaire, usufruitier, possesseur, bailleur, etat, notaire, tribunal>",
  "action": "<verbe infinitif court : construire, démolir, vendre, acheter, louer, sous-louer, hypothéquer, inscrire, saisir, exproprier, résilier, revendiquer, hériter, partager>",
  "target": "<objet de l'action : batiment, immeuble, appartement, terrain, bien immobilier, hypotheque, titre foncier, gage, servitude, succession, bail>",
  "conditions": ["<condition 1>", "<condition 2>"],
  "interpretation": "<brève explication en une phrase de ta compréhension>"
}}

RÈGLES CRITIQUES :
- "je veux" / "je souhaite" / "je" / "mon" / "ma" → actor = proprietaire
- "mon locataire" → actor = locataire (pas proprietaire)
- "la banque" / "prêteur" → actor = créancier
- "l'acheteur" / "nouveau propriétaire" → actor = acquéreur
- "sans permis/autorisation" → conditions = ["sans autorisation"]
- "avec permis/autorisation" / "légalement" → conditions = ["avec autorisation"]
- "devant notaire" / "acte authentique" → conditions = ["devant un notaire"]
- "sans accord du bailleur" → conditions = ["sans accord"]
- "démolir" / "détruire" / "raser" / "abattre" → action = démolir
- "bâtir" / "édifier" / "construire" → action = construire
- "vendre" / "céder" / "aliéner" → action = vendre

Si la phrase ne concerne PAS le droit immobilier tunisien, retourne :
{{"actor": "", "action": "", "target": "", "conditions": [], "interpretation": "Hors domaine CDR"}}

JSON :"""


def _call_mistral(text: str, timeout: int = 30) -> Optional[dict]:
    """Appelle Mistral via Ollama. Retourne None si échec."""
    prompt = _MISTRAL_PROMPT.format(text=text.strip())
    payload = {
        "model":  LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # très déterministe pour parsing
            "top_p":       0.9,
            "num_predict": 200,
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
            raw = data.get("response", "").strip()
            return _extract_json(raw)
    except (urllib.error.URLError, TimeoutError, Exception) as e:
        log.warning(f"Mistral indisponible : {e} — fallback lexical")
        return None


def _extract_json(raw: str) -> Optional[dict]:
    """Extrait un bloc JSON de la réponse LLM, ignore le bruit autour."""
    if not raw:
        return None
    # Chercher le premier { jusqu'au } correspondant
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i, c in enumerate(raw[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


# ══════════════════════════════════════════════════════════════════════════════
# PARSER FALLBACK (lexical, si Mistral indisponible)
# ══════════════════════════════════════════════════════════════════════════════

_IGNORE_WORDS = {
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "veux", "voudrais", "souhaite", "désire", "aimerais", "peux", "peut",
    "va", "vais", "aller", "être", "avoir", "faire",
    "un", "une", "des", "le", "la", "les", "du", "de", "en",
    "et", "ou", "mais", "donc", "car", "si", "que", "qui", "quoi",
    "sur", "dans", "par", "pour", "avec", "sans", "à", "au", "aux",
    "mon", "ma", "mes", "son", "sa", "ses", "notre", "nos", "leur", "leurs",
    "ce", "cet", "cette", "ces", "y",
    "est", "sont", "était", "serait", "soit",
}


def _fallback_parse(text: str) -> dict:
    """Parser lexical de secours si Mistral est indisponible."""
    t = text.lower().strip()

    actor, action, target = "", "", ""
    conditions = []

    # 1. Détecter conditions
    for pattern, value in CONDITION_PATTERNS:
        if re.search(pattern, t) and value not in conditions:
            conditions.append(value)

    # 2. Détecter acteur — PRIORITÉ aux patterns "mon X" / "le X"
    # Si on trouve "mon locataire" on prend locataire, PAS proprietaire
    PRIORITY_PATTERNS = [
        (r"\bmon\s+locataire\b",    "locataire"),
        (r"\bmes\s+locataires\b",   "locataire"),
        (r"\ble\s+locataire\b",     "locataire"),
        (r"\bmon\s+cr[ée]ancier\b", "créancier"),
        (r"\bla\s+banque\b",         "créancier"),
        (r"\bmon\s+d[ée]biteur\b",  "débiteur"),
        (r"acheteur",                   "acquéreur"),
        (r"acqu[ée]reur",               "acquéreur"),
        (r"\bmes\s+h[ée]ritiers?\b", "héritier"),
        (r"h[ée]ritier",                "héritier"),
        (r"\b[ée]tat\b",              "etat"),
        (r"\bla\s+commune\b",        "autorite_locale"),
        (r"\bla\s+municipalit[ée]\b","autorite_locale"),
        (r"\ble\s+notaire\b",        "notaire"),
        (r"\ble\s+tribunal\b",       "tribunal"),
        (r"usufruitier",                "usufruitier"),
        (r"\ble\s+possesseur\b",     "possesseur"),
        (r"\ble\s+bailleur\b",       "bailleur"),
        (r"\ble\s+preneur\b",        "preneur"),
        (r"\ble\s+vendeur\b",        "vendeur"),
    ]
    for pattern, val in PRIORITY_PATTERNS:
        if re.search(pattern, t):
            actor = val
            break

    # Si pas trouvé via patterns prioritaires, fallback sur dictionnaire
    if not actor:
        for key in sorted(ACTOR_SYNONYMS.keys(), key=len, reverse=True):
            if key in t:
                actor = ACTOR_SYNONYMS[key]
                break

    # 3. Détecter action
    for key in sorted(ACTION_SYNONYMS.keys(), key=len, reverse=True):
        if key in t:
            action = ACTION_SYNONYMS[key]
            break

    # 4. Détecter cible
    for key in sorted(TARGET_SYNONYMS.keys(), key=len, reverse=True):
        if key in t:
            target = TARGET_SYNONYMS[key]
            break

    # 5. Fallback mot par mot si rien trouvé
    if not actor or not action:
        words = [w for w in re.findall(r"\w+", t) if w not in _IGNORE_WORDS and len(w) > 2]
        if not actor and words:
            actor = words[0]
        if not action and len(words) > 1:
            action = words[1]
        if not target and len(words) > 2:
            target = words[2]

    return {
        "actor":          actor,
        "action":         action,
        "target":         target,
        "conditions":     conditions,
        "interpretation": f"Parse lexical : {actor} → {action}" + (f" ({target})" if target else ""),
        "_fallback":      True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

def parse_natural(text: str, use_llm: bool = True) -> dict:
    """
    Parse une phrase en langage naturel vers structure juridique.

    Args:
        text: phrase libre de l'utilisateur
        use_llm: si True, utilise Mistral; sinon uniquement fallback

    Returns:
        {actor, action, target, conditions, interpretation, _source}
    """
    text = text.strip()
    if not text:
        return {"error": "Texte vide"}

    # 1. Essayer Mistral
    if use_llm:
        result = _call_mistral(text)
        if result is not None:
            # Valider et normaliser le résultat de Mistral
            normalized = _normalize_result(result, text)
            normalized["_source"] = "mistral"
            log.info(f"Mistral : '{text[:60]}' → {normalized.get('actor')}/{normalized.get('action')}")
            return normalized

    # 2. Fallback lexical
    result = _fallback_parse(text)
    result["_source"] = "fallback_lexical"
    log.info(f"Fallback : '{text[:60]}' → {result.get('actor')}/{result.get('action')}")
    return result


def _normalize_result(result: dict, original_text: str) -> dict:
    """Nettoie et normalise le résultat Mistral. Corrige les erreurs d'acteur."""
    actor  = str(result.get("actor",  "")).strip().lower()
    action = str(result.get("action", "")).strip().lower()
    target = str(result.get("target", "")).strip().lower()
    conds  = result.get("conditions", [])

    # NORMALISATION via dictionnaires de synonymes
    # Mistral peut retourner "maison" mais les règles utilisent "bâtiment"
    # On mappe à la forme canonique pour améliorer le matching
    if target:
        target_canonical = TARGET_SYNONYMS.get(target, target)
        if target_canonical != target:
            log.info(f"Normalisation target : '{target}' -> '{target_canonical}'")
            target = target_canonical

    if action:
        action_canonical = ACTION_SYNONYMS.get(action, action)
        if action_canonical != action:
            log.info(f"Normalisation action : '{action}' -> '{action_canonical}'")
            action = action_canonical

    # VALIDATION : Si la phrase contient "mon locataire" / "la banque" etc.
    # mais que Mistral a retourné "proprietaire", on corrige
    text_low = original_text.lower()
    actor_corrections = [
        (["mon locataire", "mes locataires", "le locataire", "les locataires"], "locataire"),
        (["mon créancier", "mon creancier", "la banque"],                       "créancier"),
        (["acheteur", "acquéreur", "acquereur"],                                "acquéreur"),
        (["mes héritiers", "mes heritiers", "héritier", "heritier"],            "héritier"),
        (["la commune", "la municipalité", "la municipalite"],                  "autorite_locale"),
        (["le notaire"],                                                        "notaire"),
        (["le tribunal"],                                                       "tribunal"),
        (["usufruitier"],                                                       "usufruitier"),
        (["le possesseur"],                                                     "possesseur"),
        (["le bailleur"],                                                       "bailleur"),
        (["le preneur"],                                                        "preneur"),
    ]
    for signals, correct_actor in actor_corrections:
        if any(s in text_low for s in signals):
            if actor != correct_actor:
                log.info(f"Correction acteur : '{actor}' -> '{correct_actor}' (signal '{signals[0]}')")
                actor = correct_actor
            break

    # Normaliser l'actor via dictionnaire si pas déjà canonique
    if actor and actor not in {v for v in ACTOR_SYNONYMS.values()}:
        for key in sorted(ACTOR_SYNONYMS.keys(), key=len, reverse=True):
            if key in actor:
                actor = ACTOR_SYNONYMS[key]
                break

    # Nettoyer les conditions (strings uniquement)
    if not isinstance(conds, list):
        conds = []
    conds = [str(c).strip() for c in conds if c and isinstance(c, (str, int, float))]

    # Si Mistral a retourné vide → fallback pour récupérer
    if not actor or not action:
        fb = _fallback_parse(original_text)
        if not actor:  actor  = fb.get("actor", "")
        if not action: action = fb.get("action", "")
        if not target: target = fb.get("target", "")
        if not conds:  conds  = fb.get("conditions", [])

    return {
        "actor":          actor,
        "action":         action,
        "target":         target,
        "conditions":     conds,
        "interpretation": result.get("interpretation", ""),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST EN LIGNE DE COMMANDE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    test_cases = sys.argv[1:] or [
        "je veux construire une villa sans permis",
        "mon locataire veut sous-louer mon appartement sans accord",
        "je souhaite vendre ma propriété chez le notaire",
        "la banque veut inscrire une hypothèque sur mon terrain",
        "je veux démolir ma maison",
        "je veux acheter un appartement à tunis",
        "mes héritiers veulent vendre la succession",
        "l'état veut exproprier mon terrain",
    ]

    print("\n" + "═"*70)
    print("TEST DU PARSER NLP TuniState")
    print("═"*70 + "\n")

    for tc in test_cases:
        print(f"📝 '{tc}'")
        r = parse_natural(tc)
        print(f"   actor      : {r.get('actor')}")
        print(f"   action     : {r.get('action')}")
        print(f"   target     : {r.get('target')}")
        print(f"   conditions : {r.get('conditions')}")
        print(f"   source     : {r.get('_source')}")
        print(f"   → {r.get('interpretation', '')}")
        print()