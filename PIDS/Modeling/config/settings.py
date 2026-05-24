"""
Estate Mind — Configuration centralisée v2
══════════════════════════════════════════
Tous les hyperparamètres sont ici. Jamais hardcodés dans le code.
Chargés depuis .env (jamais commités).

Hyperparamètres LLM :
  LLM_TEMPERATURE      → déterminisme du modèle (0 = exact, 1 = créatif)
  NLP_TEMPERATURE      → température spécifique au nettoyage NLP (plus bas = plus précis)
  LLM_MAX_TOKENS       → budget tokens par appel
  NLP_BATCH_SIZE       → annonces traitées par lot par le NLP cleaner

Hyperparamètres pipeline :
  TRUST_SCORE_THRESHOLD → seuil pour qualifier une annonce de "suspecte"
  PRICE_OUTLIER_FACTOR  → multiplicateur IQR pour la détection d'outliers
  DEDUP_THRESHOLD       → similarité minimale pour considérer deux annonces comme doublons
  MAX_PAGES_PER_SOURCE  → pages scrapées par source à chaque run

Hyperparamètres RAG (legal) :
  RAG_CHUNK_SIZE     → taille des chunks de texte juridique (tokens)
  RAG_CHUNK_OVERLAP  → chevauchement entre chunks
  RAG_TOP_K          → nombre de documents retournés par recherche
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
RAW_DIR    = DATA_DIR / "raw"
PROC_DIR   = DATA_DIR / "processed"
LEGAL_DIR  = DATA_DIR / "legal"
MODELS_DIR = BASE_DIR / "models"

# ─── LLM — hyperparamètres exposés ───────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBED_MODEL    = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# Température principale de l'orchestrateur
# 0.0 = déterministe (routing, analyse), 0.2 = légère variabilité (synthèse)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Température du NLP Cleaner — doit rester très bas pour l'extraction structurée
# 0.0 = extraction JSON reproductible, ne jamais dépasser 0.3
NLP_TEMPERATURE = float(os.getenv("NLP_TEMPERATURE", "0.0"))

# Budget tokens par appel LLM
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))

# Taille de lot pour le nettoyage NLP (évite les timeouts sur gros datasets)
NLP_BATCH_SIZE = int(os.getenv("NLP_BATCH_SIZE", "20"))

# ─── PostgreSQL (Cloud : Supabase / Neon / Railway) ───────────────────────────
# Mettre DATABASE_URL en priorité (format cloud), sinon construction manuelle
DATABASE_URL = os.getenv("DATABASE_URL", "")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB   = os.getenv("PG_DB",   "estate_mind")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS", "postgres")

# Préfère DATABASE_URL cloud si disponible
PG_URL = DATABASE_URL or f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# ─── Neo4j ────────────────────────────────────────────────────────────────────
NEO4J_URI  = os.getenv("NEO4J_URI",  "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "password")

# ─── Vector store ─────────────────────────────────────────────────────────────
VECTOR_STORE_PATH = str(DATA_DIR / "vector_store")
VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "faiss")

# Hyperparamètres RAG
RAG_CHUNK_SIZE    = int(os.getenv("RAG_CHUNK_SIZE",    "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
RAG_TOP_K         = int(os.getenv("RAG_TOP_K",         "4"))

# ─── Données ──────────────────────────────────────────────────────────────────
RAW_CSV_PATH = str(RAW_DIR / "annonces_combined.csv")

# ─── Hyperparamètres pipeline ─────────────────────────────────────────────────
# Seuil en dessous duquel une annonce est marquée "Suspecte"
TRUST_SCORE_THRESHOLD = float(os.getenv("TRUST_SCORE_THRESHOLD", "0.50"))

# Facteur IQR pour la détection d'outliers de prix (plus bas = plus strict)
PRICE_OUTLIER_FACTOR  = float(os.getenv("PRICE_OUTLIER_FACTOR",  "3.0"))

# Seuil de similarité pour la déduplication cross-sources [0-1]
DEDUP_THRESHOLD       = float(os.getenv("DEDUP_THRESHOLD",       "0.95"))

# Pages max par source à chaque run automatique
MAX_PAGES_PER_SOURCE  = int(os.getenv("MAX_PAGES_PER_SOURCE",    "10"))

# Intervalle d'automatisation en heures (0 = désactivé)
PIPELINE_SCHEDULE_HOURS = int(os.getenv("PIPELINE_SCHEDULE_HOURS", "6"))

# Limites de validation des données
MIN_SURFACE = float(os.getenv("MIN_SURFACE",   "5"))
MAX_SURFACE = float(os.getenv("MAX_SURFACE",   "5000"))
MIN_PRICE   = float(os.getenv("MIN_PRICE",     "1000"))
MAX_PRICE   = float(os.getenv("MAX_PRICE",     "10000000"))

# ─── MLflow ───────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MLFLOW_EXPERIMENT   = os.getenv("MLFLOW_EXPERIMENT",   "estate_mind_pipeline")

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─── Récapitulatif des hyperparamètres (pour logging) ────────────────────────
def get_hyperparams_dict() -> dict:
    """
    Retourne tous les hyperparamètres sous forme de dict.
    Utilisé par MLflow pour logger les paramètres de chaque run.
    """
    return {
        # LLM
        "llm_model":             LLM_MODEL,
        "llm_temperature":       LLM_TEMPERATURE,
        "nlp_temperature":       NLP_TEMPERATURE,
        "llm_max_tokens":        LLM_MAX_TOKENS,
        "nlp_batch_size":        NLP_BATCH_SIZE,
        # Pipeline
        "trust_score_threshold": TRUST_SCORE_THRESHOLD,
        "price_outlier_factor":  PRICE_OUTLIER_FACTOR,
        "dedup_threshold":       DEDUP_THRESHOLD,
        "max_pages_per_source":  MAX_PAGES_PER_SOURCE,
        # RAG
        "rag_chunk_size":        RAG_CHUNK_SIZE,
        "rag_chunk_overlap":     RAG_CHUNK_OVERLAP,
        "rag_top_k":             RAG_TOP_K,
        # Données
        "min_surface":           MIN_SURFACE,
        "max_surface":           MAX_SURFACE,
        "min_price":             MIN_PRICE,
        "max_price":             MAX_PRICE,
    }
