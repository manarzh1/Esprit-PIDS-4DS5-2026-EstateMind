# 🏠 Estate Mind BO6 — Orchestrateur

Plateforme Immobilière Intelligente Tunisienne — Agent Orchestrateur (BO6)

## Architecture
- **BO6** orchestre uniquement — ne lit PAS PostgreSQL (sauf tables de traçabilité)
- Communication avec **BO1-BO5** uniquement via HTTP JSON
- Pipeline NLP **8 étapes** : langue → darija → traduction → NB → routage → agent → template → sauvegarde
- **Aucun LLM** — Naïve Bayes from scratch + templates

## Tables PostgreSQL BO6 (uniquement)
- `chat_sessions` — sessions utilisateur
- `chat_interactions` — historique complet (DSO3)
- `report_records` — rapports PDF (DSO2)

## Installation rapide

```bash
pip install -r requirements.txt
python scripts/train_classifier.py
python start_all.py
```

## Lancement manuel

```bash
# Terminal 1-5 : Mock agents
uvicorn mock_agents.mock_bo1:app --port 8001
uvicorn mock_agents.mock_bo2:app --port 8002
uvicorn mock_agents.mock_bo3:app --port 8003
uvicorn mock_agents.mock_bo4:app --port 8004
uvicorn mock_agents.mock_bo5:app --port 8005

# Terminal 6 : BO6
uvicorn main:app --port 8000 --reload

# Terminal 7 : Dashboard
python app/dashboard/metrics_dashboard.py
```

## URLs
- API Docs : http://localhost:8000/docs
- Health   : http://localhost:8000/api/v1/health
- Chat     : POST http://localhost:8000/api/v1/chat
- Dashboard: http://localhost:8050
- Frontend : ouvrir frontend/index.html

## Base PostgreSQL
```bash
psql -U postgres -d estate_mind -f migrations/001_schema.sql
```

## Connexion LAN (agents sur machines différentes)
Modifier `.env` :
```
AGENT_BO3_URL=http://192.168.1.43:8003
```

## Test rapide
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "quel est le prix d un S+2 a Ariana ?"}'
```
