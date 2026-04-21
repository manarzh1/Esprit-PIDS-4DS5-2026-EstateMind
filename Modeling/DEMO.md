# 🏛 Estate Mind — Guide de démo client (5 minutes)

> **Objectif** : montrer la plateforme à un client ou un jury en 5 minutes chrono, sans avoir besoin d'expliquer le code.

---

## Lancement en 3 commandes

```bash
# Terminal 1 — Backend (dans le dossier Modeling/)
source venv/Scripts/activate          # Windows
# ou : source venv/bin/activate       # Mac/Linux
uvicorn main_api:app --reload --port 8000

# Terminal 2 — Frontend (dans estate-mind-frontend/frontend/)
npm run dev

# Ouvrir dans le navigateur
# → http://localhost:3000
```

> ⏱ Le backend met ~15 secondes à démarrer la première fois (chargement des modèles).

---

## Script de démo — 5 minutes

### Minute 1 — Le Dashboard

Ouvre `http://localhost:3000`.

Montre les 4 KPIs en haut :
- **14 927 annonces brutes** collectées depuis 4 sources (Tayara, Mubawab, Tecnocasa, Remax)
- **8 412 annonces après nettoyage** — le pipeline supprime les doublons, les prix aberrants et les données manquantes
- **Trust score moyen 0.673** — chaque annonce est scorée sur 5 dimensions de fiabilité
- **1 303 annonces suspectes** détectées automatiquement

Pointe le bloc **"Insight du jour"** : *"L'IA génère un résumé du marché chaque matin à partir des données réelles du pipeline."*

Pointe les **alertes territoriales** dans le Dashboard : *"Ces alertes arrivent en temps réel depuis l'agent BO2."*

---

### Minute 2 — La Carte et les Dynamiques Territoriales

Clique sur **Carte** dans la barre de navigation.

1. En mode **Cercles** : montre les 24 gouvernorats colorés selon leur prix/m². La taille des cercles représente le volume d'annonces.

2. Bascule sur **Heatmap** : *"Voilà comment un acheteur voit immédiatement les zones chères vs accessibles — rouge = cher, bleu = accessible."*

3. Bascule sur **Clusters** : *"22 000 annonces individuelles regroupées intelligemment. En zoomant, les clusters explosent en annonces individuelles."*

4. Clique sur l'onglet **Score d'attractivité** en bas : sélectionne Hammamet vs Mahdia sur le radar. *"5 dimensions comparées en un coup d'œil — le client voit immédiatement où investir."*

Puis clique sur **Territoire** dans la navigation :

- Montre les alertes avec les **recommandations actionnables** en cliquant sur une alerte critique. *"Ce n'est pas juste une observation — c'est une recommandation : agir sous 30 jours, voici pourquoi."*

---

### Minute 3 — La Recherche et l'Analyse

Clique sur **Recherche**.

1. Tape `"Sousse appartement"` dans la barre et appuie sur Entrée.
2. Montre les filtres (budget, surface, trust minimum, source).
3. Clique sur **Analyser** sur une annonce : le panneau latéral s'ouvre avec le verdict IA en direct.
4. Montre le widget **"Ce prix est-il juste ?"** : *"Le système compare automatiquement le prix/m² de ce bien avec la médiane du marché dans cette ville."*
5. Coche 2-3 annonces et clique **Comparer** : le tableau côte à côte s'ouvre avec les meilleures valeurs surlignées en vert.

---

### Minute 4 — Le Portefeuille

Clique sur **Portefeuille**.

- Montre les biens sauvegardés avec le **delta de prix** : vert = le prix a baissé depuis la sauvegarde, rouge = il a monté.
- Clique sur **"Voir historique"** sur un bien : le graphique d'évolution des prix s'affiche.
- Montre le bouton **"Activer alerte"** : *"Le client peut configurer une alerte email pour être notifié si le prix de ce bien baisse."*

---

### Minute 5 — Le Pipeline (pour les profils techniques)

Clique sur **Pipeline**.

- Explique que le pipeline tourne automatiquement toutes les 6 heures et met à jour toutes les données.
- Montre le streaming des logs en temps réel si disponible.

---

## Questions fréquentes des clients

**"D'où viennent les données ?"**
> 4 scrapers réels : Tayara (marketplace nationale), Mubawab (professionnel), Tecnocasa (agence internationale), Remax (haut de gamme). Collecte automatique toutes les 6 heures.

**"Comment vous garantissez la fiabilité ?"**
> Chaque annonce reçoit un trust score calculé sur 5 dimensions : cohérence du prix/m², qualité de la description, réputation de la source, cohérence des données géographiques, et détection de prix suspects. Les annonces sous 0.50 sont flaggées automatiquement.

**"Est-ce que le système détecte les fausses annonces ?"**
> Oui. L'agent détecte les prix incohérents (ex: villa à 50 TND), les descriptions copiées-collées identiques avec des prix différents, les coordonnées GPS incorrectes, et les sources peu fiables. L'ensemble est loggué et tracé.

**"Comment les alertes territoriales fonctionnent ?"**
> L'agent compare le prix médian et le volume d'annonces des 45 derniers jours avec les 45 jours précédents. Si la hausse dépasse 8% sur le prix ou 20% sur le volume, une alerte est générée avec un niveau de sévérité et une recommandation actionnable.

**"Peut-on avoir les données en temps réel ?"**
> Le dashboard se rafraîchit automatiquement toutes les 60 secondes. Les alertes peuvent être envoyées par email ou webhook (Slack, Discord) dès qu'elles sont détectées.

---

## Données de démo incluses

Si PostgreSQL n'est pas configuré, la plateforme fonctionne en mode démo avec :
- Les données statiques de `annonces_combined.csv` (22 845 annonces réelles)
- Les scores de démo pré-calculés
- Les alertes territoriales simulées depuis les vraies distributions de prix

> Les données de démo sont issues d'un scraping réel effectué en février-avril 2026.
