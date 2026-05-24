"""
Estate Mind — NLP/LLM Cleaner
══════════════════════════════
Utilise le LLM pour extraire et structurer les champs manquants ou mal formés
à partir des descriptions textuelles des annonces.

Cas d'usage principaux :
  - Prix écrit en toutes lettres : "deux cent mille dinars" → 200000
  - Surface ambiguë : "env. 120m2 (selon cadastre)" → 120.0
  - Type non reconnu : "duplex avec jardin" → "villa"
  - Rooms absentes : extraites depuis "appartement 3 pièces" ou "S+2"

Architecture : few-shot prompting avec exemples concrets tunisiens.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config.settings import LLM_MODEL, OPENAI_API_KEY, NLP_TEMPERATURE, NLP_BATCH_SIZE


# ══════════════════════════════════════════════════════════════════════════════
# FEW-SHOT SYSTEM PROMPT
# La prof a insisté : c'est la qualité des exemples qui fait la différence.
# ══════════════════════════════════════════════════════════════════════════════

NLP_EXTRACTION_PROMPT = """Tu es un expert en immobilier tunisien chargé d'extraire des informations structurées depuis des annonces textuelles.

TÂCHE : À partir du titre et de la description d'une annonce, extrais et normalise ces champs :
  - price        : prix en TND (nombre entier), null si absent ou non numérique
  - surface      : surface en m² (nombre décimal), null si absente
  - rooms        : nombre de pièces (entier), null si absent
  - property_type: UN parmi [appartement, villa, maison, terrain, studio, bureau_local, immeuble, ferme, autre]
  - city         : ville normalisée en français (ex: "La Marsa", "Nabeul"), null si absente
  - governorate  : gouvernorat normalisé, null si absent
  - has_title_deed  : true si mention titre foncier / acte notarié / enregistré, false sinon
  - has_permit      : true si mention permis de construire / conforme, false sinon

RÈGLES :
  - "S+2" = 3 pièces (salon + 2 chambres), "S+3" = 4 pièces, etc.
  - "million" = × 1 000 000, "mille" ou "k" = × 1 000
  - Prix en devises étrangères → null (on ne convertit pas)
  - Retourne UNIQUEMENT du JSON valide, sans texte avant ou après

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXEMPLES (few-shot) — apprends de ces cas réels :
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXEMPLE 1
Entrée:
  titre: "Appt 3 pièces vue mer, 115 m2, 285 mille TND négoc, centre Hammamet"
  description: "Bel appartement rénové en 2022. Acte notarié. Résidence sécurisée avec gardien."
Sortie attendue:
{
  "price": 285000,
  "surface": 115.0,
  "rooms": 3,
  "property_type": "appartement",
  "city": "Hammamet",
  "governorate": "Nabeul",
  "has_title_deed": true,
  "has_permit": false
}

EXEMPLE 2
Entrée:
  titre: "URGENT vente terrain agri zone côtière"
  description: "Terrain agricole 2000m² bord de mer Ain Draham, sans notaire, paiement cash uniquement. Prix: 180.000"
Sortie attendue:
{
  "price": 180000,
  "surface": 2000.0,
  "rooms": null,
  "property_type": "terrain",
  "city": "Ain Draham",
  "governorate": "Jendouba",
  "has_title_deed": false,
  "has_permit": false
}

EXEMPLE 3
Entrée:
  titre: "S+4 duplex La Soukra"
  description: "Grand duplex standing, 220m2 habitable + 40m2 terrasse, 4 salles de bain, 2 parkings. Titre foncier disponible. 1,2 million TND ferme."
Sortie attendue:
{
  "price": 1200000,
  "surface": 220.0,
  "rooms": 5,
  "property_type": "villa",
  "city": "La Soukra",
  "governorate": "Ariana",
  "has_title_deed": true,
  "has_permit": false
}

EXEMPLE 4
Entrée:
  titre: "Bureau 85m2 Centre Sfax"
  description: "Local commercial au rez-de-chaussée, vitrine, électricité triphasée. Permis de construire conforme. Loyer possible."
