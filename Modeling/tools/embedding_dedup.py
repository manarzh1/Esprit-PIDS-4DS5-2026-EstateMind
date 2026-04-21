"""
Estate Mind — Embedding-based Deduplication
═════════════════════════════════════════════
Détecte les quasi-doublons que le Jaccard rate :

  Tayara  : "Villa avec piscine Hammamet 450K"
  Mubawab : "Somptueuse propriété bord de mer Nabeul 450 000 TND"
  → Même bien, URLs différentes → Jaccard = 0.12, Embedding cosine = 0.87 ✓

Stratégie :
  1. Construit un texte représentatif de chaque annonce (titre + ville + prix + surface)
  2. Calcule les embeddings via OpenAI text-embedding-3-small (ou fallback TF-IDF)
  3. Trouve les paires au-dessus du seuil de similarité cosinus
  4. Garde la version de la source la plus fiable (Remax > Tecnocasa > Mubawab > Tayara)

Fallback intelligent :
  Si l'API OpenAI est indisponible → TF-IDF scikit-learn (100% local, gratuit)
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from config.settings import OPENAI_API_KEY, EMBED_MODEL

# Priorité de source (garde la meilleure en cas de doublon)
SOURCE_PRIORITY = {"remax":1,"tecnocasa":2,"mubawab":3,"tayara":4,"csv":5}
DEFAULT_EMBEDDING_THRESHOLD = 0.88   # cosine similarity seuil


def _build_listing_text(row: pd.Series) -> str:
    """Construit un texte représentatif de l'annonce pour l'embedding."""
    parts = []
    if pd.notna(row.get("title")):       parts.append(str(row["title"])[:80])
    if pd.notna(row.get("city")):        parts.append(str(row["city"]))
    if pd.notna(row.get("property_type")):parts.append(str(row["property_type"]))
    if pd.notna(row.get("price")):       parts.append(f"{row['price']:.0f} TND")
    if pd.notna(row.get("surface")):     parts.append(f"{row['surface']:.0f}m2")
    if pd.notna(row.get("description")):
        parts.append(str(row["description"])[:120])
    return " | ".join(parts)


# ── Embeddings via OpenAI ────────────────────────────────────────────────────

def _embed_openai(texts: list[str], batch_size: int = 100) -> Optional[np.ndarray]:
    """Calcule les embeddings via OpenAI text-embedding-3-small."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            response = client.embeddings.create(
                model=EMBED_MODEL,
                input=batch,
            )
            batch_emb = [e.embedding for e in response.data]
            all_embeddings.extend(batch_emb)
            if i + batch_size < len(texts):
                time.sleep(0.1)   # politesse rate limit
        return np.array(all_embeddings, dtype=np.float32)
    except Exception as e:
        logger.warning(f"[EmbeddingDedup] OpenAI échoué : {e} → fallback TF-IDF")
        return None


def _embed_tfidf(texts: list[str]) -> np.ndarray:
    """Fallback TF-IDF local (scikit-learn)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=8000,
        sublinear_tf=True,
        analyzer="char_wb",   # robuste aux fautes et variantes orthographiques
    )
    matrix = vectorizer.fit_transform(texts)
    return matrix.toarray().astype(np.float32)


def _cosine_similarity_batch(
    embeddings: np.ndarray,
    indices_a:  list[int],
    indices_b:  list[int],
) -> np.ndarray:
    """Calcule la similarité cosinus entre deux listes d'indices."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    normed = embeddings / norms
    a_vecs = normed[indices_a]
    b_vecs = normed[indices_b]
    return np.sum(a_vecs * b_vecs, axis=1)


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_embedding_dedup(
    df:        pd.DataFrame,
    threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
    max_comparisons: int = 50_000,  # limite anti-OOM pour gros datasets
) -> pd.DataFrame:
    """
    Déduplication sémantique par embeddings.

    Algorithme :
      1. Filtre rapide : regroupement par price_bucket + city pour réduire O(n²)
      2. Embedding de chaque groupe candidat
      3. Comparaison cosinus par paires dans chaque groupe
      4. Conservation de la source la plus fiable

    Args:
        df            : DataFrame avec colonnes title, city, price, surface, description
        threshold     : seuil de similarité cosinus [0-1]
        max_comparisons: limite de paires à comparer (évite OOM)

    Returns:
        DataFrame dédupliqué + colonne 'embedding_dup_removed' (count)
    """
    if df.empty or len(df) < 2:
        return df

    logger.info(f"[EmbeddingDedup] Démarrage sur {len(df)} annonces (threshold={threshold})")
    t0 = time.time()

    df = df.copy().reset_index(drop=True)
    df["_priority"] = df["source"].map(SOURCE_PRIORITY).fillna(99)
    df["_price_bucket"] = (df["price"].fillna(0) // 20_000 * 20_000).astype(int)
    df["_city_norm"]    = df["city"].fillna("").str.lower().str[:15]
    df["_text"]         = df.apply(_build_listing_text, axis=1)

    # Trie par priorité de source
    df = df.sort_values("_priority").reset_index(drop=True)

    dup_indices: set = set()
    n_comparisons = 0

    # Regroupement par (price_bucket, city_norm) pour limiter les paires
    groups = df.groupby(["_price_bucket", "_city_norm"]).groups
    candidate_groups = [(k, list(v)) for k, v in groups.items() if len(v) >= 2]

    logger.info(f"[EmbeddingDedup] {len(candidate_groups)} groupes candidats à comparer")

    for key, group_indices in candidate_groups:
        if n_comparisons >= max_comparisons:
            logger.warning(f"[EmbeddingDedup] Limite de {max_comparisons} comparaisons atteinte")
            break
        if len(group_indices) < 2:
            continue

        # Filtre les doublons déjà identifiés
        active = [i for i in group_indices if i not in dup_indices]
        if len(active) < 2:
            continue

        # Embeddings du groupe
        texts = df.loc[active, "_text"].tolist()
        embeddings = _embed_openai(texts)
        if embeddings is None:
            embeddings = _embed_tfidf(texts)

        # Comparaison par paires
        n = len(active)
        for i in range(n):
            if active[i] in dup_indices:
                continue
            for j in range(i + 1, n):
                if active[j] in dup_indices:
                    continue
                n_comparisons += 1

                sim = float(_cosine_similarity_batch(
                    embeddings,
                    [i], [j]
                )[0])

                if sim >= threshold:
                    # Garde l'index de moindre priorité (= plus grand _priority)
                    pi = df.loc[active[i], "_priority"]
                    pj = df.loc[active[j], "_priority"]
                    to_remove = active[j] if pi <= pj else active[i]
                    dup_indices.add(to_remove)
                    logger.debug(f"[EmbeddingDedup] Doublon: idx {active[i]} ~ idx {active[j]} (sim={sim:.3f})")

    # Nettoyage
    df_clean = df[~df.index.isin(dup_indices)].copy()
    df_clean = df_clean.drop(columns=["_priority","_price_bucket","_city_norm","_text"])

    elapsed = round(time.time() - t0, 2)
    n_removed = len(dup_indices)
    logger.info(
        f"[EmbeddingDedup] {n_removed} doublons sémantiques supprimés "
        f"({n_comparisons} paires comparées) en {elapsed}s"
    )
    return df_clean.reset_index(drop=True)
