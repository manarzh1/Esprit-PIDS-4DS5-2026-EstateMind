# ============================================================
# PIPELINE : FUSION MULTI-SOURCES + ANALYSE EXPLORATOIRE (EDA)
# ============================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re

pd.set_option("display.max_columns", None)

# ------------------------------------------------------------
# 0. Configuration chemins
# ------------------------------------------------------------

REMAX_PATH = "data/remax_20260217_072014.csv"
TAYARA_PATH = "data/tayara_20260217_004839.csv"
TECNOCASA_PATH = "data/tecnocasa_complete_verifier.csv"
CENTURY21_PATH = "data/century21_vente_20260217_0133.csv"

GLOBAL_PATH = "data/immobilier_global.csv"


# ============================================================
# 1) FUSION MULTI-SOURCES (4 CSV IMMOBILIER)
# ============================================================

# 1.1 Charger les données
remax = pd.read_csv(REMAX_PATH)
tayara = pd.read_csv(TAYARA_PATH)
tecnocasa = pd.read_csv(TECNOCASA_PATH)
century21 = pd.read_csv(CENTURY21_PATH)

# 1.2 Standardisation REMAX
df_remax = remax.rename(columns={
    "price": "prix",
    "area_m2": "surface",
    "city": "ville",
    "property_type": "type_bien",
    "rooms": "nb_pieces"
})
df_remax["source"] = "remax"
df_remax = df_remax[["prix", "surface", "ville", "type_bien", "nb_pieces", "source"]]

# 1.3 Standardisation TAYARA
df_tayara = tayara.rename(columns={
    "price": "prix",
    "area": "surface",
    "city": "ville"
})
df_tayara["type_bien"] = None
df_tayara["nb_pieces"] = None
df_tayara["source"] = "tayara"
df_tayara = df_tayara[["prix", "surface", "ville", "type_bien", "nb_pieces", "source"]]

# 1.4 Standardisation TECNOCASA
df_tecnocasa = tecnocasa.rename(columns={
    "Prix": "prix",
    "Surface": "surface",
    "Région": "ville",
    "Type": "type_bien",
    "Pièces": "nb_pieces"
})
df_tecnocasa["source"] = "tecnocasa"
df_tecnocasa = df_tecnocasa[["prix", "surface", "ville", "type_bien", "nb_pieces", "source"]]

# 1.5 Standardisation CENTURY21
df_century = century21.rename(columns={
    "prix": "prix",
    "surface": "surface",
    "localisation": "ville",
    "type_bien": "type_bien"
})
df_century["nb_pieces"] = None
df_century["source"] = "century21"
df_century = df_century[["prix", "surface", "ville", "type_bien", "nb_pieces", "source"]]

# 1.6 Fusion
df_global = pd.concat([df_remax, df_tayara, df_tecnocasa, df_century], ignore_index=True)

# 1.7 Sauvegarde global
df_global.to_csv(GLOBAL_PATH, index=False)
print("Dataset global sauvegardé :", GLOBAL_PATH, "| Shape:", df_global.shape)
print(df_global.head())


# ============================================================
# 2) ANALYSE EXPLORATOIRE DES DONNÉES IMMOBILIÈRES (EDA)
# ============================================================

# ------------------------------------------------------------
# 2.1 Chargement (IMPORTANT : on charge le dataset global)
# ------------------------------------------------------------
file_path = GLOBAL_PATH
df = pd.read_csv(file_path)

print("\nAperçu des données (GLOBAL) :")
print(df.head())

# ------------------------------------------------------------
# 2.2 Exploration initiale
# ------------------------------------------------------------
print("\n--- Dimensions ---")
print(df.shape)

print("\n--- Types de variables ---")
print(df.dtypes)

print("\n--- Informations générales ---")
df.info()

print("\n--- Statistiques descriptives (brutes) ---")
print(df.describe(include="all"))

# ------------------------------------------------------------
# 2.3 Valeurs manquantes
# ------------------------------------------------------------
missing = df.isnull().sum()
missing_percent = (missing / len(df)) * 100

