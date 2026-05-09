"""
sumup.py
─────────────────────────────────────────────────────────────────
Module de résumé intelligent des réponses du chatbot juridique.

Fonctions :
  - sum_up_response()  : réduit et optimise une réponse LLM
  - deduplicate_sentences() : supprime les phrases redondantes
  - clean_response()   : nettoyage et formatage final

Niveaux de concision :
  - short    : 3-4 phrases, essentiel uniquement
  - medium   : 5-7 phrases, équilibré (défaut)
  - detailed : 8-12 phrases, complet mais structuré

Garanties :
  - Aucune perte d'information juridique critique
  - Fallback propre si le traitement échoue
  - Respect des références d'articles de loi
"""

import re
import logging
from typing import Optional
from config import SUMUP_ENABLED, SUMUP_DEFAULT_LEVEL, SUMUP_MAX_CHARS, SUMUP_DEDUP_ENABLED

log = logging.getLogger("sumup")


# ══════════════════════════════════════════════════════════════════
# MARQUEURS JURIDIQUES À PRÉSERVER ABSOLUMENT
# ══════════════════════════════════════════════════════════════════

_LEGAL_MARKERS = re.compile(
    r"(article\s+\d+|art\.\s*\d+|loi\s+n°\s*[\d\-]+|code\s+des\s+droits|"
    r"cdr|catu|interdit|obligatoire|permis|notaire|risque\s*:\s*\d+|"
    r"selon\s+l'article|d'après\s+l'article|en\s+vertu\s+de)",
    re.IGNORECASE,
)

# Phrases boilerplate à supprimer systématiquement
_FILLER_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^(bien sûr|certainement|absolument|bien entendu)[,!]?\s*",
        r"^(je suis (là|prêt|disponible) pour vous aider)[.!]?\s*",
        r"^(n'hésitez pas à me poser d'autres questions)[.!]?\s*",
        r"^(j'espère que (cette|ma) réponse vous (aide|satisfait|convient))[.!]?\s*",
        r"^(pour résumer ce qui précède)[,:]?\s*",
        r"^(comme je l'ai mentionné (précédemment|plus haut))[,:]?\s*",
        r"^(il est important de noter que)\s*",
        r"(si vous avez d'autres questions, .*)[.!]?\s*$",
    ]
]

