# Estate Mind — Frontend Next.js + Backend FastAPI

## Structure

```
Modeling/                       ← ton projet Python existant
├── agents/
├── tools/
├── config/
├── data/
├── main_api.py                 ← NOUVEAU — backend FastAPI (copier ici)
└── ...

estate-mind-frontend/           ← NOUVEAU — projet Next.js
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── page.tsx                ← Dashboard
│   ├── analyse/page.tsx
│   ├── marche/page.tsx
│   └── pipeline/page.tsx
├── components/
│   ├── NavBar.tsx
│   ├── Gauge.tsx
│   ├── Badge.tsx
│   └── KpiCard.tsx
├── lib/api.ts
├── types/index.ts
├── next.config.mjs
├── tsconfig.json
└── package.json
```

---

## 1. Backend FastAPI

### Installation

```bash
# Depuis le dossier Modeling/
pip install fastapi uvicorn sse-starlette
```

### Copier `main_api.py` dans `/Modeling/`

```bash
cp estate-mind-frontend/main_api.py ./main_api.py
```

### Lancer le backend

```bash
cd Modeling/
uvicorn main_api:app --reload --port 8000
```

Le backend sera accessible sur `http://localhost:8000`.
Swagger UI : `http://localhost:8000/docs`

---

## 2. Frontend Next.js

### Installation

```bash
cd estate-mind-frontend/
npm install
```

### Lancer le frontend

```bash
npm run dev
```

L'interface sera accessible sur `http://localhost:3000`.

---

## 3. Utilisation complète

Lance les deux serveurs dans deux terminaux :

**Terminal 1 — Backend :**
```bash
cd Modeling/
uvicorn main_api:app --reload --port 8000
```

**Terminal 2 — Frontend :**
```bash
cd estate-mind-frontend/
npm run dev
```

Ouvre `http://localhost:3000` dans ton navigateur.

---

## Routes API disponibles

| Méthode | Route                    | Description                          |
|---------|--------------------------|--------------------------------------|
| GET     | `/api/status`            | État du système                      |
| GET     | `/api/dashboard`         | Stats pour la page Dashboard         |
| POST    | `/api/analyze`           | Analyse trust + légal d'une annonce  |
| GET     | `/api/market`            | Statistiques marché (filtres: city, property_type) |
| POST    | `/api/pipeline`          | Lance le pipeline complet (bloquant) |
| GET     | `/api/pipeline/stream`   | Logs du pipeline en temps réel (SSE) |

---

## Variables d'environnement

Le frontend ne nécessite pas de `.env` — tout passe par le proxy Next.js vers `localhost:8000`.

Le backend utilise le `.env` de ton projet Modeling existant.

---

## Build production

```bash
# Frontend
cd estate-mind-frontend/
npm run build
npm start

# Backend
uvicorn main_api:app --host 0.0.0.0 --port 8000 --workers 2
```
