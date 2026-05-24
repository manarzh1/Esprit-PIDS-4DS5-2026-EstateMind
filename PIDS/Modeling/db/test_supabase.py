"""
Estate Mind — Test de connexion Supabase
════════════════════════════════════════
Lance ce script pour vérifier que tout fonctionne.

Usage :
    cd Modeling
    python db/test_supabase.py

Ce qu'il vérifie :
  1. DATABASE_URL présent dans .env
  2. Connexion PostgreSQL réussie
  3. Création des tables (idempotent)
  4. Insert d'une ligne de test
  5. Lecture de la ligne de test
  6. Nettoyage (supprime la ligne de test)
"""
import os
import sys
from pathlib import Path

# Ajoute le dossier parent au path pour importer les modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("ESTATE MIND — Test connexion Supabase")
print("=" * 60)

# ── 1. Vérifier DATABASE_URL ──────────────────────────────────────
print("\n[1] Vérification DATABASE_URL...")
db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("  ❌ DATABASE_URL manquant dans votre .env")
    print("  → Allez dans Supabase : Settings → Database → Connection string (URI mode)")
    print("  → Ajoutez DATABASE_URL=postgresql://postgres:[PASS]@db.xxx.supabase.co:5432/postgres")
    sys.exit(1)

# Masque le mot de passe pour l'affichage
masked = db_url.split("@")
host = masked[1] if len(masked) > 1 else "???"
print(f"  ✅ DATABASE_URL trouvé → host: {host[:40]}")

# ── 2. Connexion PostgreSQL ──────────────────────────────────────
print("\n[2] Test de connexion PostgreSQL...")
try:
    import psycopg2
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"  ✅ Connecté — PostgreSQL {version[:40]}")
    conn.close()
except ImportError:
    print("  ❌ psycopg2 non installé")
    print("  → Installez-le : pip install psycopg2-binary --break-system-packages")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ Connexion échouée : {e}")
    print("  → Vérifiez que DATABASE_URL est correct")
    print("  → Vérifiez que l'IP n'est pas bloquée par Supabase (Settings → Network)")
    sys.exit(1)

# ── 3. Créer les tables ───────────────────────────────────────────
print("\n[3] Création / vérification des tables...")
try:
    from db.supabase_manager import get_db
    db = get_db()
    db.ensure_tables()
    print("  ✅ Tables créées / vérifiées")
except Exception as e:
    print(f"  ❌ Erreur tables : {e}")
    print("  → Essayez de copier supabase_schema.sql dans Supabase → SQL Editor")
    sys.exit(1)

# ── 4. Test INSERT ───────────────────────────────────────────────
print("\n[4] Test d'insertion...")
try:
    import pandas as pd
    test_df = pd.DataFrame([{
        "url":           "https://test.estate-mind.tn/test-connexion-123",
        "source":        "test",
        "title":         "Annonce de test — à ignorer",
        "price":         100000.0,
        "surface":       80.0,
        "city":          "Tunis",
        "governorate":   "Tunis",
        "trust_score":   0.99,
        "trust_level":   "Fiable",
        "property_type": "appartement",
    }])
    stats = db.upsert_listings(test_df, pipeline_version="test")
    print(f"  ✅ Insert OK — {stats}")
except Exception as e:
    print(f"  ❌ Insert échoué : {e}")
    sys.exit(1)

# ── 5. Test SELECT ───────────────────────────────────────────────
print("\n[5] Test de lecture...")
try:
    df = db.load_listings(city="Tunis", limit=5)
    if df is not None and not df.empty:
        print(f"  ✅ Lecture OK — {len(df)} lignes chargées depuis Supabase")
        print(f"     Colonnes : {list(df.columns[:5])}...")
    else:
        print("  ⚠️  Table vide — normal si c'est la première connexion")
except Exception as e:
    print(f"  ❌ Lecture échouée : {e}")
    sys.exit(1)

# ── 6. Nettoyage de la ligne de test ─────────────────────────────
print("\n[6] Nettoyage de la ligne de test...")
try:
    import psycopg2
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM listings WHERE url = %s AND source = %s",
        ("https://test.estate-mind.tn/test-connexion-123", "test")
    )
    conn.commit()
    conn.close()
    print("  ✅ Ligne de test supprimée")
except Exception as e:
    print(f"  ⚠️  Nettoyage échoué (non critique) : {e}")

# ── Résumé ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("✅ TOUT EST OK — Supabase est correctement configuré !")
print("=" * 60)
print("\nProchaines étapes :")
print("  1. Lancez le pipeline pour peupler la base :")
print("     python agents/collector_agent.py pipeline")
print("  2. Démarrez le backend :")
print("     uvicorn main_api:app --reload --port 8000")
print("  3. Vérifiez dans Supabase → Table Editor → listings")
