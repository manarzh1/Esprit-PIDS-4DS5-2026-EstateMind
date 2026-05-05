"""
app/services/nlp/language_detector.py
=======================================
Détection de langue via langdetect (Naïve Bayes sur N-grammes de caractères).
Langues : fr, en, ar, darija (détecté comme ar).
"""

import time
from functools import lru_cache

ARABIC_CHARS = set("ءآأؤإئابتثجحخدذرزسشصضطظعغفقكلمنهوىيةً")

def _has_arabic(text: str) -> bool:
    return any(c in ARABIC_CHARS for c in text)

def detect_language(text: str) -> dict:
    """
    Détecte la langue d'un texte.
    Retourne {"language": str, "confidence": float, "ms": int}
    """
    t0 = time.monotonic()
    lang = "unknown"
    confidence = 0.5

    if _has_arabic(text):
        lang = "ar"
        confidence = 0.92
    else:
        try:
            from langdetect import detect_langs
            results = detect_langs(text)
            if results:
                top = results[0]
                detected = top.lang
                confidence = float(top.prob)
                if detected in ("fr", "en", "ar"):
                    lang = detected
                else:
                    lang = "fr"
                    confidence = 0.5
        except Exception:
            # Heuristiques simples si langdetect échoue
            text_lower = text.lower()
            fr_words = {"le", "la", "les", "un", "une", "des", "est", "sont", "quel", "prix", "combien"}
            en_words = {"the", "is", "are", "what", "how", "much", "price", "cost", "apartment"}
            fr_score = sum(1 for w in text_lower.split() if w in fr_words)
            en_score = sum(1 for w in text_lower.split() if w in en_words)
            if fr_score > en_score:
                lang, confidence = "fr", 0.7
            elif en_score > fr_score:
                lang, confidence = "en", 0.7
            else:
                lang, confidence = "fr", 0.5

    ms = int((time.monotonic() - t0) * 1000)
    return {"language": lang, "confidence": round(confidence, 3), "ms": ms}
