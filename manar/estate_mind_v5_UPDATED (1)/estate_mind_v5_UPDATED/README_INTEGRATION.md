# Estate Mind BO6 — Guide d'intégration BO3 + BO4

## ✅ Nouveautés dans cette version

| Fichier | Description |
|---------|-------------|
| `app/services/knowledge/extractors.py` | Transforme les réponses BO3/BO4 en knowledge filtrée |
| `app/services/knowledge/kb_retriever.py` | Cache 3 niveaux : RAM → Supabase → Appel réel |
| `app/services/agents/agent_clients.py` | Mis à jour avec intégration BO3+BO4 complète |
| `migrations/002_knowledge_base.sql` | Schéma Supabase bo6_knowledge |
| `mock_agents/mock_bo3.py` | Mock BO3 pour tester localement |
| `mock_agents/mock_bo4.py` | Mock BO4 pour tester localement |
| `mock_agents/mock_bo1_bo2_bo5.py` | Mocks BO1/BO2/BO5 pour tester localement |

---

## ÉTAPE 0 — Exécuter le schéma Supabase

Dans Supabase SQL Editor, exécuter dans l'ordre :
```
migrations/001_schema.sql   (déjà fait si ancien projet)
migrations/002_knowledge_base.sql   ← NOUVEAU
```

---

## 🅐 SCÉNARIO A — Même machine (localhost)

**Situation :** Tu lances BO6 ET tous les agents sur ton propre PC.

### .env actif (déjà configuré)
```
AGENT_BO3_URL=http://localhost:8003
AGENT_BO4_URL=http://localhost:8004
```

### Lancer les mocks (un terminal par agent)

```powershell
# Terminal 1 — BO1
cd mock_agents
uvicorn mock_bo1_bo2_bo5:app_bo1 --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — BO2
uvicorn mock_bo1_bo2_bo5:app_bo2 --host 0.0.0.0 --port 8002 --reload

# Terminal 3 — BO3
uvicorn mock_bo3:app --host 0.0.0.0 --port 8003 --reload

# Terminal 4 — BO4
uvicorn mock_bo4:app --host 0.0.0.0 --port 8004 --reload

# Terminal 5 — BO5
uvicorn mock_bo1_bo2_bo5:app_bo5 --host 0.0.0.0 --port 8005 --reload

# Terminal 6 — BO6 (orchestrateur)
cd ..
python start_all.py
```

### Tester
```powershell
# Vérifier que les agents répondent
curl http://localhost:8003/health
curl http://localhost:8004/health

# Tester le chat BO6
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"query": "Prix S+2 à Sousse ?"}'

curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"query": "Je veux investir 120k à Sousse"}'
```

---

## 🅑 SCÉNARIO B — Même WiFi (IP locale)

**Situation :** Chaque membre est sur son PC, tous connectés au même WiFi.

### Étape 1 — Chaque membre trouve son IP

```powershell
# Windows
ipconfig
# Chercher "Adresse IPv4" → ex: 192.168.1.25
```

### Étape 2 — Chaque membre lance son agent avec 0.0.0.0

```powershell
# PC de Yosser (BO3) — IMPORTANT : --host 0.0.0.0 obligatoire
uvicorn main:app --host 0.0.0.0 --port 8003 --reload

# PC de Wissem (BO4)
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

### Étape 3 — Chaque membre partage son IP avec Manar (BO6)

| Membre | Agent | IP exemple | Commande test |
|--------|-------|-----------|---------------|
| Manar  | BO6   | 192.168.1.10 | — |
| BO1    | BO1   | 192.168.1.20 | `curl http://192.168.1.20:8001/health` |
| BO2    | BO2   | 192.168.1.22 | `curl http://192.168.1.22:8002/health` |
| Yosser | BO3   | 192.168.1.25 | `curl http://192.168.1.25:8003/health` |
| Wissem | BO4   | 192.168.1.30 | `curl http://192.168.1.30:8004/health` |
| BO5    | BO5   | 192.168.1.35 | `curl http://192.168.1.35:8005/health` |

### Étape 4 — Manar met à jour .env

Dans `.env`, décommenter le bloc Scénario B et remplacer par les vraies IPs :
```ini
AGENT_BO1_URL=http://192.168.1.20:8001
AGENT_BO2_URL=http://192.168.1.22:8002
AGENT_BO3_URL=http://192.168.1.25:8003
AGENT_BO4_URL=http://192.168.1.30:8004
AGENT_BO5_URL=http://192.168.1.35:8005
```

### Étape 5 — Si curl échoue (pare-feu Windows)

Sur le PC de chaque agent, ouvrir PowerShell en **administrateur** :
```powershell
# Autoriser le port dans le pare-feu Windows
netsh advfirewall firewall add rule name="Agent BO3" dir=in action=allow protocol=TCP localport=8003
netsh advfirewall firewall add rule name="Agent BO4" dir=in action=allow protocol=TCP localport=8004
```

### Étape 6 — Lancer BO6
```powershell
python start_all.py
```

---

## 🅒 SCÉNARIO C — Réseaux différents (ngrok)

