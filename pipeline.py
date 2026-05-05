"""
pipeline.py
─────────────────────────────────────────────────────────────────
Steps 1-6 : PDF → texte propre → articles → règles LLM
            → nettoyage → Knowledge Graph → Risk Score

BO5 — Code des Droits Réels tunisien
"""

import json, csv, re, hashlib, time, logging, subprocess, tempfile
from pathlib import Path
from datetime import date
from collections import Counter
from typing import Optional

try:
    import requests as _req
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False

from config import (
    SOURCE_NAME, SOURCE_VERSION, SOURCE_LAW,
    DOMAIN_KW, NOISE_KW, HALLUCINATION_SIGNALS,
    ACTOR_MAP, KNOWN_ACTORS,
    STATUS_BASE, ACTOR_WEIGHT, HIGH_RISK_VERBS,
    OLLAMA_URL, LLM_MODEL, LLM_TEMP, LLM_RETRIES, LLM_SLEEP,
    TXT_CLEAN, ARTICLES_JSON, RULES_RAW, RULES_CLEAN,
    NEO4J_DIR, LOG_DIR, DATA_DIR,
)

TODAY = str(date.today())

# ── Logger ─────────────────────────────────────────────────────────────────────
_fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
log = logging.getLogger("pipeline")
log.setLevel(logging.INFO)
if not log.handlers:
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — EXTRACTION PDF + NETTOYAGE WATERMARK
# ══════════════════════════════════════════════════════════════════════════════

# Ce PDF contient un filigrane vertical "République Tunisienne"
# imprimé en rotation — tokens avec grande marge (>40sp) et ≤5 chars
_WM = {
    'ne','en','si','ni','Tu','ue','liq','ub','ép','R','la','de','le','el',
    'ci','ffi','O','ie','er','im','pr','Im','e','n','i','s','u','T','q',
    'b','p','é','a','d','f',
}
_WM_RE = re.compile(
    r'\n(?:ne|en|si|ni|Tu|ue|liq|ub|ép|R|la|de|le|el|ci|ffi|O|ie|er|im|pr|Im)\s*(?=\n)',
    re.MULTILINE,
)


def _clean_page(page: str) -> str:
    out = []
    for line in page.splitlines():
        s = line.strip()
        if not s:
            continue
        lead = len(line) - len(line.lstrip())
        if lead > 40 and len(s) <= 5 and s in _WM:
            continue
        if "Imprimerie Officielle" in line:
            continue
        if re.match(r"^\s*\d{1,3}\s*$", line):
            continue
        if re.match(r"^\s*[\.\…]{4,}", line):
            continue
        out.append(s)
    return "\n".join(out)


def extract_text(pdf_path: Optional[str] = None) -> str:
    """
    STEP 1 : PDF → code_clean.txt
    Utilise pdftotext -layout (optimal pour ce PDF).
    Filtre le watermark vertical sur 2 passes.
    Valide que le document est bien dans le domaine.
    """
    src = str(pdf_path) if pdf_path else str(
        Path(__file__).parent / "pdf_francais.pdf"
    )
    log.info(f"[STEP 1] Extraction PDF : {src}")

    tmp = tempfile.mktemp(suffix=".txt")
    r = subprocess.run(
        ["pdftotext", "-layout", src, tmp],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"pdftotext échoué : {r.stderr}")

    with open(tmp, encoding="utf-8") as f:
        raw = f.read()
    Path(tmp).unlink(missing_ok=True)

    pages = raw.split("\f")
    full  = "\n".join(_clean_page(p) for p in pages if _clean_page(p).strip())
    full  = _WM_RE.sub("\n", full)
    full  = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", full)
    full  = re.sub(r"\n{3,}", "\n\n", full)

    hits = sum(full.lower().count(kw) for kw in DOMAIN_KW)
    if hits < 50:
        raise ValueError(
            f"Document hors domaine ({hits} hits). "
            f"Vérifiez que le fichier est le Code des Droits Réels tunisien."
        )

    with open(TXT_CLEAN, "w", encoding="utf-8") as f:
        f.write(full)

    log.info(
        f"         → {len(pages)} pages | {len(full):,} chars | "
        f"{hits} hits domaine → {TXT_CLEAN}"
    )
    return full


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — DÉCOUPAGE EN ARTICLES
# ══════════════════════════════════════════════════════════════════════════════

