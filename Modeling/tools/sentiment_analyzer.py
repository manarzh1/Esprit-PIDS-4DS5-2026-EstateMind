"""
Estate Mind — Sentiment Analyzer (BO2)
════════════════════════════════════════
Analyse de sentiment des descriptions d'annonces via LLM.

Pourquoi l'analyse de sentiment pour l'immobilier tunisien ?
  - Un texte peut être très positif ("villa exceptionnelle !") mais trompeur
  - On détecte les patterns de manipulation linguistique :
    * Superlatifs excessifs sans données concrètes → signal de fraude
    * Urgence artificielle ("offre limitée", "dernier appartement")
    * Incohérences sémantiques (prix "négociable" + "prix fixe")
    * Manque de détails concrets = description volontairement vague
  - Le sentiment seul ne suffit PAS → il est 1 signal parmi 5 dans le trust score

Architecture du Trust Score Enrichi (BO2) :
  ┌─────────────────────────────────────────────────────────┐
  │  Trust Score Global = moyenne pondérée de 5 signaux     │
  │                                                         │
  │  1. Sentiment LLM           (25%) ← CE FICHIER         │
  │  2. Cohérence données       (25%) ← risk_tools.py      │
  │  3. Détection fraude        (20%) ← risk_tools.py      │
  │  4. Complétude annonce      (15%) ← risk_tools.py      │
  │  5. Fiabilité source        (15%) ← SOURCE_SCORES      │
  └─────────────────────────────────────────────────────────┘

Sortie du sentiment analyzer :
  sentiment_score    : float [0-1] (0=très négatif/suspect, 1=très positif/fiable)
  sentiment_label    : "positif_fiable" | "neutre" | "positif_suspect" | "negatif"
  manipulation_flags : liste des signaux de manipulation détectés
  confidence         : confiance du LLM [0-1]
  details            : explication en français
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger


@dataclass
class SentimentResult:
    """Résultat de l'analyse de sentiment d'une annonce."""
    sentiment_score:    float           # [0-1] : 0=suspect, 1=fiable
    sentiment_label:    str             # positif_fiable | neutre | positif_suspect | negatif
    manipulation_flags: list            # signaux de manipulation détectés
    confidence:         float           # confiance du LLM [0-1]
    details:            str             # explication
    raw_response:       Optional[str]   = None
    method:             str             = "llm"
    analyzed_at:        str             = field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Prompt d'analyse de sentiment ────────────────────────────────────────────

SENTIMENT_SYSTEM_PROMPT = """Tu es un expert en détection de fraude immobilière sur le marché tunisien.
Analyse le texte d'une annonce immobilière et retourne une évaluation JSON structurée.

IMPORTANT : Un texte positif ne signifie PAS automatiquement une annonce fiable.
Tu dois détecter les patterns de manipulation linguistique typiques des annonces frauduleuses.

Patterns de manipulation à détecter :
  - Superlatifs excessifs sans données concrètes ("exceptionnelle", "unique au monde", "incroyable")
  - Urgence artificielle ("offre limitée", "à saisir maintenant", "dernier disponible")
  - Vagueness intentionnelle (prix "négociable" sans fourchette, description floue)
  - Incohérences sémantiques (texte haut de gamme + prix impossiblement bas)
  - Numéros de téléphone répétés dans la description (spam indicator)
  - Promesses non-vérifiables ("vue imprenable garantie", "quartier le plus calme de Tunis")
  - Manque de détails techniques (pas de surface, pas d'étage, pas de nombre de pièces)
  - Fautes d'orthographe excessives (indicateur d'annonce peu sérieuse)
  - Mots-clés juridiques suspects ("sans acte notarié", "arrangement à l'amiable", "en cours de régularisation")

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "sentiment_score": 0.75,
  "sentiment_label": "positif_fiable",
  "manipulation_flags": [],
  "confidence": 0.85,
  "details": "Description professionnelle avec données concrètes. Aucun signal de manipulation.",
  "text_quality": "haute"
}

