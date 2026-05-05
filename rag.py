"""
rag.py
─────────────────────────────────────────────────────────────────
RAG — Retrieval Augmented Generation
Recherche sémantique dans le texte brut du CDR tunisien.

Utilise MiniLM (déjà installé) pour encoder les chunks du PDF
et retrouver les passages les plus pertinents pour une question.

Supporte plusieurs PDFs :
  - pdf_francais.pdf     → CDR Loi n°65-5
  - pdf_urbanisme.pdf    → Code Aménagement Territoire (si disponible)
"""

import json, re, logging
from pathlib import Path
from config  import LOG_DIR, TXT_CLEAN

log = logging.getLogger("rag")
log.setLevel(logging.INFO)
if not log.handlers:
    _fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "rag.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)


# ══════════════════════════════════════════════════════════════════
# CHARGEMENT DES TEXTES
# ══════════════════════════════════════════════════════════════════

ROOT = Path(__file__).parent

# Sources disponibles
SOURCES = {
    "CDR": {
        "txt":   ROOT / "data" / "code_clean.txt",
        "cache": ROOT / "data" / "rag_cdr_chunks.json",
        "label": "Code des Droits Réels — Loi n°65-5",
    },
    "URBANISME": {
        "txt":   ROOT / "data" / "urbanisme_clean.txt",
        "cache": ROOT / "data" / "rag_urbanisme_chunks.json",
        "label": "Code de l'Aménagement du Territoire — 2011",
    },
}

_CHUNKS_CACHE: dict[str, list[dict]] = {}
_EMBEDDINGS_CACHE: dict[str, object] = {}
_MODEL = None


def _get_model():
    """Charge MiniLM une seule fois."""
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            log.info("Chargement MiniLM pour RAG...")
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            log.warning("sentence_transformers non disponible")
    return _MODEL


# ══════════════════════════════════════════════════════════════════
# CHUNKING DU TEXTE
# ══════════════════════════════════════════════════════════════════

def _chunk_text(txt: str, source_name: str) -> list[dict]:
    """
    Découpe le texte en chunks par article.
    Chaque chunk = un article du code juridique.
    """
    chunks = []

    # Découper par articles
    pattern = r'(Article\s+\d+[^\n]*\n(?:(?!Article\s+\d+).)*)'
    matches = re.findall(pattern, txt, re.DOTALL)

    for match in matches:
        text = match.strip()
        if len(text) < 50:
            continue

        # Extraire le numéro d'article
        art_match = re.match(r'Article\s+(\d+)', text)
        art_num   = art_match.group(1) if art_match else "?"

        chunks.append({
            "article": art_num,
            "text":    text[:1000],  # limiter la taille
            "source":  source_name,
        })

    # Si pas d'articles trouvés → chunking par paragraphes
    if not chunks:
        paragraphs = [p.strip() for p in txt.split('\n\n') if len(p.strip()) > 100]
        for i, para in enumerate(paragraphs):
            chunks.append({
                "article": str(i),
                "text":    para[:1000],
                "source":  source_name,
            })

    log.info(f"RAG {source_name} : {len(chunks)} chunks créés")
    return chunks