missing_df = pd.DataFrame({
    "Missing Values": missing,
    "% Missing": missing_percent
}).sort_values("% Missing", ascending=False)

print("\n--- Valeurs manquantes ---")
print(missing_df)

plt.figure(figsize=(10, 6))
sns.heatmap(df.isnull(), cbar=False)
plt.title("Visualisation des valeurs manquantes")
plt.show()

# ------------------------------------------------------------
# 2.4 Nettoyage
# ------------------------------------------------------------
print("\n--- Suppression des doublons ---")
print("Avant :", df.duplicated().sum())
df = df.drop_duplicates()
print("Après :", df.duplicated().sum())

# Nettoyage texte
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

# Suppression lignes trop vides
threshold = len(df.columns) * 0.5
df = df.dropna(thresh=threshold)

# Conversion + extraction numérique
def extract_number(x):
    if pd.isnull(x):
        return x
    cleaned = re.sub(r"[^\d.]", "", str(x))
    return float(cleaned) if cleaned != "" else np.nan

if "prix" in df.columns:
    df["prix"] = df["prix"].apply(extract_number)
    df["prix"] = pd.to_numeric(df["prix"], errors="coerce")
    df["prix"].fillna(df["prix"].median(), inplace=True)

if "surface" in df.columns:
    df["surface"] = df["surface"].apply(extract_number)
    df["surface"] = pd.to_numeric(df["surface"], errors="coerce")

# Filtrage simple outliers
if "prix" in df.columns:
    df = df[df["prix"] > 10000]
if "surface" in df.columns:
    df = df[df["surface"] > 10]

# ------------------------------------------------------------
# 2.5 EDA : univariée + outliers
# ------------------------------------------------------------
print("\n=== Analyse univariée ===")
numeric_df = df.select_dtypes(include=[np.number])
cat_cols = df.select_dtypes(include=["object"]).columns

print("\nStats numériques :")
print(numeric_df.describe())

print("\nHistogrammes :")
numeric_df.hist(figsize=(12, 10), bins=30)
plt.tight_layout()
plt.show()

print("\nBoxplots (outliers) :")
for col in numeric_df.columns:
    plt.figure(figsize=(6, 4))
    sns.boxplot(x=df[col])
    plt.title(f"Outliers - {col}")
    plt.show()

print("\nVariables catégorielles :")
for col in cat_cols:
    print(f"\nDistribution de {col} :")
    print(df[col].value_counts(dropna=False))

# ------------------------------------------------------------
# 2.6 EDA : bivariée (corrélation + plots)
# ------------------------------------------------------------
print("\n=== Analyse bivariée ===")

corr_matrix = numeric_df.corr()
print("\nMatrice de corrélation :")
print(corr_matrix)

plt.figure(figsize=(10, 8))
sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f")
plt.title("Matrice de corrélation (numériques)")
plt.show()

if "prix" in numeric_df.columns:
    print("\nCorrélation avec le prix :")
    print(corr_matrix["prix"].sort_values(ascending=False))

    print("\nScatter plots (numériques vs prix) :")
    for col in numeric_df.columns:
        if col != "prix":
            sns.scatterplot(x=col, y="prix", data=df)
            plt.title(f"{col} vs prix")
            plt.show()

    print("\nBoxplots (catégorielles vs prix) :")
    for col in cat_cols:
        plt.figure(figsize=(8, 5))
        sns.boxplot(x=col, y="prix", data=df)
        plt.title(f"Prix selon {col}")
        plt.xticks(rotation=45)
        plt.show()

# ------------------------------------------------------------
# 2.7 Feature Engineering
# ------------------------------------------------------------
print("\n=== Feature Engineering ===")
if "prix" in df.columns and "surface" in df.columns:
    df["prix_m2"] = df["prix"] / df["surface"]
    print("Feature ajoutée : prix_m2")

if "source" in df.columns:
    print("\nRépartition des sources :")
    print(df["source"].value_counts())

# ------------------------------------------------------------
# 2.8 Sauvegardes
# ------------------------------------------------------------
output_clean = "data/immobilier_clean.csv"
df.to_csv(output_clean, index=False)
print("\nDataset clean sauvegardé :", output_clean)
