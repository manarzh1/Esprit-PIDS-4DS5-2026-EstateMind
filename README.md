# BO5 — Legal & Compliance Agent

> **Estate Mind · Group 5 · 4 DS 5**  
> Juriste IA pour le marché immobilier tunisien

---

## Prérequis

- Python 3.10+
- [Ollama](https://ollama.com/) installé et lancé
- Mistral 7B téléchargé

```bash
ollama pull mistral
```

---

## Installation

```bash
# 1. Créer l'environnement virtuel
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# 2. Installer les dépendances
pip install -r requirements.txt
```

---

## Lancer le système

**Terminal 1 — API :**
```bash
python main.py --step api
```

**Terminal 2 — Interface :**
```bash
python -m http.server 3000
```

**Navigateur :**
```
http://localhost:3000/Tunistate_ui.html
```

---

## Sources juridiques

| Code | Référence | Articles |
|------|-----------|---------|
| CDR | Loi n°65-5 du 12 février 1965 | 485 articles |
| CATU | Code de l'Aménagement du Territoire — 2011 | 317 articles indexés |

---

## Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/analyze-text` | Analyse NLP + conformité + RAG |
| POST | `/legal-risk` | Score de risque juridique |
| POST | `/chat` | Chatbot juridique |
| POST | `/rag-search` | Recherche sémantique CDR + CATU |
| POST | `/index-pdf` | Indexer un nouveau PDF |
| GET | `/health` | État du système |

---

## Exemple d'utilisation

```bash
curl -X POST http://localhost:8000/analyze-text \
  -H "Content-Type: application/json" \
  -d '{"text": "je veux construire sans permis"}'
```

Réponse :
```json
{
  "global_status": "VIOLATION",
  "risk_score": 64,
  "rag_fallback": {
    "source": "URBANISME",
    "law": "Code de l'Aménagement du Territoire 2011",
    "articles": ["Art.23 CATU"],
    "explanation": "Toute construction nécessite une autorisation..."
  }
}
```

---

## KPIs

| Métrique | Valeur |
|----------|--------|
| Règles CDR extraites | 66 |
| Taux d'hallucination | 0% |
| Couverture thématique | 28/28 concepts (100%) |
| Quality score | 8.4 / 10 |
| Reliability score | 100/100 — Grade A |
| Chunks RAG | 877 (560 CDR + 317 CATU) |
| Endpoints API | 12 |