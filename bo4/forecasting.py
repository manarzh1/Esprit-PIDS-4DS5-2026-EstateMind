import pandas as pd
import numpy as np
from prophet import Prophet
import warnings
warnings.filterwarnings("ignore")

def prepare_historical_data(df_hist: pd.DataFrame) -> pd.DataFrame:
    """Prépare les données historiques pour Prophet"""
    df = df_hist.copy()
    
    # Conversion de la date
    df["DATE_TRIM"] = pd.to_datetime(df["DATE_TRIM"], format="%d/%m/%Y", errors='coerce')
    df = df.dropna(subset=["DATE_TRIM", "PRIX_M2_MEDIAN", "GOUVERNORAT"])
    
    # Agrégation mensuelle par gouvernorat
    df_grouped = df.groupby([
        "GOUVERNORAT", 
        pd.Grouper(key="DATE_TRIM", freq="M")
    ])["PRIX_M2_MEDIAN"].mean().reset_index()
    
    df_grouped = df_grouped.rename(columns={
        "DATE_TRIM": "ds", 
        "PRIX_M2_MEDIAN": "y"
    })
    
    print(f"✅ Données historiques préparées : {len(df_grouped)} observations pour {df_grouped['GOUVERNORAT'].nunique()} gouvernorats")
    return df_grouped


def train_prophet_per_city(df_grouped: pd.DataFrame, periods: int = 36):
    """Entraîne un modèle Prophet par gouvernorat/ville"""
    models = {}
    forecasts = {}
    
    cities = df_grouped["GOUVERNORAT"].unique()
    
    for city in cities:
        df_city = df_grouped[df_grouped["GOUVERNORAT"] == city].copy()
        
        if len(df_city) < 8:
            print(f"⚠️ {city}: Pas assez de données historiques ({len(df_city)} obs)")
            continue
            
        # Modèle Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode='multiplicative',
            interval_width=0.95
        )
        
        model.fit(df_city)
        models[city] = model
        
        # Prévision future
        future = model.make_future_dataframe(periods=periods, freq='M')
        forecast = model.predict(future)
        
        forecasts[city] = forecast
        print(f"✅ Prophet entraîné pour {city} ({len(df_city)} observations)")
    
    return models, forecasts


def get_projected_price_m2(forecasts: dict, city: str, months_ahead: int = 48):
    """Retourne le prix au m² projeté dans X mois"""
    if city not in forecasts:
        return None
    
    forecast = forecasts[city]
    # Prend la valeur future la plus éloignée demandée
    future_df = forecast[forecast["ds"] > forecast["ds"].iloc[-1] - pd.DateOffset(months=1)]
    
    if not future_df.empty:
        return future_df["yhat"].iloc[-1]
    return None


def integrate_forecast_in_pipeline(df_current: pd.DataFrame, forecasts: dict, horizon_years: int = 5):
    """Intègre les prévisions Prophet dans ton dataframe principal"""
    df = df_current.copy()
    
    def get_projected_price(row):
        # Gestion des noms de colonnes flexibles
        city = str(row.get("city") or row.get("GOUVERNORAT") or row.get("city_name", "")).strip()
        if not city:
            return row.get("price_value", 0)
        
        projected_m2 = get_projected_price_m2(forecasts, city, horizon_years * 12)
        
        if projected_m2 is None:
            return row.get("price_value", 0)
        
        projected_price = projected_m2 * row.get("surface_m2", 1)
        return max(projected_price, row.get("price_value", 0))
    
    df["projected_price"] = df.apply(get_projected_price, axis=1)
    df["projected_roi"] = (df["projected_price"] - df["price_value"]) / df["price_value"]
    df["projected_roi"] = df["projected_roi"].clip(lower=0.02, upper=0.18)
    
    print(f"✅ Projections Prophet intégrées avec succès sur {len(df)} biens")
    return df


# Pour tester le module seul
if __name__ == "__main__":
    print("Testing forecasting module...")
    # Exemple d'utilisation
    # df_hist = pd.read_csv("data/historical_prices.csv")
    # df_grouped = prepare_historical_data(df_hist)
    # models, forecasts = train_prophet_per_city(df_grouped)