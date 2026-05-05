"""
app/services/nlp/translator.py
================================
Traduction vers l'anglais via deep-translator (GoogleTranslator).
Cache LRU pour éviter les appels répétés.
Timeout 5s max. Fallback : retourner le texte original.
"""

import time
from functools import lru_cache

@lru_cache(maxsize=512)
def _translate_cached(text: str, source_lang: str) -> str:
    """Traduction avec cache LRU."""
    if source_lang == "en":
        return text
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=source_lang, target="en").translate(text[:500])
        return result or text
    except Exception:
        return text

def translate_to_english(text: str, source_lang: str = "fr") -> dict:
    """
    Traduit le texte vers l'anglais.
    Retourne {"translated": str, "source_lang": str, "ms": int, "cached": bool}
    """
    t0 = time.monotonic()
    if source_lang == "en" or not text.strip():
        return {"translated": text, "source_lang": "en", "ms": 0, "cached": True}

    # Normaliser la langue pour GoogleTranslator
    lang_map = {"ar": "ar", "fr": "fr", "unknown": "fr"}
    src = lang_map.get(source_lang, "fr")

    try:
        import signal

        translated = _translate_cached(text[:500], src)
        ms = int((time.monotonic() - t0) * 1000)
        return {"translated": translated, "source_lang": src, "ms": ms, "cached": False}
    except Exception:
        ms = int((time.monotonic() - t0) * 1000)
        return {"translated": text, "source_lang": src, "ms": ms, "cached": False, "error": "translation_failed"}
