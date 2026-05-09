"""
Estimateur de prix immobilier — Random Forest
Adapté depuis Estate Mind (Tkinter) vers FastAPI
"""
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

warnings.filterwarnings("ignore")

DATA_PATH = Path(__file__).parent.parent / "data" / "all_sources_processed_FINAL.csv"

NUMERIC = ["surface_m2", "bedrooms", "bathrooms", "latitude", "longitude",
           "equipment_score", "etage_num"]
CATEG = ["city"]

_model = None
_df_clean = None
_city_stats = None
_metrics = {"rmse": None, "r2": None, "n_samples": 0, "n_cities": 0}


def load_and_train():
    global _model, _df_clean, _city_stats, _metrics

    df = pd.read_csv(DATA_PATH, sep=";", encoding="latin-1")
    df = df[df["transaction_type"] == "vente"].copy()

    df["price"] = pd.to_numeric(df["price_value"], errors="coerce")
    df["surface_m2"] = pd.to_numeric(df["surface_m2"], errors="coerce")
    df["bedrooms"] = pd.to_numeric(df["bedrooms"], errors="coerce")
    df["bathrooms"] = pd.to_numeric(df["bathrooms"], errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["equipment_score"] = 5.0
    df["etage_num"] = 2.0

    df = df.dropna(subset=["price", "surface_m2"])
    df = df[(df["price"] >= 47_000) & (df["price"] <= 4_500_000)]
    df = df[(df["surface_m2"] >= 20) & (df["surface_m2"] <= 800)]
    df["city"] = df["city"].fillna("Inconnu").str.strip().str.title()
    df["price_per_m2"] = df["price"] / df["surface_m2"]
    _df_clean = df

    _city_stats = (
        df.groupby("city").agg(
            median_price=("price", "median"),
            mean_price=("price", "mean"),
            min_price=("price", "min"),
            max_price=("price", "max"),
            count=("price", "count"),
            median_ppm2=("price_per_m2", "median"),
            lat=("latitude", "median"),
            lon=("longitude", "median"),
        ).reset_index()
    )
    _city_stats = _city_stats[_city_stats["count"] >= 3]

    X = df[NUMERIC + CATEG].copy()
    y = df["price"].copy()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    num_pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
    ])
    cat_pipe = Pipeline([
        ("imp", SimpleImputer(strategy="constant", fill_value="Inconnu")),
        ("enc", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    prep = ColumnTransformer([
        ("num", num_pipe, NUMERIC),
        ("cat", cat_pipe, CATEG),
    ])
    pipeline = Pipeline([
        ("prep", prep),
        ("rf", RandomForestRegressor(n_estimators=200, min_samples_leaf=4,
                                     n_jobs=-1, random_state=42)),
    ])
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    _model = pipeline
    _metrics["rmse"] = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    _metrics["r2"] = float(r2_score(y_test, y_pred))
    _metrics["n_samples"] = len(df)
    _metrics["n_cities"] = len(_city_stats)


def is_ready() -> bool:
    return _model is not None


def get_cities() -> list:
    if _city_stats is None:
        return []
    return sorted(_city_stats["city"].tolist())


def get_metrics() -> dict:
    return _metrics


def estimate(city: str, surface: float, bedrooms: float, bathrooms: float,
             budget: float = 0, etage: float = 2, equipment_score: float = 5) -> dict:
    if _model is None:
        raise RuntimeError("Modèle non initialisé")

    city_row = _city_stats[_city_stats["city"] == city]
    lat = float(city_row["lat"].values[0]) if len(city_row) else 36.8
    lon = float(city_row["lon"].values[0]) if len(city_row) else 10.18

    row = pd.DataFrame([{
        "surface_m2": surface,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "latitude": lat,
        "longitude": lon,
        "equipment_score": equipment_score,
        "etage_num": etage,
        "city": city,
    }])

    prep = _model.named_steps["prep"]
    rf = _model.named_steps["rf"]
    X_t = prep.transform(row)
    tree_preds = np.array([t.predict(X_t) for t in rf.estimators_]).flatten()
    predicted = float(tree_preds.mean())
    std = float(tree_preds.std())
    half_ci = max(1.28 * std, 0.5 * _metrics["rmse"])
    confidence = max(0, min(100, int((1 - std / predicted) * 100))) if predicted > 0 else 0

    city_median = float(city_row["median_price"].values[0]) if len(city_row) else None
    city_ppm2 = float(city_row["median_ppm2"].values[0]) if len(city_row) else None
    city_min = float(city_row["min_price"].values[0]) if len(city_row) else None
    city_max = float(city_row["max_price"].values[0]) if len(city_row) else None
    market_delta_pct = ((predicted - city_median) / city_median) if city_median else None

    # Surface possible avec le budget donné
    surface_possible = round(budget / (predicted / surface)) if budget > 0 and predicted > 0 else None

    return {
        "predicted": round(predicted),
        "ci_lower": round(max(0, predicted - half_ci)),
        "ci_upper": round(predicted + half_ci),
        "confidence": confidence,
        "price_per_m2": round(predicted / surface) if surface > 0 else 0,
        "city_median": round(city_median) if city_median else None,
        "city_ppm2": round(city_ppm2) if city_ppm2 else None,
        "city_min": round(city_min) if city_min else None,
        "city_max": round(city_max) if city_max else None,
        "market_delta_pct": round(market_delta_pct * 100, 1) if market_delta_pct is not None else None,
        "budget_delta": round(budget - predicted) if budget > 0 else None,
        "surface_possible": surface_possible,
        "r2": round(_metrics["r2"], 3),
        "rmse": round(_metrics["rmse"]),
    }


def get_city_distribution(city: str) -> dict:
    if _df_clean is None:
        return {}
    city_data = _df_clean[_df_clean["city"] == city]
    prices = city_data["price"].dropna().tolist()
    ppm2 = city_data["price_per_m2"].dropna().tolist()
    return {
        "prices": [round(p) for p in prices[:200]],
        "price_per_m2": [round(p) for p in ppm2[:200]],
        "count": len(prices),
    }
