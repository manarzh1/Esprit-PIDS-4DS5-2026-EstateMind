"""
app/services/nlp/intent_detector.py
======================================
Détection d'intention via Naïve Bayes + N-grammes.
Combine le texte original, normalisé, et traduit pour améliorer la précision.
"""

import time
from app.services.nlp.naive_bayes import get_classifier, INTENT_LABELS

def detect_intent(text_original: str, text_normalized: str = "", text_translated: str = "") -> dict:
    """
    Détecte l'intention d'une requête.

    Stratégie :
      1. Classifier le texte traduit (anglais) — priorité
      2. Fallback sur texte original si confiance faible
      3. Combiner les scores

    Retourne :
      {
        "intent": str,
        "confidence": float,
        "probabilities": dict,
        "top_ngrams": list[str],
        "ms": int
      }
    """
    t0 = time.monotonic()
    clf = get_classifier()

    # Classifier chaque version du texte
    texts_to_try = []
    if text_translated and text_translated.strip():
        texts_to_try.append(text_translated)
    if text_normalized and text_normalized.strip() and text_normalized != text_original:
        texts_to_try.append(text_normalized)
    texts_to_try.append(text_original)

    # Moyenner les probabilités
    combined_proba: dict[str, float] = {intent: 0.0 for intent in INTENT_LABELS}
    count = 0
    for text in texts_to_try:
        if text.strip():
            proba = clf.predict_proba(text)
            for intent in INTENT_LABELS:
                combined_proba[intent] += proba.get(intent, 0.0)
            count += 1

    if count > 0:
        for intent in INTENT_LABELS:
            combined_proba[intent] /= count

    # Normaliser
    total = sum(combined_proba.values()) or 1.0
    probabilities = {k: round(v / total, 4) for k, v in combined_proba.items()}

    # Meilleure intention
    best_intent = max(probabilities, key=probabilities.get)
    confidence = probabilities[best_intent]

    # Top N-grammes (depuis texte traduit ou original)
    main_text = text_translated or text_original
    top_ngrams = clf.get_top_features(main_text, top_n=5) if main_text.strip() else []

    ms = int((time.monotonic() - t0) * 1000)
    return {
        "intent": best_intent,
        "confidence": round(confidence, 4),
        "probabilities": probabilities,
        "top_ngrams": top_ngrams,
        "ms": ms,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  extract_params — extrait ville, budget, surface depuis le texte
# ─────────────────────────────────────────────────────────────────────────────

import re as _re

_CITY_PATTERNS = [
    "tunis", "ariana", "la marsa", "la soukra", "hammamet", "nabeul",
    "sousse", "sfax", "bizerte", "monastir", "ben arous", "la manouba",
    "gammarth", "sidi bou said", "le bardo", "raoued", "el menzah",
    "hammam sousse", "sahloul", "akouda", "le kram", "carthage",
    "el mourouj", "el aouina", "ezzahra", "megrine", "mnihla",
]

_CITY_MAP = {
    "tunis": "Tunis", "ariana": "Ariana", "la marsa": "La Marsa",
    "la soukra": "La Soukra", "hammamet": "Hammamet", "nabeul": "Nabeul",
    "sousse": "Sousse", "sfax": "Sfax", "bizerte": "Bizerte",
    "monastir": "Monastir", "ben arous": "Ben Arous",
    "la manouba": "La Manouba", "gammarth": "Gammarth",
    "sidi bou said": "Sidi Bou Said", "le bardo": "Le Bardo",
    "raoued": "Raoued", "el menzah": "El Menzah",
    "hammam sousse": "Hammam Sousse", "sahloul": "Sahloul",
    "akouda": "Akouda", "le kram": "Le Kram", "carthage": "Carthage",
    "el mourouj": "El Mourouj", "el aouina": "El Aouina",
    "ezzahra": "Ezzahra", "megrine": "Megrine", "mnihla": "Mnihla",
}

_BEDROOM_MAP = {
    "studio": 1, "s+0": 1, "s0": 1,
    "s+1": 2, "s1": 2, "f2": 2,
    "s+2": 3, "s2": 3, "f3": 3,
    "s+3": 4, "s3": 4, "f4": 4,
    "s+4": 5, "s4": 5, "f5": 5,
}


def extract_params(
    text_original: str,
    text_normalized: str,
    text_translated: str,
    intent: str,
) -> dict:
    """
    Extrait les paramètres structurés (ville, surface, budget, chambres)
    depuis les différentes représentations du texte utilisateur.
    """
    all_text = f"{text_original} {text_normalized} {text_translated}".lower()
    params: dict = {"query": text_original}

    # ── Ville ─────────────────────────────────────────────────
    city_found = None
    for pattern in sorted(_CITY_PATTERNS, key=len, reverse=True):
        if pattern in all_text:
            city_found = _CITY_MAP.get(pattern, pattern.title())
            break
    if city_found:
        params["city"]  = city_found
        params["ville"] = city_found

    # ── Type de bien (S+N) ─────────────────────────────────────
    for code, bedrooms in _BEDROOM_MAP.items():
        if code in all_text:
            params["bedrooms"] = bedrooms
            # Estimer surface par défaut selon type
            params.setdefault("surface", 40 + bedrooms * 25)
            break

    # ── Surface (m²) ──────────────────────────────────────────
    m = _re.search(r"(\d{2,4})\s*m[²2]", all_text)
    if m:
        params["surface"] = int(m.group(1))

    # ── Budget ────────────────────────────────────────────────
    # Ex: "300 000 tnd", "350k", "500 mille"
    m = _re.search(r"(\d[\d\s]*)\s*(tnd|dt|dinar|mille|k\b)", all_text)
    if m:
        raw_val = m.group(1).replace(" ", "")
        mult = m.group(2).lower()
        val = int(raw_val)
        if mult in ("k",):
            val *= 1000
        elif mult in ("mille",) and val < 10000:
            val *= 1000
        if val > 5000:  # éviter de confondre avec surface
            params["budget"] = float(val)

    # ── Valeurs par défaut selon intent ───────────────────────
    if intent == "price_estimation":
        params.setdefault("surface", 100)
        params.setdefault("bedrooms", 2)
        params.setdefault("bathrooms", 1)
        params.setdefault("budget", 0)
    elif intent == "investment_analysis":
        params.setdefault("budget", 300_000)
    elif intent in ("location_analysis", "report_generation", "general_query"):
        params.setdefault("budget", 300_000)
        params.setdefault("type_bien", "appartement")

    return params