Sortie attendue:
{
  "price": null,
  "surface": 85.0,
  "rooms": null,
  "property_type": "bureau_local",
  "city": "Sfax",
  "governorate": "Sfax",
  "has_title_deed": false,
  "has_permit": true
}

EXEMPLE 5 (cas difficile — prix en toutes lettres + S+N ambigu)
Entrée:
  titre: "Vente appart S+2 Marsa Plage"
  description: "Deux cent quatre-vingt mille dinars. Surface habitable soixante-quinze mètres carrés. Cuisine équipée, 2 SDB."
Sortie attendue:
{
  "price": 280000,
  "surface": 75.0,
  "rooms": 3,
  "property_type": "appartement",
  "city": "La Marsa",
  "governorate": "Tunis",
  "has_title_deed": false,
  "has_permit": false
}

EXEMPLE 6 (terrain sans infos)
Entrée:
  titre: "Vente terrain Zaghouan"
  description: "Contact pour plus d'infos. Sérieux s'abstenir. Prix à débattre."
Sortie attendue:
{
  "price": null,
  "surface": null,
  "rooms": null,
  "property_type": "terrain",
  "city": "Zaghouan",
  "governorate": "Zaghouan",
  "has_title_deed": false,
  "has_permit": false
}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Maintenant traite l'annonce suivante et retourne UNIQUEMENT le JSON :"""


# ══════════════════════════════════════════════════════════════════════════════
# HEURISTIQUES RAPIDES (sans LLM)
# Appliquées d'abord pour éviter les appels inutiles
# ══════════════════════════════════════════════════════════════════════════════

def _extract_sn(text: str) -> Optional[int]:
    """Extrait le nombre de pièces depuis 'S+N' tunisien."""
    m = re.search(r"[Ss]\+\s*(\d)", text)
    return int(m.group(1)) + 1 if m else None


def _extract_price_heuristic(text: str) -> Optional[float]:
    """Tente d'extraire un prix numérique basique."""
    text = text.lower().replace(" ", "").replace(",", ".")
    if "million" in text:
        m = re.search(r"([\d.]+)\s*million", text)
        return float(m.group(1)) * 1_000_000 if m else None
    if any(k in text for k in ["000dt", "000tnd", "k tnd"]):
        m = re.search(r"([\d.]+)\s*(?:000|k)", text)
        return float(m.group(1)) * 1_000 if m else None
    m = re.search(r"(\d{4,7})", text.replace(".", ""))
    return float(m.group(1)) if m else None


