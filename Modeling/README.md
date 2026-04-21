# Estate Mind — PropTech Tunisienne

Plateforme d'analyse du marché immobilier tunisien — architecture multi-agents IA.

## Lancement rapide

```bash
# Terminal 1 — Backend
cd Modeling
source venv/Scripts/activate
uvicorn main_api:app --reload --port 8000

# Terminal 2 — Frontend
cd estate-mind-frontend/frontend
npm run dev
```

## Architecture

| BO | Agent | Statut |
|---|---|---|
| BO1 — Market Reliability | CollectorAgent | ✅ Complet |
| BO2 — Territorial Dynamics | TerritorialAgent | ✅ Complet |
| BO3 — Price Estimation | PricingAgent | 🔄 En cours |
| BO4 — Investment Support | PricingAgent | 🔄 En cours |
| BO5 — Legal Compliance | LegalAgent | ✅ Complet |
| BO6 — Platform Operation | LangGraph Orchestrator | ✅ Complet |

## Stack

Backend : FastAPI · LangChain · LangGraph · OpenAI · PostgreSQL · MLflow
Frontend : Next.js 14 · TypeScript · Recharts · Leaflet

## Variables .env

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:pass@host:5432/estate_mind
LLM_TEMPERATURE=0.0
NLP_TEMPERATURE=0.0
NLP_BATCH_SIZE=20
MAX_PAGES_PER_SOURCE=10
PIPELINE_SCHEDULE_HOURS=6
TRUST_SCORE_THRESHOLD=0.50
```

## Commandes utiles

```bash
# Pipeline complet
python agents/collector_agent.py pipeline

# Évaluation NLP (ground truth 60 annonces annotées)
python tools/nlp_evaluator.py

# MLflow UI
mlflow ui --backend-store-uri sqlite:///mlflow.db

# Pipeline automatique toutes les 6h
python agents/collector_agent.py schedule 6
```

## Routes API principales

GET  /api/dashboard                    — métriques dashboard
GET  /api/market                       — stats marché
GET  /api/recommendations              — recommandations personnalisées
GET  /api/territorial/summary          — analyse territoriale complète
GET  /api/territorial/alerts           — zones émergentes + recommandations
GET  /api/territorial/time-series      — séries temporelles
GET  /api/territorial/spatial          — heatmap + stats géographiques
POST /api/analyze                      — analyse d'une annonce

## Limites méthodologiques

Voir `docs/methodology.md` pour la calibration complète des seuils et les limites.
