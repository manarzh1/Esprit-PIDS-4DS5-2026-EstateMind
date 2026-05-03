#!/bin/bash
# ══════════════════════════════════════════════════════
#  IMMO TUNISIA — Lancement local (Mac/Linux)
# ══════════════════════════════════════════════════════

cd "$(dirname "$0")"

echo ""
echo " ╔═══════════════════════════════════════╗"
echo " ║   IMMO TUNISIA — Démarrage serveur   ║"
echo " ╚═══════════════════════════════════════╝"
echo ""

echo "[1/2] Installation des dépendances..."
pip install -r requirements.txt -q

echo ""
echo "[2/2] Démarrage du serveur FastAPI..."
echo ""
echo " → API:   http://localhost:8000"
echo " → Docs:  http://localhost:8000/docs"
echo " → App:   http://localhost:8000"
echo ""
echo " Ctrl+C pour arrêter"
echo ""

uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
