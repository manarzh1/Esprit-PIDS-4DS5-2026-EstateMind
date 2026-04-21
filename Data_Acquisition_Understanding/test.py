
# ============================================================
# ANALYSE EXPLORATOIRE DES DONNÉES IMMOBILIÈRES
# ============================================================

# ------------------------------------------------------------
# 1. Introduction
# ------------------------------------------------------------
# Objectif :
# Explorer, nettoyer et préparer les données issues du scraping immobilier.
#
# Étapes :
# - Analyse de la structure des données
# - Identification des valeurs manquantes et incohérences
# - Nettoyage et transformation
# - Analyse univariée et bivariée
# - Préparation des données pour analyse ou machine learning
#
# Source :
# Données collectées via scraping (Tayara, Mubawab, etc.)
#
# Remarque :
# Le pipeline est reproductible : il suffit de changer le chemin du fichier CSV


# ------------------------------------------------------------
# 2. Import des librairies
# ------------------------------------------------------------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re

pd.set_option('display.max_columns', None)


# ------------------------------------------------------------
# 3. Chargement des données
# ------------------------------------------------------------

file_path = "data/immobilier.csv"

df = pd.read_csv(file_path)

print("Aperçu des données :")
print(df.head())


# ------------------------------------------------------------
# 4. Exploration initiale
# ------------------------------------------------------------

print("\n--- Dimensions ---")
print(df.shape)

print("\n--- Types de variables ---")
print(df.dtypes)

print("\n--- Informations générales ---")
df.info()

print("\n--- Statistiques descriptives (brutes) ---")
print(df.describe(include='all'))


# ------------------------------------------------------------
# Valeurs manquantes
# ------------------------------------------------------------

missing = df.isnull().sum()
missing_percent = (missing / len(df)) * 100

missing_df = pd.DataFrame({
    'Missing Values': missing,
    '% Missing': missing_percent
}).sort_values('% Missing', ascending=False)

print("\n--- Valeurs manquantes ---")
print(missing_df)

plt.figure(figsize=(10, 6))
sns.heatmap(df.isnull(), cbar=False)
plt.title("Visualisation des valeurs manquantes")
plt.show()


# ------------------------------------------------------------
# 5. Nettoyage des données
# ------------------------------------------------------------

# 5.1 Suppression des doublons
print("\n--- Suppression des doublons ---")
print("Avant :", df.duplicated().sum())

df = df.drop_duplicates()

print("Après :", df.duplicated().sum())

# 5.2 Nettoyage texte : suppression des espaces inutiles
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

# 5.3 Gestion des valeurs manquantes : suppression lignes trop vides
threshold = len(df.columns) * 0.5
df = df.dropna(thresh=threshold)

# 5.4 Conversion des types (avant extraction d’unités)
if 'prix' in df.columns:
    df['prix'] = pd.to_numeric(df['prix'], errors='coerce')

if 'surface' in df.columns:
    df['surface'] = pd.to_numeric(df['surface'], errors='coerce')

# 5.5 Nettoyage des unités (si prix/surface contiennent des chaînes)
def extract_number(x):
    if pd.isnull(x):
        return x
    return float(re.sub(r"[^\d.]", "", str(x)))

if 'prix' in df.columns:
    df['prix'] = df['prix'].apply(extract_number)
    df['prix'].fillna(df['prix'].median(), inplace=True)  # imputation simple

if 'surface' in df.columns:
    df['surface'] = df['surface'].apply(extract_number)

# 5.6 Gestion des valeurs aberrantes (règles simples)
if 'prix' in df.columns:
    df = df[df['prix'] > 10000]

if 'surface' in df.columns:
    df = df[df['surface'] > 10]


# ============================================================
# 6. Chargement et préparation des données (EDA + contrôles)
# ============================================================

print("\n=== 6. Chargement et préparation des données ===")

# Variables numériques et catégorielles
numeric_df = df.select_dtypes(include=[np.number])
cat_cols = df.select_dtypes(include=['object']).columns

# 6.1 Import des données (déjà fait) -> rappel
print("\n6.1 Import des données : terminé (df chargé depuis CSV).")

# 6.2 Interprétation : structure globale
print("\n6.2 Interprétation :")
print("- Les types de variables et le volume du dataset ont été inspectés.")
print("- Les valeurs manquantes et la qualité globale ont été identifiées.")

# 6.3 Vérification des doublons
print("\n6.3 Vérification des doublons :")
print("Doublons restants :", df.duplicated().sum())

# 6.4 Interprétation
print("\n6.4 Interprétation :")
print("- Les doublons ont été supprimés pour éviter un biais dans l’analyse.")

# 6.5 Vérification des valeurs manquantes (après nettoyage)
print("\n6.5 Valeurs manquantes après nettoyage :")
print(df.isnull().sum().sort_values(ascending=False))