sentiment_label options :
  "positif_fiable"   → texte positif ET cohérent, pas de manipulation
  "neutre"           → texte factuel, informatif, acceptable
  "positif_suspect"  → très positif MAIS avec signaux de manipulation
  "negatif"          → texte négatif ou très lacunaire
  "spam"             → texte clairement frauduleux ou hors contexte"""

# ── Heuristiques rapides (sans LLM) ──────────────────────────────────────────

MANIPULATION_PATTERNS = {
    "urgence_artificielle": [
        "offre limitée", "à saisir", "dernier disponible", "ne manquez pas",
        "offre exceptionnelle valable", "urgent", "vente rapide", "à vendre vite",
    ],
    "superlatifs_vagues": [
        "exceptionnel", "unique au monde", "incroyable opportunité", "rarissime",
        "splendide", "magnifique au-delà", "incomparable", "sans égal",
    ],
    "manque_infos_critiques": [],    # détecté par absence de champs
    "juridique_suspect": [
        "sans acte", "arrangement amiable", "en cours de régularisation",
        "sans titre", "sous seing privé uniquement", "affaire à régler",
    ],
    "spam_indicators": [
        r"\d{8,}",          # numéros de téléphone répétés
        r"(.)\1{4,}",       # caractères répétés (aaaa, !!!)
    ],
}

def _heuristic_sentiment(text: str, row: Optional[pd.Series] = None) -> SentimentResult:
    """
    Analyse heuristique sans LLM — rapide et gratuite.
    Moins précise mais utilisable comme fallback ou pré-filtre.
    """
    if not text or len(text.strip()) < 20:
        return SentimentResult(
            sentiment_score=0.3, sentiment_label="negatif",
            manipulation_flags=["description_vide_ou_trop_courte"],
            confidence=0.9, details="Description absente ou trop courte.",
            method="heuristic",
        )

    text_lower = text.lower()
    flags      = []
    score      = 0.6   # score de départ neutre

    # Détection des patterns de manipulation
    for pattern_type, keywords in MANIPULATION_PATTERNS.items():
        for kw in keywords:
            if kw.startswith(r"\d") or kw.startswith("("):
                # Regex
                if re.search(kw, text):
                    flags.append(pattern_type)
                    break
            elif kw in text_lower:
                flags.append(pattern_type)
                break

    # Pénalités pour les flags
    flag_penalties = {
        "urgence_artificielle":    -0.15,
        "superlatifs_vagues":      -0.10,
        "juridique_suspect":       -0.25,
        "spam_indicators":         -0.30,
    }
    for f in set(flags):
        score += flag_penalties.get(f, -0.10)

    # Bonus pour signaux positifs
    positive_signals = [
        "titre foncier", "acte notarié", "superficie", "m²",
        "étage", "ascenseur", "parking", "chauffage central",
    ]
    n_positive = sum(1 for s in positive_signals if s in text_lower)
    score += min(n_positive * 0.05, 0.20)

    # Longueur de description (une bonne description = plus fiable)
    if len(text) > 300:  score += 0.10
    elif len(text) < 50: score -= 0.15

    score = max(0.0, min(1.0, score))

    if score >= 0.75:   label = "positif_fiable"
    elif score >= 0.55: label = "neutre"
    elif score >= 0.35: label = "positif_suspect" if flags else "neutre"
    else:               label = "negatif"

    details = (
        f"Score {score:.2f}. "
        + (f"Flags : {', '.join(set(flags))}." if flags else "Aucun flag de manipulation.")
        + f" {n_positive} signal(s) positif(s) détecté(s)."
    )

    return SentimentResult(
        sentiment_score=round(score, 3), sentiment_label=label,
        manipulation_flags=list(set(flags)), confidence=0.65,
        details=details, method="heuristic",
    )


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """
    Analyseur de sentiment pour les annonces immobilières tunisiennes.

    Combine :
      1. Analyse LLM (si OpenAI disponible) pour la sémantique profonde
      2. Heuristiques regex pour les patterns manifestes
      3. Signaux structurels (complétude, cohérence)

    Produit un sentiment_score [0-1] qui entre dans le trust score global
    avec un poids de 25%.
    """

    def __init__(self, use_llm: bool = True, temperature: float = 0.0):
        self.use_llm     = use_llm
        self.temperature = temperature
        self._llm        = None

    def _get_llm(self):
        """Initialise le LLM paresseusement."""
        if self._llm is not None:
            return self._llm
        try:
            from langchain_openai import ChatOpenAI
            from config.settings import LLM_MODEL, OPENAI_API_KEY
            if not OPENAI_API_KEY:
                return None
            self._llm = ChatOpenAI(
                model=LLM_MODEL, temperature=self.temperature,
                api_key=OPENAI_API_KEY, max_tokens=400,
            )
            return self._llm
        except Exception as e:
            logger.warning(f"[Sentiment] LLM non disponible : {e}")
            return None

    def analyze(
        self,
        description:   str,
        title:         str          = "",
        row:           Optional[pd.Series] = None,
        use_heuristic_always: bool  = False,
    ) -> SentimentResult:
        """
        Analyse le sentiment d'une annonce immobilière.

        Args:
            description          : texte complet de la description
            title                : titre de l'annonce (optionnel)
            row                  : ligne complète pour les signaux structurels
            use_heuristic_always : force le mode heuristique (sans LLM)

        Returns:
            SentimentResult avec score, label, flags, confidence, details
        """
        text = f"{title}\n{description}".strip() if title else description.strip()

        # Texte vide → score bas direct
        if not text or len(text) < 10:
            return SentimentResult(
                sentiment_score=0.2, sentiment_label="negatif",
                manipulation_flags=["no_description"], confidence=1.0,
                details="Aucune description fournie.", method="heuristic",
            )

        # Mode heuristique si LLM non souhaité ou non disponible
        if use_heuristic_always or not self.use_llm:
            return _heuristic_sentiment(text, row)

        llm = self._get_llm()
        if llm is None:
            return _heuristic_sentiment(text, row)

        # ── Analyse LLM ───────────────────────────────────────────────────────
        try:
            prompt = f"""Analyse cette annonce immobilière tunisienne :

