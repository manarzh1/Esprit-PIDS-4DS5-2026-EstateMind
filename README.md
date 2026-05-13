# 🏠 Estate Mind — BO6 Orchestrateur

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat-square&logo=supabase)
![NLP](https://img.shields.io/badge/NLP-Naïve%20Bayes%20From%20Scratch-FF6B00?style=flat-square)
![Multi-Agent](https://img.shields.io/badge/Architecture-Multi--Agent-6C63FF?style=flat-square)

Cerveau central d'Estate Mind — plateforme immobilière intelligente tunisienne.  
Pipeline NLP 8 étapes · Orchestration multi-agents · Knowledge Base 3 niveaux · Traçabilité complète Supabase

</div>

---

## Vue d'ensemble

BO6 est l'orchestrateur central du système Estate Mind. Il reçoit chaque question utilisateur (FR / EN / AR / Darija), la fait traverser un pipeline NLP complet, route la requête vers l'agent spécialisé approprié, construit la réponse en Markdown et trace tout dans Supabase.

 le classificateur d'intentions est un Naïve Bayes multinomial codé from scratch en pur Python.

---

## Architecture BO6

```
Utilisateur (FR / EN / AR / Darija)
           │  POST /api/v1/chat
           ▼
┌──────────────────────────────────────────────────────┐
│                   BO6 — Port 8000                    │
│                                                      │
│  1. Détection de langue     langdetect               │
│  2. Normalisation Darija    TunisianNormalizer        │
│  3. Traduction → EN         deep-translator           │
│  4. Classification NB       nb_model.pkl (from scratch│
│  5. Routage intent          router.py                │
│  6. Appel agent             dispatcher + KB cache     │
│  7. Template réponse        _tpl_price / _tpl_inv …  │
│  8. Sauvegarde              Supabase — 20+ champs     │
└──────────────┬───────────────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼
  BO1        BO2        BO3        BO4        BO5
 :8001      :8002      :8003      :8004      :8005
General   Location   Prix    Investment   Légal
```

---

## Ce que BO6 fait concrètement

### Pipeline NLP — 8 étapes

| # | Étape | Module | Détail |
|---|---|---|---|
| 1 | Détection langue | `language_detector.py` | Identifie FR / EN / AR / Darija |
| 2 | Normalisation Darija | `tunisian_normalizer.py` | 100+ termes dialectaux → FR standard |
| 3 | Traduction → EN | `translator.py` | Uniformisation avant classification |
| 4 | Classification NB | `naive_bayes.py` | Intent + confidence + top n-grams |
| 5 | Routage | `agents/router.py` | Intent → agent cible |
| 6 | Appel agent | `agent_clients.py` | HTTP + Knowledge Base 3 niveaux |
| 7 | Template Markdown | `orchestrator.py` | Réponse structurée par intent |
| 8 | Sauvegarde | `chat_repo.py` | 20+ champs dans Supabase |

Chaque étape est chronométrée avec un budget strict de 20 secondes au total.

---

### Naïve Bayes From Scratch

Le classificateur d'intentions est entièrement codé en Python pur — sans scikit-learn.

```
log P(c|d) = log P(c) + Σ count(t,d) × log P(t|c)
P(t|c) Laplace = (count(t,c) + 1) / (total_c + |V|)
```

- N-grammes 1→3 : `"prix"` | `"prix_m2"` | `"prix_m2_tunis"`
- Laplace smoothing : zéro probabilité nulle sur mots inconnus
- Explicabilité : top n-grams retournés dans chaque réponse API
- Sérialisé en `models_pkl/nb_model.pkl`, ré-entraînable via `scripts/train_classifier.py`

**Performances mesurées : Accuracy ~0.92 · Macro F1 ~0.89 · ECE ~0.04**

---

### Support Darija Tunisien

Le `TunisianNormalizer` traite le dialecte tunisien avant tout le pipeline — un problème qu'aucun outil NLP standard ne résout.

```
"chnowa soum dar fi tunis"   →  "quel est prix maison à tunis"
"bkaddesh kri appart 9arib"  →  "combien louer appartement proche"
"wesh ghali fi ariana"       →  "quoi cher à ariana"
```

Plus de 100 termes Arabizi + arabe dialectal couverts, avec détection positionnelle et préservation du contexte.

---

### Knowledge Base — 3 niveaux de cache

Chaque appel agent passe d'abord par la KB avant tout HTTP — réduction des appels réels de ~80%.

```
Niveau 1 — RAM Python          0 ms    dict _memory_cache
Niveau 2 — Supabase            5 ms    table bo6_knowledge.agent_cache
Niveau 3 — Appel agent HTTP    ~        si cache vide ou expiré
```

La clé de cache est un SHA-256 (16 chars) des paramètres anonymisés. Même requête → même clé → résultat instantané.  
TTL par agent : BO1 30 min · BO2 120 min · BO3 60 min · BO4 240 min

---

### Extracteurs — Filtrage des réponses agents

> **Actif uniquement en réseau WiFi local** — l'extraction intervient dès que BO6 reçoit la réponse HTTP d'un agent distant.

Avant toute mise en cache ou construction de réponse, les données brutes des agents passent par `knowledge/extractors.py`. Ce module extrait uniquement les champs utiles et écarte le reste — aucun dataset complet n'est jamais exposé à l'utilisateur ni stocké en cache.

```
PC Agent (WiFi)         PC BO6
     │                     │
     │  réponse JSON brute │
     │────────────────────▶│
     │                extractors.py
     │                  (filtrage)
     │                     │
     │              données filtrées
     │                     │
     │              template Markdown
     │                     │
     │               réponse finale
```

Chaque agent a son extracteur dédié qui ne conserve que ce qui est strictement nécessaire : prix médian, score d'investissement, zone géographique, statut juridique, etc. Cette couche protège aussi contre les réponses malformées ou incomplètes d'un agent distant défaillant.

---

### Traçabilité Supabase

Chaque interaction sauvegarde 20+ champs :

```
query · langue détectée · intent · probabilities NB · top n-grams
darija_terms détectés · agent appelé · réponse brute · pipeline_steps
timing ms par étape · session_id · interaction_id
```

Schémas : `bo6_tracking` (sessions, interactions, rapports) + `bo6_knowledge` (cache agents)

---

## Structure du projet

```
estate_v3/
├── main.py                          # FastAPI + lifespan
├── start_all.py                     # Lanceur BO6 + Dashboard
├── app/
│   ├── api/v1/endpoints/
│   │   ├── chat.py                  # POST /api/v1/chat
│   │   ├── history.py               # GET  /api/v1/history
│   │   ├── report.py                # POST /api/v1/report
│   │   └── metrics.py               # GET  /api/v1/metrics
│   ├── services/
│   │   ├── orchestrator.py          # Pipeline 8 étapes — cœur BO6
│   │   ├── agents/
│   │   │   ├── agent_clients.py     # Dispatchers BO1→BO5
│   │   │   └── router.py            # Intent → agent
│   │   ├── nlp/
│   │   │   ├── naive_bayes.py       # Classificateur from scratch
│   │   │   ├── tunisian_normalizer.py
│   │   │   ├── language_detector.py
│   │   │   └── translator.py
│   │   ├── knowledge/
│   │   │   ├── kb_retriever.py      # Cache 3 niveaux
│   │   │   └── extractors.py
│   │   └── report/
│   │       └── pdf_generator.py     # ReportLab — PDF A4
│   ├── db/repositories/
│   │   └── chat_repo.py             # CRUD Supabase
│   └── dashboard/
│       └── metrics_dashboard.py     # Dash + Plotly — port 8050
├── frontend/
│   ├── index.html                   # Interface chat
│   └── dashboard.html               # Dashboard avec chatbot flottant
├── migrations/
│   ├── 001_schema.sql               # Tables bo6_tracking
│   └── 002_knowledge_base.sql       # Table agent_cache
├── models_pkl/
│   └── nb_model.pkl                 # Modèle NB sérialisé
└── scripts/
    ├── train_classifier.py
    └── evaluate.py
```

---

## API

### `POST /api/v1/chat`

```json
// Request
{ "query": "Quel est le prix d'un S+2 à Ariana ?", "session_id": "uuid" }

// Response
{
  "response": "## Estimation de prix — Ariana\n...",
  "detected_language": "fr",
  "detected_intent": "price_estimation",
  "intent_confidence": 0.87,
  "routed_to_agent": "BO3",
  "processing_ms": 1240,
  "explanation": {
    "naive_bayes_detail": { "top_features": ["prix_s+2", "ariana"] }
  }
}
```

### Autres endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/history` | Historique paginé d'une session |
| `POST /api/v1/report` | Génération PDF (ReportLab A4) |
| `GET /api/v1/metrics` | Métriques NLP complètes |
| `GET /api/v1/health` | Status BO6 + agents |

---

## Démarrage rapide

```bash
# Dépendances
pip install -r requirements.txt

# Configurer .env
cp .env.example .env

# Migrations Supabase
# Exécuter migrations/001_schema.sql puis 002_knowledge_base.sql

# Lancer BO6
python start_all.py
```

| Interface | URL |
|---|---|
| Chat | http://localhost:8000/frontend/index.html |
| Dashboard | http://localhost:8000/frontend/dashboard.html |
| Swagger | http://localhost:8000/docs |
| Métriques Dash | http://localhost:8050 |

---

## Configuration réseau — WiFi local

Le projet fonctionne en **réseau WiFi local** — chaque agent tourne sur un PC différent du même réseau.

**Étape 1 — Trouver l'IP de chaque PC :**
```bash
# Windows
ipconfig        # → "Adresse IPv4"

# Linux / Mac
ip a            # → "inet"
```

**Étape 2 — Remplir le `.env` avec les vraies IPs :**

```ini
AGENT_BO1_URL=http://192.168.1.10:8001   # PC membre BO1
AGENT_BO2_URL=http://192.168.1.11:8002   # PC membre BO2
AGENT_BO3_URL=http://192.168.1.12:8003   # PC membre BO3
AGENT_BO4_URL=http://192.168.1.13:8004   # PC membre BO4
AGENT_BO5_URL=http://192.168.1.14:8005   # PC membre BO5
```

**Étape 3 — Lancer chaque agent avec `--host 0.0.0.0` :**

```bash
uvicorn main:app --host 0.0.0.0 --port 8001   # sur le PC BO1
uvicorn main:app --host 0.0.0.0 --port 8002   # sur le PC BO2
uvicorn main:app --host 0.0.0.0 --port 8003   # sur le PC BO3
uvicorn main:app --host 0.0.0.0 --port 8004   # sur le PC BO4
```

> **Windows uniquement** — si un agent n'est pas joignable, ouvrir le pare-feu :
> ```bash
> netsh advfirewall firewall add rule name="BO1" dir=in action=allow protocol=TCP localport=8001
> netsh advfirewall firewall add rule name="BO2" dir=in action=allow protocol=TCP localport=8002
> netsh advfirewall firewall add rule name="BO3" dir=in action=allow protocol=TCP localport=8003
> netsh advfirewall firewall add rule name="BO4" dir=in action=allow protocol=TCP localport=8004
> ```

---

## Évaluation

```bash
python scripts/evaluate.py          # Métriques complètes
python scripts/train_classifier.py  # Ré-entraîner le NB
pytest tests/ -v
```

| Métrique | Valeur |
|---|---|
| Accuracy | ~0.92 |
| Macro F1 | ~0.89 |
| ECE | ~0.04 |
| Perplexité | ~2.1 |

---

<div align="center">
Estate Mind BO6 — Développé avec ❤️ en Tunisie · Python · FastAPI · NLP From Scratch
</div>