_ART_RE = re.compile(
    r"(?:^|\n)(Article\s+(?:premier|Premier|1er|\d+)\s*[\.\-–])\s*(.*?)"
    r"(?=(?:\nArticle\s+(?:premier|Premier|1er|\d+)\s*[\.\-–])|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _parse_art_num(raw: str) -> Optional[int]:
    r = raw.strip().lower()
    if r in ("premier", "1er", "1ere", "première"):
        return 1
    try:
        return int(r)
    except ValueError:
        return None


def _clean_body(text: str) -> str:
    text = re.sub(r"Imprimerie Officielle[^\n]*", "", text)
    text = re.sub(r"\n\s*\d{1,3}\s*\n", "\n", text)
    text = re.sub(r"[\.\…]{5,}[^\n]*", "", text)
    text = re.sub(r"\n\s*[a-zA-ZÀ-ÿ]{1,2}\s*\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_articles(txt_path: Optional[str] = None) -> list[dict]:
    """
    STEP 2 : texte → articles.json
    Chaque article porte source_*, article_ref, article_number, text_hash.
    """
    src = Path(txt_path) if txt_path else TXT_CLEAN
    log.info(f"[STEP 2] Découpage en articles : {src}")

    with open(src, encoding="utf-8") as f:
        text = f.read()

    articles: list[dict] = []
    seen: set[str]       = set()
    idx = 0

    for header, body in _ART_RE.findall(text):
        body = _clean_body(body)
        if len(body) < 50:
            continue
        nm      = re.search(r"Article\s+(premier|Premier|1er|\d+)", header, re.IGNORECASE)
        raw_num = nm.group(1) if nm else "?"
        idx    += 1
        key     = f"{raw_num}|{body[:40]}"
        if key in seen:
            continue
        seen.add(key)
        articles.append({
            "article_ref":     raw_num,
            "article_number":  _parse_art_num(raw_num),
            "article_index":   idx,
            "text":            body,
            "source_file":     "pdf_francais.pdf",
            "source_name":     SOURCE_NAME,
            "source_version":  SOURCE_VERSION,
            "source_law":      SOURCE_LAW,
            "extraction_date": TODAY,
            "text_hash":       hashlib.md5(body.encode()).hexdigest(),
        })

    articles.sort(key=lambda a: (a["article_number"] or 9999, a["article_index"]))

    with open(ARTICLES_JSON, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    lens = [len(a["text"]) for a in articles]
    log.info(
        f"         → {len(articles)} articles "
        f"[min={min(lens)} max={max(lens)} moy={sum(lens)//len(lens)}] "
        f"→ {ARTICLES_JSON}"
    )
    return articles



# ══════════════════════════════════════════════════════════════════════════════
# FILTRES ANTI-HALLUCINATION — références à des codes étrangers
# ══════════════════════════════════════════════════════════════════════════════

_FRENCH_PATTERNS = {
    "code de l'urbanisme", "code de la construction",
    "code de l'environnement", "code rural", "code forestier",
    "code de la voirie", "code général des impôts",
    "r142", "r.162", "r143", "r132", "l. 132", "l.162", "l145",
    "169-1 du", "1423 du", "1643 du", "1458 du", "1726 du",
    "836 du code civil", "837-1", "172-4 du", "1642-1",
    "142-6 du", "132-4 du", "540-1 du", "145-3 du",
    "514-2 du", "513-2 du", "431-1 du", "article r.", "article l. 1",
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2b — PIPELINE HYBRIDE : N-GRAM TF-IDF + RE-RANKING + TOP-K
#
#  Étape A — N-gram TF-IDF (1,3)
#    Vectorise les 468 articles avec unigrammes + bigrammes + trigrammes.
#    K-Means regroupe en n_clusters groupes thématiques.
#    → Résultat : ~30-50 candidats par groupe.
#
#  Étape B — Re-ranking sémantique (all-MiniLM-L6-v2)
#    Encode chaque article en vecteur 384D.
#    Calcule la similarité cosinus par rapport au centroïde du groupe.
#    → Corrige les erreurs de TF-IDF, classe par pertinence de sens.
#
#  Étape C — Sélection top-k
#    Score combiné = 0.4 × score_tfidf + 0.6 × score_sémantique
#    Garde les top_k meilleurs articles par groupe.
#    → Mistral reçoit un contexte concentré → moins d'hallucinations.
#
#  Installation : pip install scikit-learn sentence-transformers
# ══════════════════════════════════════════════════════════════════════════════

def chunk_hybrid_pipeline(
    articles_path: Optional[str] = None,
    n_clusters:    int   = 12,
    top_k:         int   = 6,
    alpha:         float = 0.4,
    model_name:    str   = "all-MiniLM-L6-v2",
    ngram_range:   tuple = (1, 3),
    max_features:  int   = 800,
) -> list[dict]:
    """
    STEP 2b — Pipeline hybride NLP.

    Paramètres :
        n_clusters   : nb de groupes thématiques (12 = thèmes du CDR tunisien)
        top_k        : articles conservés par groupe (4 recommandé)
        alpha        : poids TF-IDF dans le score combiné (0.4)
                       → le sémantique (0.6) prime car le CDR utilise
                         des synonymes variés pour les mêmes droits
        model_name   : modèle sentence-transformers (80 MB, CPU)
        ngram_range  : (1,3) = unigrammes + bigrammes + trigrammes
                       → capture "titre foncier", "servitude de passage"
        max_features : nb de n-grams discriminants retenus (800 optimal
                       pour 468 articles)

    Sortie : data/chunks_hybrid.json
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import normalize
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError as e:
        raise RuntimeError(
            f"Dépendance manquante : {e}\n"
            "  pip install scikit-learn sentence-transformers"
        )

    src = Path(articles_path) if articles_path else ARTICLES_JSON
    log.info("[STEP 2b] Pipeline hybride NLP")
    log.info(f"           ngram_range={ngram_range}  max_features={max_features}"
             f"  n_clusters={n_clusters}  top_k={top_k}  alpha={alpha}")

    with open(src, encoding="utf-8") as f:
        articles = json.load(f)
    log.info(f"           → {len(articles)} articles à traiter")

    texts = [a["text"] for a in articles]

    # ── ÉTAPE A : N-GRAM TF-IDF ──────────────────────────────────────────────
    log.info("           [A] Vectorisation N-gram TF-IDF…")
    vectorizer = TfidfVectorizer(
        ngram_range   = ngram_range,
        max_features  = max_features,
        min_df        = 2,      # ignore les hapax (1 seul article)
        max_df        = 0.85,   # ignore "article", "loi" (trop communs)
        sublinear_tf  = True,   # log(TF) normalise les articles longs
        analyzer      = "word",
        token_pattern = r"(?u)\b[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]{1,}\b",
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    log.info(f"           → Matrice TF-IDF : {tfidf_matrix.shape[0]} × {tfidf_matrix.shape[1]}")

    # Clustering K-Means sur les vecteurs TF-IDF
    n_eff  = min(n_clusters, len(articles))
    kmeans = KMeans(n_clusters=n_eff, random_state=42, n_init=10, max_iter=300)
    labels = kmeans.fit_predict(tfidf_matrix)
    log.info(f"           → {n_eff} clusters créés")

    # Score TF-IDF de chaque article vs centroïde de son cluster
    tfidf_dense  = normalize(tfidf_matrix.toarray(), norm="l2")
    centers_norm = normalize(kmeans.cluster_centers_,  norm="l2")
    tfidf_scores = np.array([
        float(tfidf_dense[i] @ centers_norm[labels[i]])
        for i in range(len(articles))
    ])

    # Termes dominants de chaque cluster (pour les logs)
    feature_names = vectorizer.get_feature_names_out()
    cluster_terms: dict[int, list[str]] = {}
    for cid in range(n_eff):
        top_idx = kmeans.cluster_centers_[cid].argsort()[-6:][::-1]
        cluster_terms[cid] = [feature_names[i] for i in top_idx]

    # Regrouper les indices par cluster
    clusters: dict[int, list[int]] = {}
    for i, cid in enumerate(labels):
        clusters.setdefault(int(cid), []).append(i)

    for cid in sorted(clusters):
        terms = cluster_terms.get(cid, [])
        log.info(f"           Cluster {cid:>2} — {len(clusters[cid]):>3} articles "
                 f"— {', '.join(terms[:3])}")

    # ── ÉTAPE B : RE-RANKING SÉMANTIQUE ──────────────────────────────────────
    log.info(f"           [B] Re-ranking sémantique ({model_name})…")
    log.info("               Chargement modèle (1re fois : téléchargement ~80 MB)…")
    sem_model  = SentenceTransformer(model_name)
    embeddings = sem_model.encode(
        texts,
        batch_size          = 32,
        show_progress_bar   = True,
        convert_to_numpy    = True,
        normalize_embeddings= True,  # L2-normalisé → produit scalaire = cosinus
    )
    log.info(f"               → Embeddings : {embeddings.shape}")

    # ── ÉTAPE C : SCORE COMBINÉ + SÉLECTION TOP-K ────────────────────────────
    log.info(f"           [C] Score combiné + sélection top-{top_k}…")
    chunks: list[dict] = []

    for cid in sorted(clusters):
        indices = clusters[cid]

        # Centroïde sémantique = moyenne L2-normalisée des embeddings du cluster
        cluster_embs = embeddings[indices]          # shape: (n_in_cluster, 384)
        centroid     = cluster_embs.mean(axis=0)
        norm         = np.linalg.norm(centroid)
        centroid     = centroid / (norm + 1e-10)

        # Score sémantique = similarité cosinus avec le centroïde
        sem_scores   = cluster_embs @ centroid      # shape: (n_in_cluster,)

        # Score TF-IDF local
        local_tfidf  = tfidf_scores[indices]

        # Score combiné : alpha × tfidf + (1-alpha) × sémantique
        combined     = alpha * local_tfidf + (1.0 - alpha) * sem_scores

        # Top-k par score combiné décroissant
        sorted_local    = np.argsort(combined)[::-1][:top_k]
        selected_global = [indices[j] for j in sorted_local]

        # Remettre les articles dans l'ordre naturel (numéro d'article)
        selected_arts = [articles[i] for i in selected_global]
        selected_arts.sort(key=lambda a: a.get("article_number") or 9999)

        # Construire le texte fusionné du chunk
        merged_text = "\n\n".join(
            f"--- Article {a['article_ref']} ---\n{a['text']}"
            for a in selected_arts
        )
        first = selected_arts[0]

        chunks.append({
            "article_ref":     (f"{selected_arts[0]['article_ref']}"
                                f"-{selected_arts[-1]['article_ref']}"),
            "article_refs":    [a["article_ref"]    for a in selected_arts],
            "article_numbers": [a["article_number"] for a in selected_arts],
            "article_index":   first["article_index"],
            "text":            merged_text,
            "cluster_id":      cid,
            "cluster_terms":   cluster_terms.get(cid, []),
            "n_articles":      len(selected_arts),
            "top_k":           top_k,
            "alpha":           alpha,
            "chunk_method":    "hybrid_ngram_tfidf_semantic",
            "model_used":      model_name,
            "scores": {
                "tfidf_avg":    round(float(local_tfidf[sorted_local].mean()),  4),
                "semantic_avg": round(float(sem_scores[sorted_local].mean()),   4),
                "combined_avg": round(float(combined[sorted_local].mean()),     4),
            },
            "source_file":     first["source_file"],
            "source_name":     first["source_name"],
            "source_version":  first["source_version"],
            "source_law":      first.get("source_law", ""),
            "extraction_date": TODAY,
            "text_hash":       hashlib.md5(merged_text.encode()).hexdigest(),
        })

    out = DATA_DIR / "chunks_hybrid.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    avg_sc = sum(c["scores"]["combined_avg"] for c in chunks) / len(chunks)
    log.info(f"           → {len(chunks)} chunks  "
             f"({len(articles)} → {len(chunks)} appels LLM)  "
             f"score moy={avg_sc:.3f}")
    log.info(f"           → {out}")
    return chunks


# ══════════════════════════════════════════════════════════════════════════════
# ONTOLOGIE DES CONCEPTS JURIDIQUES — Code des Droits Réels tunisien
# ══════════════════════════════════════════════════════════════════════════════

CDR_CONCEPTS = {
    # Livre 1 : Propriete
    "propriete": [
        "propriétaire", "propriété", "droit exclusif",
        "user jouir", "disposer", "abus de droit",
    ],
    "accession": [
        "accession", "accéder", "incorporation",
        "construction sur terrain", "plantation",
    ],
    "copropriete": [
        "copropriété", "copropriétaire", "parties communes",
        "coindivisaire", "indivision", "quote-part",
    ],
    "mitoyennete": [
        "mitoyen", "mitoyenneté", "mur mitoyen",
        "clôture mitoyenne", "fossé mitoyen", "bornage",
    ],
    # Livre 2 : Droits reels demembres
    "usufruit": [
        "usufruit", "usufruitier", "nu-propriétaire",
        "quasi-usufruit", "extinction usufruit",
    ],
    "usage_habitation": [
        "droit d'usage", "droit d'habitation",
        "usager", "usage personnel",
    ],
    "emphyteose": [
        "emphytéose", "emphytéote",
        "bail emphytéotique", "mise en valeur",
    ],
    "superficie": [
        "superficie", "superficiaire",
        "sol", "tréfonds",
    ],
    "enzel": [
        "enzel", "enzéliste",
        "droit enzel", "canon enzel",
    ],
    "kirdar": [
        "kirdar", "droit kirdar", "canon kirdar",
    ],
    # Livre 3 : Servitudes
    "servitude": [
        "servitude", "passage", "fonds servant", "fonds dominant",
        "servitude naturelle", "servitude légale",
        "écoulement des eaux", "vue",
    ],
    # Livre 4 : Possession
    "possession": [
        "possession", "possesseur", "prescription",
        "usucapion", "bonne foi", "mauvaise foi",
        "prescription acquisitive",
    ],
    # Livre 5 : Suretes reelles
    "hypotheque": [
        "hypothèque", "hypothéquer", "créancier hypothécaire",
        "inscription hypothèque", "radiation hypothèque",
        "purge hypothèque",
    ],
    "gage_nantissement": [
        "gage", "nantissement", "créancier gagiste",
        "remise", "réalisation gage", "vente gage",
    ],
    "privilege": [
        "privilège", "créancier privilégié",
        "priorité paiement", "sûreté",
    ],
    # Livre 6 : Bail
    "bail_location": [
        "louer", "bail", "locataire", "bailleur",
        "preneur", "loyer", "fermage", "location",
    ],
    "sous_location": [
        "sous-louer", "sous-location", "sous-bail",
        "accord bailleur", "autorisation sous-louer",
    ],
    "resiliation_bail": [
        "résilier", "résiliation", "congé",
        "expulsion", "rupture bail", "renouvellement",
    ],
    # Livre 7 : Immatriculation fonciere
    "immatriculation": [
        "immatriculation", "titre foncier", "conservateur foncier",
        "réquisition", "registre foncier", "livre foncier",
    ],
    "morcellement_lotissement": [
        "morcellement", "lotissement", "division parcellaire",
        "parcelle", "permis de lotir",
    ],
    "expropriation": [
        "exproprier", "expropriation", "utilité publique",
        "indemnité", "transfert propriété",
    ],
    # Transactions immobilieres
    "vente": [
        "vendre", "céder", "aliéner", "vente", "cession",
        "acte authentique", "notaire", "acheteur", "vendeur",
    ],
    "construction": [
        "construire", "construction", "édifier", "bâtir",
        "bâtiment", "travaux", "extension", "permis de construire",
    ],
    "demolition": [
        "démolir", "détruire", "démolition",
        "destruction", "raser", "abattre",
    ],
    # Autres droits
    "succession_heritage": [
        "succession", "héritier", "hériter",
        "donation", "legs", "partage succession",
    ],
    "preemption": [
        "préemption", "droit de préférence",
        "retrait", "substitution",
    ],
    "saisie": [
        "saisir", "saisie immobilière", "saisie-exécution",
        "vente forcée", "mise en vente judiciaire",
    ],
    "donation": [
        "donation", "donateur", "donataire",
        "libéralité", "révocation donation",
    ],
}


def chunk_coverage_pipeline(
    articles_path: Optional[str] = None,
    top_k_per_concept: int = 4,
    model_name:        str = "all-MiniLM-L6-v2",
) -> list[dict]:
    """
    STEP 2b ALTERNATIF — Coverage-based sampling.

    Garantit la couverture thématique en sélectionnant explicitement
    les articles pour chaque concept juridique défini dans CDR_CONCEPTS.

    Contrairement à chunk_hybrid_pipeline (K-Means), cette approche
    GARANTIT qu'au moins 1 chunk existe pour chaque concept juridique.

    Paramètres :
        top_k_per_concept : nb d'articles gardés par concept (4 recommandé)
        model_name        : modèle sentence-transformers pour le re-ranking

    Sortie : data/chunks_hybrid.json (format compatible avec extract_rules)
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError as e:
        raise RuntimeError(
            f"Dépendance manquante : {e}\n"
            "  pip install scikit-learn sentence-transformers"
        )

    src = Path(articles_path) if articles_path else ARTICLES_JSON
    log.info("[STEP 2b] Pipeline COVERAGE-BASED")
    log.info(f"           Concepts CDR : {len(CDR_CONCEPTS)}")
    log.info(f"           Top-k par concept : {top_k_per_concept}")

    with open(src, encoding="utf-8") as f:
        articles = json.load(f)
    log.info(f"           → {len(articles)} articles à traiter")

    texts = [a["text"].lower() for a in articles]

    # ── A : Pour chaque concept, trouver les articles pertinents ─────────────
    log.info("           [A] Identification des articles par concept…")
    concept_articles = {}  # {concept: [article_indices]}

    for concept, keywords in CDR_CONCEPTS.items():
        matching = []
        for i, text in enumerate(texts):
            # Compter les occurrences des mots-clés dans l'article
            score = sum(text.count(kw) for kw in keywords)
            if score > 0:
                matching.append((i, score))
        # Trier par score décroissant
        matching.sort(key=lambda x: -x[1])
        concept_articles[concept] = matching
        count = len(matching)
        status = "✅" if count >= top_k_per_concept else (
            "⚠️ " if count > 0 else "❌"
        )
        log.info(f"           {status} {concept:<22} : {count} articles pertinents")

    # ── B : Re-ranking sémantique par concept ────────────────────────────────
    log.info(f"           [B] Re-ranking sémantique ({model_name})…")
    sem_model = SentenceTransformer(model_name)

    # Encoder tous les articles une seule fois
    article_texts = [a["text"] for a in articles]
    log.info(f"               Encodage de {len(article_texts)} articles…")
    embeddings = sem_model.encode(
        article_texts, batch_size=32, show_progress_bar=True,
        convert_to_numpy=True, normalize_embeddings=True,
    )

    # Encoder chaque concept comme une "phrase de requête"
    concept_queries = {
        c: " ".join(kws) for c, kws in CDR_CONCEPTS.items()
    }
    concept_embs = {
        c: sem_model.encode([q], convert_to_numpy=True, normalize_embeddings=True)[0]
        for c, q in concept_queries.items()
    }

    # ── C : Sélection top-k par concept avec score combiné ───────────────────
    log.info(f"           [C] Sélection top-{top_k_per_concept} par concept…")
    chunks = []
    selected_indices = set()  # Pour éviter la duplication

    for concept, matching in concept_articles.items():
        if not matching:
            log.warning(f"           Concept SAUTÉ (aucun article) : {concept}")
            continue

        # Candidats = articles ayant au moins un mot-clé
        candidate_indices = [i for i, _ in matching[:20]]  # top-20 par mots-clés
        candidate_embs    = embeddings[candidate_indices]

        # Score sémantique par rapport à la requête concept
        sim_scores = candidate_embs @ concept_embs[concept]

        # Score lexical normalisé (mots-clés)
        max_lex = max(s for _, s in matching[:20])
        lex_scores = np.array([
            matching[j][1] / max_lex for j in range(min(20, len(matching)))
        ])

        # Score combiné : 40% lexical + 60% sémantique
        combined = 0.4 * lex_scores + 0.6 * sim_scores

        # Top-k
        top_positions = np.argsort(combined)[::-1][:top_k_per_concept]
        selected = [candidate_indices[j] for j in top_positions]

        # Créer le chunk
        selected_arts = [articles[i] for i in selected]
        selected_arts.sort(key=lambda a: a.get("article_number") or 9999)

        merged_text = "\n\n".join(
            f"--- Article {a['article_ref']} ---\n{a['text']}"
            for a in selected_arts
        )
        first = selected_arts[0]

        chunks.append({
            "article_ref":     (f"{selected_arts[0]['article_ref']}"
                                f"-{selected_arts[-1]['article_ref']}"),
            "article_refs":    [a["article_ref"]    for a in selected_arts],
            "article_numbers": [a["article_number"] for a in selected_arts],
            "article_index":   first["article_index"],
            "text":            merged_text,
            "concept":         concept,
            "concept_keywords": CDR_CONCEPTS[concept],
            "n_articles":      len(selected_arts),
            "top_k":           top_k_per_concept,
            "chunk_method":    "coverage_based_ontology",
            "model_used":      model_name,
            "scores": {
                "semantic_avg": round(float(sim_scores[top_positions].mean()), 4),
                "lexical_avg":  round(float(lex_scores[top_positions].mean()), 4),
                "combined_avg": round(float(combined[top_positions].mean()), 4),
            },
            "source_file":     first["source_file"],
            "source_name":     first["source_name"],
            "source_version":  first["source_version"],
            "source_law":      first.get("source_law", ""),
            "extraction_date": TODAY,
            "text_hash":       hashlib.md5(merged_text.encode()).hexdigest(),
        })
        selected_indices.update(selected)

    # ── Sauvegarder au même emplacement que chunk_hybrid_pipeline ────────────
    out = DATA_DIR / "chunks_hybrid.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    # Statistiques
    avg_sc = sum(c["scores"]["combined_avg"] for c in chunks) / max(1, len(chunks))
    coverage = len(chunks) / len(CDR_CONCEPTS) * 100
    log.info(f"           → {len(chunks)} chunks  "
             f"({len(articles)} articles  →  {len(chunks)} appels LLM)")
    log.info(f"           → Articles uniques sélectionnés : {len(selected_indices)}")
    log.info(f"           → Couverture thématique : {coverage:.1f}% "
             f"({len(chunks)}/{len(CDR_CONCEPTS)} concepts)")
    log.info(f"           → Score moyen : {avg_sc:.3f}")
    log.info(f"           → {out}")
    return chunks

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — EXTRACTION RÈGLES PAR LLM
# ══════════════════════════════════════════════════════════════════════════════

def _build_prompt(art: dict) -> str:
    """
    Prompt amélioré v2 — force des actions claires et complètes.
    Corrige le problème des actions vagues ('à l'encontre', 'ne rien faire').
    """
    refs       = ", ".join(str(r) for r in art.get("article_refs", [art["article_ref"]]))
    n_arts     = art.get("n_articles", 1)
    valid_nums = refs
    return f"""Tu es un juriste expert STRICT en droit tunisien des droits réels.

SOURCE : {art["source_name"]} ({art["source_version"]})
LOI    : {art.get("source_law", "Loi n°65-5 du 12 février 1965")}
ARTICLES : {refs}  ({n_arts} article(s))
NUMÉROS VALIDES : {valid_nums}

════════════════════════════════════════════════════════════
RÈGLES STRICTES
════════════════════════════════════════════════════════════
1.  Extraire UNIQUEMENT les règles EXPLICITEMENT dans le texte
2.  INTERDICTION d'inférer ou compléter une règle
3.  INTERDICTION d'utiliser le droit français ou étranger
4.  Aucune règle explicite → retourner : []
5.  "article" = UNIQUEMENT l'un de : {valid_nums}
6.  INTERDIT : code urbanisme, code civil français, RGPD, code pénal
7.  "status" = obligation | permis | interdit  (rien d'autre)
8.  Actions en FRANÇAIS uniquement

════════════════════════════════════════════════════════════
RÈGLE CRITIQUE — FORMAT DE L'ACTION
════════════════════════════════════════════════════════════
Le champ "action" DOIT être un VERBE À L'INFINITIF COMPLET
qui décrit clairement ce que fait l'acteur.

✅ CORRECT — verbes complets et clairs :
   "construire sans autorisation"
   "sous-louer le bien loué"
   "inscrire une hypothèque"
   "démolir un bâtiment"
   "payer le loyer"
   "exercer la possession paisiblement"
   "aliéner le bien hypothéqué"
   "réclamer l'indemnité"

✗ INTERDIT — actions vagues ou fragmentées :
   "à l'encontre"          → trop vague, REFUSER
   "ne rien faire"         → trop vague, REFUSER
   "exercent"              → pas infinitif, REFUSER
   "doit"                  → pas une action, REFUSER
   "est tenu"              → pas infinitif, REFUSER
   "peut"                  → pas une action, REFUSER
   "faire"                 → trop vague, REFUSER

Si l'action ne peut pas être exprimée par un verbe infinitif
clair et complet → NE PAS extraire cette règle.

════════════════════════════════════════════════════════════
EXEMPLES DE BONNES EXTRACTIONS
════════════════════════════════════════════════════════════
Texte : "Le locataire ne peut sous-louer sans accord du bailleur"
→ actor="locataire", action="sous-louer le bien loué",
  target="bien loué", status="interdit",
  conditions=["sans accord écrit du bailleur"]

Texte : "Le propriétaire est tenu d'entretenir son bien"
→ actor="proprietaire", action="entretenir son bien",
  target="bien immobilier", status="obligation", conditions=[]

Texte : "Le créancier peut inscrire l'hypothèque"
→ actor="créancier", action="inscrire l'hypothèque",
  target="registre foncier", status="permis", conditions=[]

════════════════════════════════════════════════════════════
FORMAT JSON STRICT — zéro texte avant ou après
════════════════════════════════════════════════════════════
[
  {{
    "actor":      "acteur juridique du texte",
    "action":     "VERBE INFINITIF COMPLET ET CLAIR",
    "target":     "objet de l'action ou vide",
    "status":     "obligation | permis | interdit",
    "conditions": ["conditions explicites du texte"],
    "article":    "Article N"
  }}
]

════════════════════════════════════════════════════════════
TEXTE — CDR TUNISIEN (Loi n°65-5 / 1965)
════════════════════════════════════════════════════════════
{art["text"]}
"""


def _call_llm(prompt: str) -> str:
    if not _HAS_REQ:
        raise RuntimeError("pip install requests")
    resp = _req.post(
        OLLAMA_URL,
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
              "options": {"temperature": LLM_TEMP, "top_p": 0.3}},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def _parse_json(raw: str) -> list[dict]:
    """
    Parse JSON robuste — gère les cas où Mistral ajoute du texte
    avant ou après le JSON (erreur "Extra data").
    """
    # Nettoyer les blocs markdown
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Stratégie 1 : chercher le tableau JSON le plus complet
    # Trouver toutes les positions de '[' et ']' et essayer chaque combinaison
    for m in re.finditer(r"\[", raw):
        start = m.start()
        # Trouver le ']' correspondant en comptant les brackets
        depth = 0
        for i, c in enumerate(raw[start:], start):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    candidate = raw[start:i+1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, list):
                            return result
                    except json.JSONDecodeError:
                        pass
                    break

    # Stratégie 2 : chercher un objet JSON seul
    for m in re.finditer(r"\{", raw):
        start = m.start()
        depth = 0
        for i, c in enumerate(raw[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[start:i+1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return [result]
                    except json.JSONDecodeError:
                        pass
                    break

    # Stratégie 3 : regex classique en dernier recours
    m = re.search(r"\[.*?\]", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    return []


# Actions vagues à rejeter automatiquement
_VAGUE_ACTIONS = {
    # Fragments de phrases — ne décrivent pas une action complète
    "à l'encontre", "ne rien faire", "exercent", "doit", "est tenu",
    "peut", "agir", "être", "avoir", "effectuer", "procéder",
    "se conformer", "respecter les", "appliquer", "mettre en oeuvre",
    # NB : "faire" seul est vague, mais "faire construire" est valide
    # → le filtre monosyllabe gère les cas intermédiaires
}

def _is_valid_raw(rule: dict) -> bool:
    if not isinstance(rule, dict):
        return False
    if not rule.get("actor") or not rule.get("action"):
        return False
    if rule.get("status", "").lower().strip() not in {"obligation", "permis", "interdit"}:
        return False

    action = rule.get("action", "").strip().lower()

    # Rejeter les actions trop courtes (moins de 3 caractères)
    if len(action) < 3:
        log.warning(f"         ✗ Action trop courte rejetée : '{action}'")
        return False

    # Rejeter les actions vagues connues
    if action in _VAGUE_ACTIONS or action in {v.lower() for v in _VAGUE_ACTIONS}:
        log.warning(f"         ✗ Action vague rejetée : '{action}'")
        return False

    # Rejeter si l'action ne contient pas de verbe substantiel
    # (doit avoir au moins 2 mots OU être un verbe infinitif reconnu)
    mots = action.split()
    verbes_infinitif = {
        # Construction / destruction
        "construire", "démolir", "détruire", "raser", "abattre",
        "rénover", "édifier", "bâtir", "reconstruire",
        # Vente / transfert
        "vendre", "acheter", "céder", "aliéner", "acquérir",
        "transférer", "muter", "exproprier", "immatriculer",
        # Bail / location
        "louer", "sous-louer", "relouer", "résilier", "renouveler",
        # Droits réels
        "hypothéquer", "inscrire", "radier", "saisir", "gager",
        "exercer", "jouir", "user", "disposer", "posséder",
        "revendiquer", "réclamer", "prescrire", "usucaper",
        # Entretien / gestion
        "entretenir", "payer", "percevoir", "exploiter",
        "diviser", "partager", "modifier", "transformer",
        # Extinction / disparition
        "s'éteindre", "expirer", "s'éteindre",
        # Autres
        "dilapider", "aliéner", "morceler", "lotir",
    }
    if len(mots) == 1 and mots[0] not in verbes_infinitif:
        log.warning(f"         ✗ Action monosyllabe vague rejetée : '{action}'")
        return False

    full = " ".join([
        rule.get("actor", ""), rule.get("action", ""),
        rule.get("target", ""), " ".join(rule.get("conditions", [])),
    ]).lower()
    if any(h in full for h in HALLUCINATION_SIGNALS):
        return False
    # Filtre 3 : article cite un code étranger
    art_field = rule.get("article", "").lower()
    if any(p in art_field for p in _FRENCH_PATTERNS):
        log.warning(f"         ✗ Article étranger rejeté : "
                    f"{rule.get('article', '')[:60]}")
        return False

    return any(kw in full for kw in DOMAIN_KW)


def extract_rules(articles_path: Optional[str] = None) -> list[dict]:
    """
    STEP 3 : chunks + LLM → rules_raw.json
    Priorité automatique :
        chunks_hybrid.json   (pipeline hybride NLP)
        chunks_semantic.json (pipeline sémantique seul)
        articles.json        (article par article — mode dégradé)
    """
    hybrid_p   = DATA_DIR / "chunks_hybrid.json"
    semantic_p = DATA_DIR / "chunks_semantic.json"

    if not articles_path and hybrid_p.exists():
        _src = hybrid_p
        log.info(f"[STEP 3] Mode HYBRIDE NLP ({LLM_MODEL}) : {_src}")
    elif not articles_path and semantic_p.exists():
        _src = semantic_p
        log.info(f"[STEP 3] Mode SÉMANTIQUE ({LLM_MODEL}) : {_src}")
    else:
        _src = Path(articles_path) if articles_path else ARTICLES_JSON
        log.info(f"[STEP 3] Mode article/article ({LLM_MODEL}) : {_src}")

    with open(_src, encoding="utf-8") as f:
        arts = json.load(f)
    log.info(f"         → {len(arts)} chunks/articles")

    all_rules, empty = [], 0
    for i, art in enumerate(arts):
        log.info(f"         [{i+1:>3}/{len(arts)}] Art.{art['article_ref']}…")
        extracted = []
        for attempt in range(LLM_RETRIES + 1):
            try:
                parsed = _parse_json(_call_llm(_build_prompt(art)))
                for r in parsed:
                    if _is_valid_raw(r):
                        rl = art.get("article_refs", [art["article_ref"]])
                        nl = art.get("article_numbers", [art.get("article_number")])
                        r.update({
                            "article_ref":     rl[0] if rl else art["article_ref"],
                            "article_number":  nl[0] if nl else art.get("article_number"),
                            "article_index":   art["article_index"],
                            "source_file":     art["source_file"],
                            "source_name":     art["source_name"],
                            "source_version":  art["source_version"],
                            "extraction_date": TODAY,
                            "text_hash":       art["text_hash"],
                            "cluster_id":      art.get("cluster_id", -1),
                            "chunk_method":    art.get("chunk_method", "article"),
                        })
                        extracted.append(r)
                break
            except Exception as e:
                if attempt < LLM_RETRIES:
                    log.warning(f"         retry {attempt+1} ({e})")
                    time.sleep(1)
        if extracted:
            all_rules.extend(extracted)
        else:
            empty += 1
        time.sleep(LLM_SLEEP)

    with open(RULES_RAW, "w", encoding="utf-8") as f:
        json.dump(all_rules, f, ensure_ascii=False, indent=2)
    log.info(f"         → {len(all_rules)} règles | {empty} vides → {RULES_RAW}")
    return all_rules


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — NETTOYAGE + NORMALISATION
# ══════════════════════════════════════════════════════════════════════════════

_STATUS_NORM = {
    "obligation": "obligation", "obligatoire": "obligation",
    "interdit":   "interdit",   "interdite":   "interdit",
    "permis":     "permis",     "autorisé":    "permis",
    "peut":       "permis",
}

_ACTION_FUSIONS = {
    "construire une maison":             "construire",
    "construire une habitation":         "construire",
    "construire un bâtiment":            "construire",
    "faire des travaux":                 "effectuer des travaux",
    "faire des travaux sur un immeuble": "effectuer des travaux",
    "possession":                        "exercer la possession",
    "possession et utilisation":         "exercer la possession",
    "acquérir des biens immobiliers":    "acquérir un bien immobilier",
    "acheter des biens immobiliers":     "acquérir un bien immobilier",
    "vendre des biens immobiliers":      "vendre un bien immobilier",
}


def _norm_actor(raw: str) -> str:
    k = raw.strip().lower()
    if k in ACTOR_MAP:
        return ACTOR_MAP[k]
    for pat, cat in ACTOR_MAP.items():
        if pat in k:
            return cat
    return k


def _norm_status(raw: str) -> str:
    k = raw.strip().lower()
    for pat, v in _STATUS_NORM.items():
        if pat in k:
            return v
    return ""


def _norm_action(raw: str) -> str:
    a = re.sub(
        r"^(doit|doivent|est interdit de|peuvent|peut|"
        r"a l'obligation de|il est interdit de)\s+",
        "", raw.strip().lower(),
    )
    return _ACTION_FUSIONS.get(a, a)


def _norm_target(raw: str) -> str:
    t = raw.strip()
    return "" if t.lower() in {"aucun", "aucune", "n/a", "", "none", "-", "null"} else t


def _norm_conds(conds: list) -> list[str]:
    seen, out = set(), []
    for c in conds:
        if not isinstance(c, str) or len(c.strip()) < 5:
            continue
        k = c.strip().lower()
        if k not in seen:
            seen.add(k)
            out.append(c.strip())
    return out


def _quality_score(rule: dict) -> int:
    s = 0
    s += 2 if rule.get("actor") in KNOWN_ACTORS else (1 if rule.get("actor") else 0)
    nw = len(rule.get("action", "").split())
    s += 2 if nw >= 3 else (1 if nw >= 1 else 0)
    s += 2 if rule.get("status") in {"obligation", "permis", "interdit"} else 0
    s += 1 if rule.get("target") else 0
    s += 1 if rule.get("conditions") else 0
    s += 1 if rule.get("article") else 0
    return s


def clean_rules(raw_path: Optional[str] = None) -> list[dict]:
    """
    STEP 4 : rules_raw.json → rules_clean.json
    - normalise acteur / action / status / target / conditions
    - filtre bruit + hors domaine
    - déduplique par hash MD5
    - ajoute quality_score, priority, actor_standard
    - risk_score = 0 (calculé en STEP 6)
    """
    src = Path(raw_path) if raw_path else RULES_RAW
    log.info(f"[STEP 4] Nettoyage : {src}")

    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    log.info(f"         → {len(data)} règles brutes")

    cleaned: list[dict] = []
    seen: set[str]      = set()
    stats               = Counter()

    for rule in data:
        actor      = _norm_actor(rule.get("actor", ""))
        action     = _norm_action(rule.get("action", ""))
        target     = _norm_target(rule.get("target", ""))
        status     = _norm_status(rule.get("status", ""))
        article    = rule.get("article", "").strip().lower()
        conditions = _norm_conds(rule.get("conditions", []))

        if not status:
            stats["status_invalide"] += 1; continue
        if not actor or not action:
            stats["champs_vides"] += 1; continue

        bag = " ".join([actor, action, target,
                        " ".join(conditions), article]).lower()

        if any(n in bag for n in NOISE_KW):
            stats["bruit"] += 1; continue
        if not any(kw in bag for kw in DOMAIN_KW):
            stats["hors_domaine"] += 1; continue

        # Double filtre : articles codes étrangers résiduels
        if any(p in article for p in _FRENCH_PATTERNS):
            stats["article_etranger"] += 1; continue

        key = hashlib.md5(f"{actor}|{action}|{target}|{status}".encode()).hexdigest()
        if key in seen:
            stats["doublon"] += 1; continue
        seen.add(key)

        tmp = dict(actor=actor, action=action, target=target,
                   status=status, conditions=conditions, article=article)
        qs  = _quality_score(tmp)

        cleaned.append({
            "actor":           actor,
            "action":          action,
            "target":          target,
            "status":          status,
            "conditions":      conditions,
            "article":         article,
            "quality_score":   qs,
            "priority":        "high" if qs >= 8 else "medium" if qs >= 5 else "low",
            "low_quality":     qs < 5,
            "actor_standard":  actor in KNOWN_ACTORS,
            "source_file":     rule.get("source_file",    "pdf_francais.pdf"),
            "source_name":     rule.get("source_name",    SOURCE_NAME),
            "source_version":  rule.get("source_version", SOURCE_VERSION),
            "article_ref":     rule.get("article_ref", ""),
            "article_number":  rule.get("article_number"),
            "article_index":   rule.get("article_index"),
            "extraction_date": rule.get("extraction_date", TODAY),
            "text_hash":       rule.get("text_hash", ""),
            "cleaning_date":   TODAY,
            "rule_hash":       key,
            "risk_score":      0,
        })
        stats["accepté"] += 1

    cleaned.sort(key=lambda r: (r.get("article_number") or 9999,
                                r.get("article_index")  or 9999))

    with open(RULES_CLEAN, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    log.info(f"         → {stats['accepté']} règles finales")
    for k, v in stats.items():
        if v:
            log.info(f"           {k}: {v}")
    log.info(f"         → {RULES_CLEAN}")
    return cleaned


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — KNOWLEDGE GRAPH NEO4J (DS01)
# ══════════════════════════════════════════════════════════════════════════════

_REL = {"obligation": "MUST", "permis": "CAN", "interdit": "CANNOT"}


def _mid(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()[:12]


def _esc(s: str) -> str:
    return s.replace("'", "\\'").replace('"', '\\"')


def build_graph(clean_path: Optional[str] = None) -> dict:
    """
    STEP 5 / DS01 : rules_clean.json → Knowledge Graph
    Nœuds    : Actor, Action, Target, Condition, Article
    Relations: MUST, CAN, CANNOT, HAS_TARGET, REQUIRES, CITED_IN
    Exports  : 6 CSV + graph_import.cypher + graph_report.json
    """
    src = Path(clean_path) if clean_path else RULES_CLEAN
    log.info(f"[STEP 5 / DS01] Knowledge Graph : {src}")

    with open(src, encoding="utf-8") as f:
        rules = json.load(f)

    actors, actions, targets, conditions, articles = {}, {}, {}, {}, {}
    rels: list[dict] = []

    for rule in rules:
        aid   = _mid(rule["actor"])
        actid = _mid(rule["action"])
        tid   = _mid(rule["target"]) if rule.get("target") else None
        artid = _mid(rule.get("article", ""))

        actors.setdefault(aid, {
            "id": aid, "name": rule["actor"],
            "is_standard": rule.get("actor_standard", False),
        })
        verb = rule["action"].split()[0] if rule["action"].split() else rule["action"]
        actions.setdefault(actid, {"id": actid, "name": rule["action"], "verb": verb})
        if tid:
            targets.setdefault(tid, {"id": tid, "name": rule["target"]})
        art_ref = rule.get("article", "")
        articles.setdefault(artid, {
            "id": artid, "reference": art_ref,
            "article_number": rule.get("article_number"),
            "source_name": rule.get("source_name", ""),
            "source_version": rule.get("source_version", ""),
        })
        cids = []
        for c in rule.get("conditions", []):
            cid = _mid(c)
            conditions.setdefault(cid, {"id": cid, "text": c})
            cids.append(cid)

        rels.append({
            "actor_id":        aid,
            "action_id":       actid,
            "target_id":       tid or "",
            "article_id":      artid,
            "condition_ids":   "|".join(cids),
            "relation":        _REL.get(rule["status"], "UNKNOWN"),
            "status":          rule["status"],
            "article_ref":     art_ref,
            "quality_score":   rule.get("quality_score", 0),
            "risk_score":      rule.get("risk_score", 0),
            "priority":        rule.get("priority", "medium"),
            "source_version":  rule.get("source_version", ""),
            "extraction_date": rule.get("extraction_date", ""),
            "cleaning_date":   rule.get("cleaning_date", ""),
        })

    # CSV
    NEO4J_DIR.mkdir(exist_ok=True)
    def _wcsv(rows, path, fields):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)

    _wcsv(list(actors.values()),     NEO4J_DIR / "actors.csv",
          ["id", "name", "is_standard"])
    _wcsv(list(actions.values()),    NEO4J_DIR / "actions.csv",
          ["id", "name", "verb"])
    _wcsv(list(targets.values()),    NEO4J_DIR / "targets.csv",
          ["id", "name"])
    _wcsv(list(conditions.values()), NEO4J_DIR / "conditions.csv",
          ["id", "text"])
    _wcsv(list(articles.values()),   NEO4J_DIR / "articles.csv",
          ["id", "reference", "article_number", "source_name", "source_version"])
    _wcsv(rels, NEO4J_DIR / "relationships.csv", [
        "actor_id", "action_id", "target_id", "article_id", "condition_ids",
        "relation", "status", "article_ref", "quality_score", "risk_score",
        "priority", "source_version", "extraction_date", "cleaning_date",
    ])

    # Cypher
    _write_cypher(actors, actions, targets, conditions, articles, rels)

    # Rapport
    cnt = Counter(r["relation"] for r in rels)
    summary = {
        "build_date":    str(date.today()),
        "source":        SOURCE_NAME,
        "input_rules":   len(rules),
        "nodes": {
            "Actor":     len(actors),   "Action":    len(actions),
            "Target":    len(targets),  "Condition": len(conditions),
            "Article":   len(articles),
            "total":     len(actors)+len(actions)+len(targets)+len(conditions)+len(articles),
        },
        "relationships": {
            "total":  len(rels),
            "MUST":   cnt.get("MUST",   0),
            "CAN":    cnt.get("CAN",    0),
            "CANNOT": cnt.get("CANNOT", 0),
        },
    }
    with open(NEO4J_DIR / "graph_report.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info(
        f"         → {summary['nodes']['total']} nœuds | {len(rels)} relations "
        f"(MUST={cnt.get('MUST',0)} CAN={cnt.get('CAN',0)} CANNOT={cnt.get('CANNOT',0)}) "
        f"→ {NEO4J_DIR}/"
    )
    return summary


def _write_cypher(actors, actions, targets, conditions, articles, rels):
    lines = [
        f"// Knowledge Graph — {SOURCE_NAME} {SOURCE_VERSION} | {date.today()}",
        "",
        "// ── Contraintes (exécuter UNE SEULE FOIS) ──",
        "CREATE CONSTRAINT actor_id   IF NOT EXISTS FOR (n:Actor)     REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT action_id  IF NOT EXISTS FOR (n:Action)    REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT target_id  IF NOT EXISTS FOR (n:Target)    REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT cond_id    IF NOT EXISTS FOR (n:Condition) REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article)   REQUIRE n.id IS UNIQUE;",
        "",
        "// ── Index ──",
        "CREATE INDEX actor_name  IF NOT EXISTS FOR (n:Actor)   ON (n.name);",
        "CREATE INDEX action_verb IF NOT EXISTS FOR (n:Action)  ON (n.verb);",
        "",
        "// ── Nœuds ──",
    ]
    for n in actors.values():
        lines.append(
            f"MERGE (:Actor {{id:'{n['id']}',name:'{_esc(n['name'])}',is_standard:{str(n['is_standard']).lower()}}});"
        )
    for n in actions.values():
        lines.append(
            f"MERGE (:Action {{id:'{n['id']}',name:'{_esc(n['name'])}',verb:'{_esc(n['verb'])}'}});"
        )
    for n in targets.values():
        lines.append(f"MERGE (:Target {{id:'{n['id']}',name:'{_esc(n['name'])}'}});")
    for n in conditions.values():
        lines.append(f"MERGE (:Condition {{id:'{n['id']}',text:'{_esc(n['text'])}'}});")
    for n in articles.values():
        num = n["article_number"] if n["article_number"] else "null"
        lines.append(
            f"MERGE (:Article {{id:'{n['id']}',reference:'{_esc(n['reference'])}',article_number:{num},source:'{_esc(n['source_name'])}'}});"
        )
    lines += ["", "// ── Relations MUST/CAN/CANNOT ──"]
    for r in rels:
        props = (
            f"article:'{_esc(r['article_ref'])}',status:'{r['status']}',"
            f"quality_score:{r['quality_score']},risk_score:{r['risk_score']},"
            f"priority:'{r['priority']}',source_version:'{r['source_version']}',"
            f"extraction_date:'{r['extraction_date']}',cleaning_date:'{r['cleaning_date']}'"
        )
        lines.append(
            f"MATCH (a:Actor{{id:'{r['actor_id']}'}}),(act:Action{{id:'{r['action_id']}'}}) "
            f"MERGE (a)-[:{r['relation']} {{{props}}}]->(act);"
        )
    lines += ["", "// ── HAS_TARGET ──"]
    for r in rels:
        if r["target_id"]:
            lines.append(
                f"MATCH (act:Action{{id:'{r['action_id']}'}}),(t:Target{{id:'{r['target_id']}'}}) "
                f"MERGE (act)-[:HAS_TARGET]->(t);"
            )
    lines += ["", "// ── REQUIRES (conditions) ──"]
    for r in rels:
        for cid in r["condition_ids"].split("|"):
            if cid:
                lines.append(
                    f"MATCH (act:Action{{id:'{r['action_id']}'}}),(c:Condition{{id:'{cid}'}}) "
                    f"MERGE (act)-[:REQUIRES]->(c);"
                )
    lines += ["", "// ── CITED_IN ──"]
    for r in rels:
        lines.append(
            f"MATCH (art:Article{{id:'{r['article_id']}'}}),(act:Action{{id:'{r['action_id']}'}}) "
            f"MERGE (art)-[:CITED_IN]->(act);"
        )
    lines += [
        "",
        "// ── Requêtes utiles ──",
        "// MATCH (a:Actor{name:'proprietaire'})-[r:MUST]->(act) RETURN a,r,act",
        "// MATCH (a:Actor)-[r:CANNOT]->(act) RETURN a.name,act.name,r.risk_score ORDER BY r.risk_score DESC",
        "// MATCH (a:Actor)-[r]->(act:Action)-[:HAS_TARGET]->(t) RETURN a.name,type(r),act.name,t.name LIMIT 30",
    ]
    with open(NEO4J_DIR / "graph_import.cypher", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — RISK SCORE DS03
# ══════════════════════════════════════════════════════════════════════════════

def compute_risk_scores(clean_path: Optional[str] = None) -> list[dict]:
    """
    STEP 6 / DS03 : calcule risk_score /100 pour chaque règle.

    Formule :
      score = (STATUS_BASE × ACTOR_WEIGHT) + verb_bonus − cond_malus + quality_bonus
      → clamped [0, 100], trié par risk_score décroissant.
    """
    src = Path(clean_path) if clean_path else RULES_CLEAN
    log.info(f"[STEP 6 / DS03] Risk Scoring : {src}")

    with open(src, encoding="utf-8") as f:
        rules = json.load(f)

    for rule in rules:
        base   = STATUS_BASE.get(rule.get("status", ""), 0)
        weight = ACTOR_WEIGHT.get(rule.get("actor", ""), 1.0)
        action = rule.get("action", "").lower()
        conds  = rule.get("conditions", [])
        qs     = rule.get("quality_score", 5)

        verb_bonus  = 10 if any(v in action for v in HIGH_RISK_VERBS) else 0
        cond_malus  = min(15, len(conds) * 3)
        qual_bonus  = round((qs / 10) * 10)

        raw = (base * weight) + verb_bonus - cond_malus + qual_bonus
        rule["risk_score"] = min(100, max(0, round(raw)))

    rules.sort(key=lambda r: -r["risk_score"])

    with open(src, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    scores = [r["risk_score"] for r in rules]
    high   = sum(1 for s in scores if s >= 70)
    log.info(
        f"         → min={min(scores)} moy={sum(scores)//len(scores)} "
        f"max={max(scores)} | risque élevé (≥70): {high}/{len(rules)}"
    )
    return rules