TITRE : {title[:100] if title else 'Non fourni'}
DESCRIPTION : {description[:600]}

Détecte les signaux de manipulation et évalue la fiabilité du texte."""

            from langchain_core.messages import SystemMessage, HumanMessage
            response = llm.invoke([
                SystemMessage(content=SENTIMENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])

            raw = response.content.strip()

            # Parse JSON
            json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(raw)

            # Enrichit avec les heuristiques pour les flags manifestes
            heuristic = _heuristic_sentiment(text, row)
            llm_flags = data.get("manipulation_flags", [])
            combined_flags = list(set(llm_flags + heuristic.manipulation_flags))

            # Combine score LLM + heuristique (LLM plus fiable)
            llm_score  = float(data.get("sentiment_score", 0.5))
            combined   = 0.7 * llm_score + 0.3 * heuristic.sentiment_score

            return SentimentResult(
                sentiment_score=round(max(0, min(1, combined)), 3),
                sentiment_label=data.get("sentiment_label", "neutre"),
                manipulation_flags=combined_flags,
                confidence=float(data.get("confidence", 0.75)),
                details=data.get("details", ""),
                raw_response=raw,
                method="llm+heuristic",
            )

        except Exception as e:
            logger.warning(f"[Sentiment] Parsing LLM échoué : {e} → fallback heuristique")
            return _heuristic_sentiment(text, row)

    def analyze_batch(
        self,
        df:          pd.DataFrame,
        max_rows:    int  = 500,
        use_llm:     bool = False,   # False par défaut en batch (coût)
    ) -> pd.DataFrame:
        """
        Analyse de sentiment sur un DataFrame.
        Ajoute les colonnes : sentiment_score, sentiment_label, manipulation_flags
        """
        logger.info(f"[Sentiment] Analyse de {min(len(df), max_rows)} annonces...")
        results = []
        subset  = df.head(max_rows)

        for _, row in subset.iterrows():
            desc   = str(row.get("description", "") or "")
            title  = str(row.get("title", "") or "")
            result = self.analyze(
                description=desc, title=title, row=row,
                use_heuristic_always=not use_llm,
            )
            results.append({
                "sentiment_score":     result.sentiment_score,
                "sentiment_label":     result.sentiment_label,
                "manipulation_flags":  ",".join(result.manipulation_flags),
                "sentiment_confidence":result.confidence,
            })

        # Complète les lignes non analysées
        while len(results) < len(df):
            results.append({
                "sentiment_score": 0.5, "sentiment_label": "neutre",
                "manipulation_flags": "", "sentiment_confidence": 0.0,
            })

        for col in ["sentiment_score", "sentiment_label", "manipulation_flags", "sentiment_confidence"]:
            df[col] = [r[col] for r in results]

        logger.info(f"[Sentiment] Terminé. Score moyen : {df['sentiment_score'].mean():.3f}")
        return df


# ══════════════════════════════════════════════════════════════════════════════
# TRUST SCORE ENRICHI (BO2 suggestion prof)
# ══════════════════════════════════════════════════════════════════════════════

def compute_enriched_trust_score(
    row:           pd.Series,
    df_ref:        pd.DataFrame,
    sentiment:     Optional[SentimentResult] = None,
) -> dict:
    """
    Trust Score enrichi combinant 5 signaux — suggestion de la prof.

    Architecture :
      Signal 1 — Sentiment LLM        (25%) : analyse textuelle profonde
      Signal 2 — Cohérence données    (25%) : prix/m² vs médiane, surface bornes
      Signal 3 — Détection fraude     (20%) : doublons, patterns spam
      Signal 4 — Complétude annonce   (15%) : champs critiques présents
      Signal 5 — Fiabilité source     (15%) : score par source

    Returns :
        dict avec trust_score_enriched, trust_level, breakdown, signals
    """
    from tools.gru_trust_classifier import SOURCE_SCORES, THRESHOLDS

    price    = float(row.get("price",   0) or 0)
    surface  = float(row.get("surface", 0) or 0)
    desc     = str(row.get("description", "") or "")
    source   = str(row.get("source", "unknown") or "").lower()
    city     = str(row.get("city", "") or "")

    # ── Signal 1 : Sentiment (25%) ────────────────────────────────────────────
    if sentiment:
        s1 = sentiment.sentiment_score
    else:
        s1 = _heuristic_sentiment(desc).sentiment_score

    # ── Signal 2 : Cohérence données (25%) ───────────────────────────────────
    city_prices = df_ref[df_ref["city"].astype(str) == city]["price"].dropna() if "city" in df_ref.columns else pd.Series()
    med_price   = float(city_prices.median()) if not city_prices.empty else 200_000

    s2 = 0.5  # défaut
    if price > 0 and surface > 0:
        ppm2          = price / surface
        nat_ppm2_med  = float(df_ref["price_per_m2"].dropna().median()) if "price_per_m2" in df_ref.columns else 2200
        ppm2_ratio    = ppm2 / max(nat_ppm2_med, 1)
        # Cohérence si ratio entre 0.4 et 2.5 (ni trop bas ni trop haut)
        s2 = 1.0 - min(abs(ppm2_ratio - 1.0), 1.5) / 1.5
        s2 = max(0.1, s2)

    # ── Signal 3 : Détection fraude (20%) ─────────────────────────────────────
    s3 = 1.0
    # Prix à 0 ou anormalement bas
    if price == 0 or (price > 0 and price < 500):  s3 -= 0.4
    # Surface aberrante
    if surface > 0 and (surface < 5 or surface > 5000):  s3 -= 0.3
    # Description trop courte
    if len(desc) < 30:  s3 -= 0.2
    # Numéro de téléphone dans la description (souvent spam)
    if re.search(r'\b[2-9]\d{7}\b', desc):  s3 -= 0.1
    s3 = max(0.0, s3)

    # ── Signal 4 : Complétude (15%) ───────────────────────────────────────────
    critical_fields = ["price", "surface", "city", "property_type", "description", "url"]
    present = sum(1 for f in critical_fields if pd.notna(row.get(f)) and str(row.get(f, "")).strip() not in ("", "nan", "0", "0.0"))
    s4 = present / len(critical_fields)

    # ── Signal 5 : Fiabilité source (15%) ────────────────────────────────────
    s5 = SOURCE_SCORES.get(source, 0.45)

    # ── Trust Score Global ────────────────────────────────────────────────────
    weights = [0.25, 0.25, 0.20, 0.15, 0.15]
    signals = [s1, s2, s3, s4, s5]
    trust_score_enriched = float(sum(w * s for w, s in zip(weights, signals)))
    trust_score_enriched = round(max(0.0, min(1.0, trust_score_enriched)), 3)

    trust_level = (
        "Fiable"  if trust_score_enriched >= THRESHOLDS[1] else
        "Moyen"   if trust_score_enriched >= THRESHOLDS[0] else
        "Suspect"
    )

    return {
        "trust_score_enriched": trust_score_enriched,
        "trust_level":          trust_level,
        "breakdown": {
            "sentiment_llm":     {"score": round(s1, 3), "weight": "25%"},
            "data_coherence":    {"score": round(s2, 3), "weight": "25%"},
            "fraud_detection":   {"score": round(s3, 3), "weight": "20%"},
            "completeness":      {"score": round(s4, 3), "weight": "15%"},
            "source_reliability":{"score": round(s5, 3), "weight": "15%"},
        },
        "manipulation_flags": sentiment.manipulation_flags if sentiment else [],
    }


# ── Singleton global ──────────────────────────────────────────────────────────
_analyzer: Optional[SentimentAnalyzer] = None

def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer(use_llm=True, temperature=0.0)
    return _analyzer
