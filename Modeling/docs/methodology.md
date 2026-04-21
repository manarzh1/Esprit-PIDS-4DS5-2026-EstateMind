# Estate Mind — Méthodologie et Calibration

## BO1 — Improve Market Reliability

### DSO1 : Ingestion multi-sources

**Connecteurs et normalisation**
Les 4 scrapers (Tayara, Mubawab, Tecnocasa, Remax) produisent des formats hétérogènes. La couche `BaseConnector` normalise vers un schéma de 13 colonnes standardisé. La priorité de source en cas de doublon — Remax (1) > Tecnocasa (2) > Mubawab (3) > Tayara (4) — reflète la fiabilité relative des données : Remax et Tecnocasa sont des agences professionnelles avec des données structurées, Tayara est une marketplace ouverte avec plus de bruit.

**Déduplication**
Trois niveaux de déduplication sont appliqués séquentiellement :
1. Exacte sur URL : supprime les annonces identiques cross-sources
2. Fuzzy (Jaccard trigrammes) : seuil 0.85 basé sur les tests sur le dataset (au-dessous → faux positifs, au-dessus → doublons non détectés)
3. Sémantique (embeddings cosinus) : seuil 0.88 empirique

**Bornes de validation des prix**
- Minimum : 1 000 TND (en dessous = probablement un loyer ou une erreur)
- Maximum : 10 000 000 TND (au-dessus = ultra-luxe hors marché standard)
- Ces bornes excluent environ 2-3% des annonces dans annonces_combined.csv

### DSO2 : Enrichissement NLP/LLM

**Température LLM = 0.0**
Choix délibéré pour l'extraction structurée. Une température non nulle introduit de la variabilité dans les extractions numériques (prix, surface) — problématique pour la reproductibilité. La température 0 garantit qu'une même annonce produit toujours la même extraction.

**Few-shot : 6 exemples**
6 exemples couvrant les cas difficiles tunisiens : prix en toutes lettres, S+N, terrains sans infos, bureaux, duplex. Au-dessus de 8 exemples, le prompt dépasse le contexte utile du modèle pour des extractions courtes.

**Évaluation de la qualité NLP**
Voir `tools/nlp_evaluator.py` — jeu de test de 60 annonces annotées manuellement. Métriques : précision par champ (tolérance ±5% pour le prix, ±10% pour la surface), taux d'extraction.

**Limites du NLP :**
- Les prix en devises étrangères (EUR, USD) sont neutralisés (= null) — pas de conversion car les taux fluctuent
- Les annonces sans description (champ vide) ne bénéficient pas de l'enrichissement
- Les prix "prix à débattre" ou "négociable" sont correctement retournés comme null

### DSO3 : Tracking et orchestration

**MLflow**
Chaque run pipeline est tracé avec tous les hyperparamètres et métriques. La baseline de drift est mise à jour uniquement si aucun drift n'est détecté — ce qui évite qu'une distribution corrompue devienne la nouvelle référence.

**Drift detection (KS test)**
Seuil p-value < 0.05 (standard statistique). Le test de Kolmogorov-Smirnov est préféré au test t de Student car non-paramétrique — les distributions de prix immobiliers sont asymétriques à droite.

---

## BO2 — Understand Territorial Dynamics

### DSO1 : Séries temporelles

**Méthode de détection de tendance : double approche**

| Méthode | Avantage | Limite |
|---|---|---|
| Régression linéaire | Pente continue, interprétable | Sensible aux outliers de prix |
| Mann-Kendall | Non-paramétrique, p-value | Seulement hausse/baisse/stable |

La combinaison des deux est retenue. Mann-Kendall (α = 0.05) valide la significativité ; la régression linéaire donne la magnitude.

**Pourquoi α = 0.05 ?**
Seuil standard en sciences statistiques. Au-dessus (0.10), trop de faux positifs — des fluctuations normales seraient déclarées "tendances". En dessous (0.01), le test devient trop conservateur et rate des tendances réelles sur des séries courtes (3 mois de données).

**Fréquence d'agrégation : mensuelle (freq="M")**
Choix entre hebdomadaire (trop de bruit), mensuel (équilibre signal/bruit), trimestriel (trop peu de points pour détecter une tendance). Le mensuel est retenu car cohérent avec les cycles immobiliers tunisiens (annonces qui restent en ligne 2-6 semaines en moyenne).