**Situation :** Chaque membre est chez soi, réseaux WiFi différents.

### Étape 1 — Installer ngrok

1. Aller sur https://ngrok.com/download
2. Créer un compte gratuit
3. Télécharger et installer ngrok

```powershell
# Configurer le token (dans ngrok dashboard → "Your Authtoken")
ngrok config add-authtoken VOTRE_TOKEN_ICI
```

### Étape 2 — Chaque membre lance son agent ET ngrok

```powershell
# Terminal 1 : lancer l'agent
uvicorn main:app --host 0.0.0.0 --port 8003 --reload

# Terminal 2 : créer le tunnel public
ngrok http 8003
```

### Étape 3 — ngrok affiche l'URL publique

```
Forwarding  https://abc123def456.ngrok-free.app → http://localhost:8003
```

**⚠️ Important :** L'URL change à chaque redémarrage de ngrok (compte gratuit).

### Étape 4 — Partager l'URL avec Manar

Chaque membre envoie son URL ngrok à Manar via WhatsApp/Teams.

### Étape 5 — Manar met à jour .env

```ini
AGENT_BO1_URL=https://xxxxxxxx.ngrok-free.app
AGENT_BO2_URL=https://yyyyyyyy.ngrok-free.app
AGENT_BO3_URL=https://zzzzzzzz.ngrok-free.app
AGENT_BO4_URL=https://aaaaaaaa.ngrok-free.app
AGENT_BO5_URL=https://bbbbbbbb.ngrok-free.app
```

### Étape 6 — Lancer BO6
```powershell
python start_all.py
```

---

## 🧪 Tests d'intégration

### Vérifier la knowledge base
```powershell
# Après quelques requêtes chat, vérifier que le cache se remplit
# Dans Supabase SQL Editor :
#   SELECT * FROM bo6_knowledge.agent_cache ORDER BY created_at DESC LIMIT 10;
```

### Tester les endpoints BO3 directement
```powershell
# Estimation de prix
curl "http://localhost:8003/api/estimate?city=Sousse&property_type=S+2"

# Tendances marché
curl "http://localhost:8003/api/market-trends?city=Ariana"

# Recommandations
curl "http://localhost:8003/api/recommendations?budget=180000&city=Tunis"
```

### Tester l'endpoint BO4 directement
```powershell
curl -X POST http://localhost:8004/bo4/analyze `
  -H "Content-Type: application/json" `
  -d '{"budget": 120000, "cities": ["Sousse", "Nabeul"], "goal": "revente", "horizon": 3, "risk": "medium"}'
```

### Test complet du chat BO6 avec BO3
```powershell
# Prix → appelle BO3 /api/estimate
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"query": "Quel est le prix d un S+2 à Ariana ?"}'

# Même requête → réponse depuis cache (0ms pour BO3)
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"query": "Prix appartement Ariana ?"}'
```

### Test complet du chat BO6 avec BO4
```powershell
# Investissement → appelle BO4 /bo4/analyze
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"query": "Je veux investir 150000 TND à Sousse, bon investissement ?"}'
```

---

## 📋 Ce que chaque équipe doit avoir dans son projet

### Endpoint OBLIGATOIRE (tous les BOs)
```python
@app.get("/health")
def health():
    return {"status": "ok", "agent": "BOX", "version": "1.0.0"}
```

### BO3 doit exposer
```
GET /api/estimate?city=X&property_type=Y&budget=Z
GET /api/market-trends?city=X
GET /api/recommendations?budget=X&city=Y
GET /api/opportunities?city=X     (optionnel)
POST /predict                      (legacy — conservé)
```

### BO4 doit exposer
```
POST /bo4/analyze   Body: {budget, cities, goal, horizon, risk}
POST /score         Body: {query, city, budget_max}  (legacy)
```

### Format de réponse standardisé
```json
{
  "status": "success",
  "agent": "BO3",
  "city": "Sousse",
  "...données métier...": "...",
  "available": true
}
```

### En cas d'erreur
```json
{
  "available": false,
  "error": "description de l'erreur",
  "agent": "BOX"
}
```

---

## 📊 Architecture Knowledge Base

```
Requête utilisateur
      ↓
BO6 Pipeline NLP (8 étapes)
      ↓
KB Retriever (3 niveaux)
  ├── Niveau 1 : RAM cache (0ms)      → retourne si valide
  ├── Niveau 2 : Supabase (5-10ms)    → retourne si valide
  └── Niveau 3 : Appel agent réel
        ├── BO3 : GET /api/estimate   → extract_bo3_estimate()
        │         GET /api/market-trends → extract_bo3_trends()
        │         GET /api/recommendations → extract_bo3_recommendations()
        └── BO4 : POST /bo4/analyze   → extract_bo4_analysis()
                  POST /score         → extract_bo4_score()
                        ↓
              store_in_kb() → bo6_knowledge.agent_cache (TTL 1h)
```

**Données JAMAIS récupérées par BO6 :**
- Dataset brut (8500 biens BO4)
- Poids ML / valeurs SHAP brutes
- Données utilisateurs privées
- Configurations internes des agents