def _load_chunks(source_key: str) -> list[dict]:
    """Charge ou génère les chunks d'une source."""
    global _CHUNKS_CACHE

    if source_key in _CHUNKS_CACHE:
        return _CHUNKS_CACHE[source_key]

    src = SOURCES.get(source_key)
    if not src:
        return []

    # Vérifier cache sur disque
    if src["cache"].exists():
        with open(src["cache"], encoding="utf-8") as f:
            chunks = json.load(f)
        log.info(f"RAG {source_key} : {len(chunks)} chunks chargés depuis cache")
        _CHUNKS_CACHE[source_key] = chunks
        return chunks

    # Générer depuis le texte
    if not src["txt"].exists():
        log.warning(f"RAG {source_key} : fichier texte non trouvé ({src['txt']})")
        return []

    with open(src["txt"], encoding="utf-8") as f:
        txt = f.read()

    chunks = _chunk_text(txt, source_key)

    # Sauvegarder cache
    with open(src["cache"], "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    _CHUNKS_CACHE[source_key] = chunks
    return chunks


def _get_embeddings(chunks: list[dict], source_key: str):
    """Calcule ou charge les embeddings des chunks."""
    global _EMBEDDINGS_CACHE

    if source_key in _EMBEDDINGS_CACHE:
        return _EMBEDDINGS_CACHE[source_key]

    model = _get_model()
    if model is None:
        return None

    texts = [c["text"] for c in chunks]
    log.info(f"RAG {source_key} : encodage de {len(texts)} chunks...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    _EMBEDDINGS_CACHE[source_key] = embeddings
    return embeddings


# ══════════════════════════════════════════════════════════════════
# RECHERCHE RAG
# ══════════════════════════════════════════════════════════════════

def search(
    query:      str,
    sources:    list[str] = None,
    top_k:      int       = 3,
) -> list[dict]:
    """
    Recherche sémantique dans les sources disponibles.

    Args:
        query   : question de l'utilisateur
        sources : ["CDR", "URBANISME"] ou None pour toutes
        top_k   : nombre de résultats par source

    Returns:
        Liste de chunks pertinents triés par score
    """
    if sources is None:
        sources = [k for k in SOURCES if SOURCES[k]["txt"].exists()]

    if not sources:
        log.warning("Aucune source RAG disponible")
        return []

    model = _get_model()
    if model is None:
        return _fallback_search(query, sources, top_k)

    # Encoder la question
    try:
        import numpy as np
        query_emb = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
    except Exception as e:
        log.warning(f"Erreur encodage query : {e}")
        return _fallback_search(query, sources, top_k)

    all_results = []

    for src_key in sources:
        chunks = _load_chunks(src_key)
        if not chunks:
            continue

        embeddings = _get_embeddings(chunks, src_key)
        if embeddings is None:
            continue

        # Similarité cosinus
        scores = (embeddings @ query_emb).tolist()

        # Top-k
        indexed = sorted(enumerate(scores), key=lambda x: -x[1])[:top_k]
        for idx, score in indexed:
            if score > 0.2:  # seuil minimum de pertinence
                all_results.append({
                    "article":    chunks[idx]["article"],
                    "text":       chunks[idx]["text"],
                    "source":     src_key,
                    "source_label": SOURCES[src_key]["label"],
                    "score":      round(score, 3),
                })

    # Trier par score global
    all_results.sort(key=lambda x: -x["score"])
    return all_results[:top_k * len(sources)]


def _fallback_search(query: str, sources: list[str], top_k: int) -> list[dict]:
    """Recherche par mots-clés si MiniLM indisponible."""
    q = query.lower()
    words = [w for w in q.split() if len(w) > 3]
    results = []

    for src_key in sources:
        chunks = _load_chunks(src_key)
        scored = []
        for chunk in chunks:
            txt = chunk["text"].lower()
            score = sum(txt.count(w) for w in words)
            if score > 0:
                scored.append((score, chunk, src_key))

        scored.sort(key=lambda x: -x[0])
        for score, chunk, sk in scored[:top_k]:
            results.append({
                "article":     chunk["article"],
                "text":        chunk["text"],
                "source":      sk,
                "source_label": SOURCES[sk]["label"],
                "score":       score / 10,
            })

    results.sort(key=lambda x: -x["score"])
    return results[:top_k]


def format_context(results: list[dict], max_chars: int = 1500) -> str:
    """Formate les résultats RAG en contexte pour Mistral."""
    if not results:
        return ""

    lines = []
    total = 0
    for r in results:
        snippet = r["text"][:400]
        line = f"[{r['source_label']} — Art.{r['article']}] {snippet}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    return "\n\n".join(lines)


def available_sources() -> list[str]:
    """Retourne les sources RAG disponibles."""
    return [k for k in SOURCES if SOURCES[k]["txt"].exists()]


# ══════════════════════════════════════════════════════════════════
# INDEXATION D'UN NOUVEAU PDF
# ══════════════════════════════════════════════════════════════════

def index_pdf(pdf_path: str, source_key: str) -> dict:
    """
    Indexe un nouveau PDF pour le RAG.
    Utilise pdftotext pour extraire le texte.

    Args:
        pdf_path   : chemin vers le PDF
        source_key : clé dans SOURCES ("CDR" ou "URBANISME")
    """
    import subprocess

    pdf = Path(pdf_path)
    if not pdf.exists():
        return {"error": f"PDF non trouvé : {pdf_path}"}

    src = SOURCES.get(source_key)
    if not src:
        return {"error": f"Source inconnue : {source_key}"}

    # Extraire le texte
    txt_path = src["txt"]
    log.info(f"Extraction PDF {pdf.name} → {txt_path}")

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf), str(txt_path)],
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            return {"error": f"pdftotext échoué : {result.stderr.decode()}"}
    except FileNotFoundError:
        return {"error": "pdftotext non installé (Poppler requis)"}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout extraction PDF"}

    # Invalider le cache
    if src["cache"].exists():
        src["cache"].unlink()
    if source_key in _CHUNKS_CACHE:
        del _CHUNKS_CACHE[source_key]
    if source_key in _EMBEDDINGS_CACHE:
        del _EMBEDDINGS_CACHE[source_key]

    # Générer les nouveaux chunks
    chunks = _load_chunks(source_key)

    return {
        "success":  True,
        "source":   source_key,
        "pdf":      str(pdf),
        "chunks":   len(chunks),
        "txt_path": str(txt_path),
    }


# ══════════════════════════════════════════════════════════════════
# TEST EN LIGNE DE COMMANDE
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "sous-louer appartement sans accord"

    print(f"\n🔍 Recherche RAG : '{query}'")
    print(f"Sources disponibles : {available_sources()}")
    print()

    results = search(query, top_k=3)

    if not results:
        print("Aucun résultat trouvé.")
    else:
        for i, r in enumerate(results, 1):
            print(f"[{i}] Score={r['score']:.3f} | Art.{r['article']} | {r['source_label']}")
            print(f"    {r['text'][:200]}...")
            print()