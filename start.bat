@echo off
REM ══════════════════════════════════════════════════════
REM  IMMO TUNISIA — Lancement local (Windows)
REM  Double-cliquez sur ce fichier pour démarrer
REM ══════════════════════════════════════════════════════

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   IMMO TUNISIA — Démarrage serveur   ║
echo  ╚═══════════════════════════════════════╝
echo.

REM Aller dans le dossier du projet
cd /d "%~dp0"

REM Installer les dépendances si besoin
echo [1/2] Vérification des dépendances...
pip install -r requirements.txt -q

echo.
echo [2/2] Démarrage du serveur FastAPI...
echo.
echo  → API:      http://localhost:8000
echo  → Docs:     http://localhost:8000/docs
echo  → App:      http://localhost:8000
echo.
echo  Appuyez sur Ctrl+C pour arrêter
echo.

REM Lancer avec rechargement automatique en dev
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

pause