def _needs_llm_enrichment(row: pd.Series) -> bool:
    """Décide si une ligne nécessite un enrichissement LLM."""
    return any([
        pd.isna(row.get("price")) or row.get("price", 0) == 0,
        pd.isna(row.get("surface")) or row.get("surface", 0) == 0,
        pd.isna(row.get("rooms")),
        pd.isna(row.get("property_type")) or str(row.get("property_type")) in ("", "nan", "autre"),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# ENRICHISSEMENT LLM
# ══════════════════════════════════════════════════════════════════════════════

def enrich_single_listing(
    row: pd.Series,
    llm: ChatOpenAI,
) -> dict:
    """
    Enrichit une annonce unique via LLM.
    Retourne un dict avec les champs extraits (None si non trouvé).
    """
    title = str(row.get("title", ""))
    desc  = str(row.get("description", ""))[:800]   # tronque pour économiser tokens

    user_msg = f"titre: \"{title}\"\ndescription: \"{desc}\""

    try:
        response = llm.invoke([
            SystemMessage(content=NLP_EXTRACTION_PROMPT),
            HumanMessage(content=user_msg),
        ])
        raw = response.content.strip()

        # Nettoyage JSON défensif
        if "```" in raw:
            raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

        extracted = json.loads(raw)
        return extracted

    except json.JSONDecodeError as e:
        logger.warning(f"[nlp_cleaner] JSON invalide pour '{title[:40]}' : {e}")
        return {}
    except Exception as e:
        logger.warning(f"[nlp_cleaner] Erreur LLM pour '{title[:40]}' : {e}")
        return {}


def _merge_extracted(row: pd.Series, extracted: dict) -> pd.Series:
    """
    Fusionne les données extraites par le LLM avec la ligne existante.
    Règle : ne remplace un champ que s'il est vide/null dans la ligne d'origine.
    """
    row = row.copy()

    field_map = {
        "price":        "price",
        "surface":      "surface",
        "rooms":        "rooms",
        "property_type":"property_type",
        "city":         "city",
        "governorate":  "governorate",
    }

    for llm_key, df_col in field_map.items():
        llm_val = extracted.get(llm_key)
        if llm_val is None:
            continue
        current = row.get(df_col)
        if pd.isna(current) or current == "" or current == 0 or str(current) == "autre":
            row[df_col] = llm_val

    # Colonnes bonus (toujours ajoutées)
    row["has_title_deed"] = extracted.get("has_title_deed", False)
    row["has_permit"]     = extracted.get("has_permit", False)

    return row


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE BATCH
# ══════════════════════════════════════════════════════════════════════════════

def run_nlp_enrichment(
    df: pd.DataFrame,
    temperature: float = NLP_TEMPERATURE,
    batch_size:  int   = NLP_BATCH_SIZE,
    force_all:   bool  = False,
) -> pd.DataFrame:
    """
    Enrichit le DataFrame avec le LLM pour les lignes qui en ont besoin.

    Hyperparamètres :
        temperature : 0.0 = déterministe (recommandé pour extraction)
                      0.2 = légère variabilité (utile si les annonces sont très floues)
        batch_size  : nombre de lignes traitées par lot (pour logs + monitoring)
        force_all   : True = enrichit toutes les lignes (coûteux, pour démo)

    Returns:
        DataFrame enrichi avec colonnes supplémentaires :
        has_title_deed, has_permit, nlp_enriched (bool)
    """
    logger.info(f"[nlp_cleaner] 🚀 Enrichissement NLP démarré (temperature={temperature})")

    # Filtrage des lignes à enrichir
    if force_all:
        mask = pd.Series([True] * len(df), index=df.index)
    else:
        mask = df.apply(_needs_llm_enrichment, axis=1)

    n_to_enrich = mask.sum()
    logger.info(f"[nlp_cleaner] {n_to_enrich}/{len(df)} lignes nécessitent un enrichissement LLM")

    if n_to_enrich == 0:
        df["nlp_enriched"]  = False
        df["has_title_deed"]= False
        df["has_permit"]    = False
        return df

    llm = ChatOpenAI(
        model       = LLM_MODEL,
        temperature = temperature,
        api_key     = OPENAI_API_KEY,
        max_tokens  = 300,   # extraction JSON courte
    )

    rows_enriched = []
    indices_to_enrich = df[mask].index.tolist()

    for batch_start in range(0, len(indices_to_enrich), batch_size):
        batch_idx = indices_to_enrich[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(indices_to_enrich) + batch_size - 1) // batch_size
        logger.info(f"[nlp_cleaner] Batch {batch_num}/{total_batches} ({len(batch_idx)} lignes)")

        for idx in batch_idx:
            row       = df.loc[idx]
            extracted = enrich_single_listing(row, llm)
            new_row   = _merge_extracted(row, extracted)
            new_row["nlp_enriched"] = bool(extracted)
            rows_enriched.append((idx, new_row))

    # Réintègre les lignes enrichies
    for idx, enriched_row in rows_enriched:
        df.loc[idx] = enriched_row

    # Lignes non enrichies
    df.loc[~mask, "nlp_enriched"]   = False
    df.loc[~mask, "has_title_deed"] = False
    df.loc[~mask, "has_permit"]     = False

    n_success = sum(1 for _, r in rows_enriched if r.get("nlp_enriched"))
    logger.info(f"[nlp_cleaner] ✅ {n_success}/{n_to_enrich} lignes enrichies avec succès")
    return df