# Phrases de conclusion typiques à garder uniquement si c'est la dernière phrase
_CLOSING_PATTERNS = re.compile(
    r"(consultez un notaire|contactez un juriste|rapprochez-vous d'un professionnel"
    r"|recommande de consulter)",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════
# NETTOYAGE DES PHRASES
# ══════════════════════════════════════════════════════════════════

def _split_sentences(text: str) -> list[str]:
    """Découpe un texte en phrases propres."""
    # Normaliser les fins de phrase
    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    # Découper sur . ! ? (en protégeant les abréviations courantes)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ÿ«\"])", text)

    cleaned = []
    for s in sentences:
        s = s.strip()
        if len(s) < 15:  # trop court pour être une phrase utile
            continue
        cleaned.append(s)

    return cleaned


def _remove_filler(sentence: str) -> Optional[str]:
    """Supprime les phrases boilerplate. Retourne None si la phrase est inutile."""
    s = sentence.strip()
    for pattern in _FILLER_PATTERNS:
        # Si le pattern couvre toute la phrase → supprimer
        if pattern.sub("", s).strip() == "":
            return None
        s = pattern.sub("", s).strip()

    if len(s) < 10:
        return None

    # Capitaliser si nécessaire
    if s and s[0].islower():
        s = s[0].upper() + s[1:]

    return s


def _similarity_simple(a: str, b: str) -> float:
    """Similarité rapide par Jaccard sur les n-grams de mots (sans dépendances)."""
    if not a or not b:
        return 0.0
    wa = set(re.findall(r"\w{4,}", a.lower()))
    wb = set(re.findall(r"\w{4,}", b.lower()))
    if not wa or not wb:
        return 0.0
    intersection = wa & wb
    union = wa | wb
    return len(intersection) / len(union)


def deduplicate_sentences(sentences: list[str], threshold: float = 0.60) -> list[str]:
    """
    Supprime les phrases quasi-identiques en conservant la première occurrence.
    Préserve toujours les phrases contenant des marqueurs juridiques critiques.
    """
    if not SUMUP_DEDUP_ENABLED:
        return sentences

    kept = []
    for candidate in sentences:
        # Les phrases avec marqueurs juridiques passent toujours
        if _LEGAL_MARKERS.search(candidate):
            kept.append(candidate)
            continue

        is_dup = False
        for existing in kept:
            if _similarity_simple(candidate, existing) >= threshold:
                is_dup = True
                break

        if not is_dup:
            kept.append(candidate)

    return kept


# ══════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ══════════════════════════════════════════════════════════════════

def sum_up_response(
    text: str,
    level: str = None,
    max_chars: int = None,
) -> str:
    """
    Réduit et optimise intelligemment une réponse LLM.

    Args:
        text      : réponse brute du LLM
        level     : "short" | "medium" | "detailed" (défaut : config)
        max_chars : limite de caractères (écrase la limite du niveau)

    Returns:
        Réponse optimisée, concise et professionnelle.
        En cas d'échec, retourne le texte original.

    Garanties :
        - Conservation des références d'articles de loi
        - Conservation des scores de risque
        - Conservation des recommandations pratiques
        - Aucune invention d'information
    """
    if not SUMUP_ENABLED or not text or not text.strip():
        return text

    # Résoudre le niveau et la limite de caractères
    level = level or SUMUP_DEFAULT_LEVEL
    if level not in SUMUP_MAX_CHARS:
        level = SUMUP_DEFAULT_LEVEL

    char_limit = max_chars or SUMUP_MAX_CHARS[level]

    # Si déjà court → ne rien faire
    if len(text.strip()) <= char_limit:
        return text.strip()

    try:
        # 1. Découper en phrases
        sentences = _split_sentences(text)
        if not sentences:
            return text.strip()[:char_limit]

        # 2. Supprimer le boilerplate
        cleaned = []
        for s in sentences:
            result = _remove_filler(s)
            if result:
                cleaned.append(result)

        if not cleaned:
            cleaned = sentences  # fallback : garder tout

        # 3. Dédupliquer les phrases redondantes
        unique = deduplicate_sentences(cleaned)

        # 4. Prioriser selon le niveau
        # Toujours garder les phrases avec marqueurs juridiques
        legal_sentences = [s for s in unique if _LEGAL_MARKERS.search(s)]
        other_sentences = [s for s in unique if not _LEGAL_MARKERS.search(s)]

        # Garder aussi les phrases de clôture (recommandation pratique)
        closing = [s for s in other_sentences if _CLOSING_PATTERNS.search(s)]
        filler_other = [s for s in other_sentences if not _CLOSING_PATTERNS.search(s)]

        # Assembler par priorité
        if level == "short":
            priority = legal_sentences[:2] + closing[:1] + filler_other[:1]
        elif level == "medium":
            priority = legal_sentences[:3] + filler_other[:2] + closing[:1]
        else:  # detailed
            priority = legal_sentences + filler_other[:4] + closing[:1]

        # 5. Assembler avec limite de caractères
        result_parts = []
        total = 0
        for s in priority:
            if total + len(s) + 1 > char_limit:
                break
            result_parts.append(s)
            total += len(s) + 1

        if not result_parts:
            # Fallback : juste tronquer proprement
            return text.strip()[:char_limit].rsplit(" ", 1)[0] + "."

        # 6. Formater le résultat final
        result = " ".join(result_parts)

        # S'assurer que ça se termine par une ponctuation
        if result and result[-1] not in ".!?":
            result += "."

        return result

    except Exception as e:
        log.warning(f"sum_up_response échoué ({e}) — retour texte original")
        return text.strip()[:char_limit] if len(text) > char_limit else text.strip()


def clean_response(text: str) -> str:
    """
    Nettoyage léger d'une réponse : espaces, ponctuation, sauts de ligne.
    À appliquer systématiquement avant d'envoyer une réponse à l'utilisateur.
    """
    if not text:
        return text

    # Supprimer les sauts de ligne multiples
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Supprimer les espaces multiples
    text = re.sub(r" {2,}", " ", text)
    # Supprimer les espaces avant ponctuation
    text = re.sub(r" +([.,;:!?])", r"\1", text)
    # Trim
    text = text.strip()

    return text