**Limite principale**
`scraped_at` est la date de collecte par le scraper, pas la date de mise en ligne réelle de l'annonce, ni la date de transaction. On mesure l'activité du marché telle qu'observable à un instant donné. Une annonce peut rester en ligne des semaines après la transaction effective.

### DSO2 : Agrégation spatiale

**3 niveaux de granularité**
- Ville (top 30) : pour l'acheteur individuel
- Gouvernorat (24) : pour l'investisseur provincial  
- Région (7) : pour le stratège institutionnel

**Centroïdes approximatifs**
Les coordonnées GPS par zone sont calculées comme la moyenne des annonces de la zone, pas le centroïde géographique réel. Déviation estimée : 5-20 km selon la concentration des annonces. Acceptable pour l'affichage cartographique, insuffisant pour des analyses de proximité.

**Couverture géographique par source**

| Source | Couverture principale | Biais |
|---|---|---|
| Tayara | Nationale mais surreprésente Grand Tunis | Marketplace ouverte → plus d'annonces dans les zones densément peuplées |
| Mubawab | Côte-Est + Grand Tunis | Agences professionnelles concentrées |
| Tecnocasa | 8 provinces seulement | Absente du Sud et Nord-Ouest |
| Remax | Nationale | Bonne couverture mais segment haut de gamme |

### DSO3 : Zones émergentes

**Calibration du score composite**

```
Score = 0.6 × price_growth_normalized + 0.4 × volume_growth_normalized
```

- **Coefficient prix (0.6)** : dans un marché immobilier, la hausse de prix est un signal de tension plus fiable que la hausse de volume, qui peut refléter une suroffre ou une saisonnalité. Référence : Case & Shiller (2003), "Real Differences Between Local Housing Markets".
- **Coefficient volume (0.4)** : la hausse de volume indique un regain d'attractivité mais reste secondaire.

**Calibration du seuil price_threshold = 8%**
Calculé à partir de la volatilité observée dans annonces_combined.csv :
- Écart-type mensuel des prix médians par ville ≈ 4-5%
- Un seuil à 8% ≈ 1.6σ → signal au-delà du bruit naturel
- Testé sur les données : à 5%, trop d'alertes (bruit) ; à 12%, trop peu (manque des signaux réels)

**Calibration du seuil volume_threshold = 20%**
- Variation naturelle du volume entre semaines : ±10-15%
- Un seuil à 20% capte les hausses structurelles (nouvelles agences, événements) sans être déclenché par la variabilité normale

**Calibration des fenêtres temporelles**
- Récente = 45 jours : correspond à ~6 semaines, durée minimale pour observer une tendance sans confondre avec une saisonnalité de court terme
- Référence = 90 jours : 2× la fenêtre récente pour minimiser la variance de la baseline

**Niveaux de sévérité**

| Sévérité | Score composite | Interprétation |
|---|---|---|
| Critical | > 0.70 | Signal fort, action recommandée sous 30 jours |
| High | 0.40 – 0.70 | Signal modéré, veille active recommandée |
| Medium | < 0.40 | Signal faible, à confirmer sur le prochain run |

---

## Limites générales du projet

1. **Fenêtre temporelle** : 3 mois de données (février-avril 2026). Les tendances détectées sont de court terme. Une analyse robuste nécessiterait 12-24 mois de collecte continue.

2. **Prix ≠ transactions** : les prix affichés sont des prix demandés. Les prix réels de transaction (après négociation) sont généralement 5-15% inférieurs en Tunisie.

3. **Biais de sélection** : les biens qui se vendent rapidement apparaissent peu dans les données (retraits rapides). Les données surreprésentent les biens difficiles à vendre.

4. **Données manquantes géographiques** : environ 30% des annonces Tayara ont des coordonnées GPS imputées au centroïde du gouvernorat (champ `_imputed.latitude = true`). Ces annonces contribuent aux statistiques de prix mais pas à la heatmap.

5. **Couverture temporelle inégale** : Remax et Tecnocasa ont des historiques plus longs dans leurs CSV que Tayara. Les séries temporelles Remax sont plus longues et donc plus robustes pour la détection de tendance.
