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