# 6.6 Interprétation
print("\n6.6 Interprétation :")
print("- Les lignes trop incomplètes ont été supprimées.")
print("- Le prix a été imputé via la médiane (approche simple).")

# 6.8 Détection et traitement des valeurs aberrantes (outliers)
print("\n6.8 Outliers (visualisation rapide via boxplots) :")
for col in numeric_df.columns:
    plt.figure(figsize=(6, 4))
    sns.boxplot(x=df[col])
    plt.title(f"Outliers - {col}")
    plt.show()

# 6.9 Remarque
print("\n6.9 Remarque :")
print("- Le filtrage des outliers est basé sur des règles simples (prix > 10000, surface > 10).")
print("- Il peut être affiné par quantiles ou par domaine métier plus tard.")

# 6.12 Transformation : encodage (préparation ML)
print("\n6.12 Transformation : encodage (catégorielles -> codes)")

df_encoded = df.copy()
for col in cat_cols:
    df_encoded[col] = df_encoded[col].astype('category').cat.codes

print("Encodage terminé. Aperçu :")
print(df_encoded.head())

# 6.16 Transformation : normalisation/standardisation
print("\n6.16 Transformation : standardisation (option ML)")

scaled_df = None
try:
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    scaled_df = df_encoded.copy()

    numeric_cols = scaled_df.select_dtypes(include=[np.number]).columns
    scaled_df[numeric_cols] = scaler.fit_transform(scaled_df[numeric_cols])

    print("Standardisation terminée. Aperçu :")
    print(scaled_df.head())

except Exception as e:
    print("Standardisation ignorée (sklearn non installé ou erreur).")
    print("Erreur :", e)


# ============================================================
# 7. Analyse univariée
# ============================================================

print("\n=== 7. Analyse univariée ===")

# 7.1 Variables quantitatives : stats + histogrammes
print("\n7.1 Statistiques descriptives (numériques) :")
print(numeric_df.describe())

print("\n7.1 Histogrammes (variables numériques) :")
numeric_df.hist(figsize=(12, 10), bins=30)
plt.tight_layout()
plt.show()

# 7.7 Variables qualitatives : fréquences et proportions
print("\n7.7 Variables qualitatives : fréquences et proportions")
for col in cat_cols:
    print(f"\nDistribution de {col} :")
    print(df[col].value_counts(dropna=False))
    print("\nProportions :")
    print((df[col].value_counts(dropna=False) / len(df)).round(3))


# ============================================================
# 8. Analyse bivariée
# ============================================================

print("\n=== 8. Analyse bivariée ===")

# 8.1 Relations entre variables quantitatives : corrélation
print("\n8.1 Matrice de corrélation :")
corr_matrix = numeric_df.corr()
print(corr_matrix)

plt.figure(figsize=(10, 8))
sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f")
plt.title("Matrice de corrélation (variables numériques)")
plt.show()

# 8.2 Relation prix vs variables quantitatives (scatter)
if 'prix' in numeric_df.columns:
    print("\n8.2 Scatter plots : variables numériques vs prix")
    for col in numeric_df.columns:
        if col != 'prix':
            sns.scatterplot(x=col, y='prix', data=df)
            plt.title(f"{col} vs prix")
            plt.show()

# 8.2 Relation prix vs variables qualitatives (boxplot)
if 'prix' in df.columns:
    print("\n8.2 Boxplots : prix vs variables catégorielles")
    for col in cat_cols:
        plt.figure(figsize=(8, 5))
        sns.boxplot(x=col, y='prix', data=df)
        plt.title(f"Prix selon {col}")
        plt.xticks(rotation=45)
        plt.show()


# ============================================================
# 9. Feature Engineering
# ============================================================

print("\n=== 9. Feature Engineering ===")

if 'prix' in df.columns and 'surface' in df.columns:
    df['prix_m2'] = df['prix'] / df['surface']
    print("Feature ajoutée : prix_m2")

if 'source' in df.columns:
    print("\nRépartition des sources :")
    print(df['source'].value_counts())


# ============================================================
# 10. Sauvegarde des données
# ============================================================

print("\n=== 10. Sauvegarde ===")

output_clean = "data/immobilier_clean.csv"
output_encoded = "data/immobilier_encoded.csv"
output_scaled = "data/immobilier_scaled.csv"

df.to_csv(output_clean, index=False)
df_encoded.to_csv(output_encoded, index=False)

print("Dataset clean sauvegardé :", output_clean)
print("Dataset encodé sauvegardé :", output_encoded)

if scaled_df is not None:
    scaled_df.to_csv(output_scaled, index=False)
    print("Dataset standardisé sauvegardé :", output_scaled)
