"""
Estate Mind — Active Learning Feedback Loop
════════════════════════════════════════════
Le système apprend de ses erreurs sans réentraînement.

Quand un utilisateur signale une extraction NLP incorrecte via le frontend :
  → La correction est persistée dans data/state/corrections.json
  → Au prochain run, ces exemples corrigés sont injectés dans le few-shot prompt
  → Le LLM extrait mieux les cas similaires au run suivant

Flux :
  Frontend → POST /api/feedback/correction
  → ActiveLearningStore.add_correction()
  → Prochain run NLP : FewShotBuilder.build_prompt(base_prompt, n_shots=6)
  → Le LLM voit les exemples corrigés réels et généralise

Types de corrections supportées :
  - Prix mal extrait (ex: "million" mal parsé)
  - Surface absente mais présente dans la description
  - Type de bien mal classifié (duplex → villa, non → appartement)
  - Ville mal normalisée
  - Nombre de pièces mal inféré depuis "S+N"
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


CORRECTIONS_PATH = Path("data/state/corrections.json")
MAX_SHOTS        = 8     # max exemples injectés dans le prompt (évite context overflow)
MIN_SHOTS_TO_USE = 1     # utilise le feedback dès le 1er exemple


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Correction:
    """Représente une correction faite par un utilisateur."""
    correction_id:  str
    submitted_at:   str
    listing_url:    str
    listing_title:  str
    listing_desc:   str       # description brute (input du LLM)
    field_corrected:str       # "price" | "surface" | "rooms" | "property_type" | "city"
    value_wrong:    str       # valeur extraite par le LLM (incorrecte)
    value_correct:  str       # valeur correcte fournie par l'utilisateur
    user_comment:   Optional[str] = None
    used_in_runs:   int = 0   # compteur : combien de fois utilisé en few-shot


@dataclass
class FeedbackStats:
    total_corrections:   int = 0
    corrections_by_field:dict = field(default_factory=dict)
    most_corrected_field:str  = ""
    avg_used_in_runs:    float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# STORE — persistance des corrections
# ══════════════════════════════════════════════════════════════════════════════

class ActiveLearningStore:
    """Persiste et gère les corrections utilisateurs."""

    def __init__(self, path: Path = CORRECTIONS_PATH):
        self.path = path
        self._data: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def add_correction(
        self,
        listing_url:     str,
        listing_title:   str,
        listing_desc:    str,
        field_corrected: str,
        value_wrong:     str,
        value_correct:   str,
        user_comment:    Optional[str] = None,
    ) -> Correction:
        """Ajoute une correction utilisateur au store."""
        import uuid
        correction = Correction(
            correction_id   = uuid.uuid4().hex[:8],
            submitted_at    = datetime.utcnow().isoformat(),
            listing_url     = listing_url,
            listing_title   = listing_title[:80],
            listing_desc    = listing_desc[:400],
            field_corrected = field_corrected,
            value_wrong     = str(value_wrong),
            value_correct   = str(value_correct),
            user_comment    = user_comment,
        )
        self._data.append(asdict(correction))
        self._save()
        logger.info(
            f"[ActiveLearning] Correction enregistrée : "
            f"champ={field_corrected}, wrong='{value_wrong}' → correct='{value_correct}'"
        )
        return correction

    def get_corrections(
        self,
        field:   Optional[str] = None,
        limit:   int = MAX_SHOTS,
    ) -> list[Correction]:
        """Retourne les corrections les moins utilisées (pour maximiser la diversité)."""
        data = self._data
        if field:
            data = [c for c in data if c.get("field_corrected") == field]
        # Trie par used_in_runs ASC (priorité aux exemples frais)
        data = sorted(data, key=lambda c: c.get("used_in_runs", 0))
        return [Correction(**{k: v for k, v in c.items() if k in Correction.__dataclass_fields__})
                for c in data[:limit]]

    def mark_used(self, correction_ids: list[str]) -> None:
        """Incrémente le compteur d'utilisation."""
        for item in self._data:
            if item.get("correction_id") in correction_ids:
                item["used_in_runs"] = item.get("used_in_runs", 0) + 1
        self._save()

    def get_stats(self) -> FeedbackStats:
        stats = FeedbackStats(total_corrections=len(self._data))
        by_field: dict = {}
        for c in self._data:
            f = c.get("field_corrected", "?")
            by_field[f] = by_field.get(f, 0) + 1
        stats.corrections_by_field = by_field
        stats.most_corrected_field = max(by_field, key=by_field.get) if by_field else ""
        uses = [c.get("used_in_runs", 0) for c in self._data]
        stats.avg_used_in_runs = round(sum(uses) / max(len(uses), 1), 1)
        return stats


# ══════════════════════════════════════════════════════════════════════════════
# FEW-SHOT BUILDER — injecte les corrections dans le prompt NLP
# ══════════════════════════════════════════════════════════════════════════════

class FewShotBuilder:
    """
    Construit le few-shot prompt NLP enrichi avec les corrections utilisateurs.
    Au lieu d'exemples génériques, le LLM voit des cas réels qu'il a mal traités.
    """

    def __init__(self):
        self.store = ActiveLearningStore()

    def build_correction_block(self, n_shots: int = MAX_SHOTS) -> str:
        """
        Construit le bloc d'exemples corrigés à injecter dans le prompt NLP.
        Retourne une chaîne vide si pas assez de corrections.
        """
        corrections = self.store.get_corrections(limit=n_shots)
        if len(corrections) < MIN_SHOTS_TO_USE:
            return ""

        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "EXEMPLES CORRIGÉS PAR LES UTILISATEURS (apprends de ces erreurs réelles) :",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        for c in corrections:
            lines.append(f"""
CAS RÉEL ({c.field_corrected}) :
  Annonce : "{c.listing_title}"
  Description : "{c.listing_desc[:200]}..."
  ERREUR commise : {c.field_corrected} = "{c.value_wrong}" ← INCORRECT
  CORRECTION : {c.field_corrected} = "{c.value_correct}" ← CORRECT
  {f'Note utilisateur : {c.user_comment}' if c.user_comment else ''}""")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        # Marque ces corrections comme utilisées
        self.store.mark_used([c.correction_id for c in corrections])

        block = "\n".join(lines)
        logger.info(
            f"[ActiveLearning] {len(corrections)} exemple(s) corrigé(s) "
            f"injecté(s) dans le prompt NLP"
        )
        return block

    def enhance_prompt(self, base_prompt: str, n_shots: int = MAX_SHOTS) -> str:
        """
        Enrichit le prompt NLP de base avec les corrections utilisateurs.
        Insère le bloc avant la dernière ligne (instruction finale).
        """
        correction_block = self.build_correction_block(n_shots)
        if not correction_block:
            return base_prompt

        # Insère avant la dernière ligne du prompt
        lines = base_prompt.strip().split("\n")
        enhanced = "\n".join(lines[:-1]) + correction_block + lines[-1]
        return enhanced

    def get_stats_summary(self) -> str:
        """Résumé des stats pour le logging."""
        s = self.store.get_stats()
        if s.total_corrections == 0:
            return "Aucune correction utilisateur enregistrée."
        return (
            f"{s.total_corrections} corrections | "
            f"Champ le + corrigé : {s.most_corrected_field} | "
            f"Utilisées en moyenne : {s.avg_used_in_runs}x par run"
        )
