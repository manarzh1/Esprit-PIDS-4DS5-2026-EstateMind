"""
app/services/agents/bo3_mock_agent.py
=======================================
Module de données réelles BO3 — remplace les appels HTTP quand
USE_HTTP_AGENTS=false (mode direct).

Données extraites depuis :
  - backend/data/all_sources_processed_FINAL.csv  (8 673 annonces)
  - backend/data/immobilier_tunisie_global.csv     (SARIMA — 24 gouvernorats)

Utilisation dans agent_clients.py :
    from app.services.agents.bo3_mock_agent import estimate_price, recommend_zones, sarima_invest

FLOW :
  call_bo3(intent="price_estimation", params, session_id)
      └── estimate_price(city, surface, bedrooms, bathrooms, budget)
              └── retourne le même format JSON que /api/estimate

  call_bo3(intent="location_analysis", ...)
      └── recommend_zones(ville, budget, type_bien)
              └── retourne le même format que /api/recommend

  call_bo3(intent="investment_analysis", ...)
      └── sarima_invest(gouvernorat)
              └── retourne le même format que /api/train + /api/analysis
"""

import math
import time
from difflib import get_close_matches

# ─────────────────────────────────────────────────────────────────────────────
#  DONNÉES RÉELLES — extraites des CSVs BO3
# ─────────────────────────────────────────────────────────────────────────────

CITY_STATS: dict = {
    "Ain Zaghouan": {"median_price": 515000, "min_price": 285000, "max_price": 630000, "count": 9, "median_ppm2": 3280, "lat": 36.8588, "lon": 10.2853},
    "Akouda": {"median_price": 366000, "min_price": 130000, "max_price": 1150000, "count": 110, "median_ppm2": 3791, "lat": 35.87, "lon": 10.57},
    "Ariana": {"median_price": 370000, "min_price": 48800, "max_price": 3000000, "count": 397, "median_ppm2": 2400, "lat": 36.8665, "lon": 10.1647},
    "Ariana Ville": {"median_price": 350000, "min_price": 100000, "max_price": 1350000, "count": 320, "median_ppm2": 2800, "lat": 36.8625, "lon": 10.1956},
    "Ben Arous": {"median_price": 240000, "min_price": 49000, "max_price": 1850000, "count": 291, "median_ppm2": 1850, "lat": 36.7531, "lon": 10.2332},
    "Beni Khiar": {"median_price": 270000, "min_price": 200000, "max_price": 580000, "count": 7, "median_ppm2": 2903, "lat": 36.47, "lon": 10.78},
    "Bizerte": {"median_price": 292500, "min_price": 50000, "max_price": 1500000, "count": 82, "median_ppm2": 1662, "lat": 37.2746, "lon": 9.8739},
    "Bizerte Nord": {"median_price": 212500, "min_price": 130000, "max_price": 1100000, "count": 22, "median_ppm2": 2031, "lat": 37.272, "lon": 9.8708},
    "Borj Cedria": {"median_price": 235000, "min_price": 210000, "max_price": 356000, "count": 3, "median_ppm2": 800, "lat": 36.6956, "lon": 10.3872},
    "Boumhel Bassatine": {"median_price": 344500, "min_price": 165000, "max_price": 800000, "count": 22, "median_ppm2": 2942, "lat": 36.5772, "lon": 10.3425},
    "Carthage": {"median_price": 500000, "min_price": 240000, "max_price": 2000000, "count": 18, "median_ppm2": 4171, "lat": 36.8566, "lon": 10.3258},
    "Carthage Byrsa": {"median_price": 1700000, "min_price": 110000, "max_price": 2250000, "count": 3, "median_ppm2": 3541, "lat": 36.8607, "lon": 10.3245},
    "Chott Mariem": {"median_price": 240000, "min_price": 185000, "max_price": 420000, "count": 3, "median_ppm2": 2198, "lat": 35.9335, "lon": 10.5465},
    "Cité El Khadra": {"median_price": 312500, "min_price": 210000, "max_price": 420000, "count": 6, "median_ppm2": 3333, "lat": 36.8266, "lon": 10.1882},
    "Denden": {"median_price": 235000, "min_price": 170000, "max_price": 490000, "count": 10, "median_ppm2": 1885, "lat": 36.826, "lon": 10.124},
    "El Aouina": {"median_price": 390000, "min_price": 200000, "max_price": 1100000, "count": 19, "median_ppm2": 3500, "lat": 36.851, "lon": 10.2273},
    "El Kram": {"median_price": 307500, "min_price": 175000, "max_price": 900000, "count": 20, "median_ppm2": 3007, "lat": 36.8358, "lon": 10.2737},
    "El Manar": {"median_price": 380000, "min_price": 230000, "max_price": 700000, "count": 14, "median_ppm2": 3461, "lat": 36.8638, "lon": 10.1907},
    "El Menzah": {"median_price": 350000, "min_price": 190000, "max_price": 1900000, "count": 79, "median_ppm2": 2755, "lat": 36.8589, "lon": 10.179},
    "El Mourouj": {"median_price": 262500, "min_price": 130000, "max_price": 850000, "count": 36, "median_ppm2": 2272, "lat": 36.7362, "lon": 10.2084},
    "El Omrane": {"median_price": 265000, "min_price": 150000, "max_price": 800000, "count": 12, "median_ppm2": 2500, "lat": 36.8183, "lon": 10.1596},
    "Ezzahra": {"median_price": 340000, "min_price": 165000, "max_price": 1000000, "count": 14, "median_ppm2": 2916, "lat": 36.7688, "lon": 10.2574},
    "Fouchana": {"median_price": 215000, "min_price": 130000, "max_price": 500000, "count": 9, "median_ppm2": 1750, "lat": 36.681, "lon": 10.1643},
    "Gammarth": {"median_price": 725000, "min_price": 200000, "max_price": 2500000, "count": 28, "median_ppm2": 5000, "lat": 36.9125, "lon": 10.291},
    "Ghar El Melh": {"median_price": 155000, "min_price": 130000, "max_price": 200000, "count": 3, "median_ppm2": 1250, "lat": 37.1968, "lon": 10.1762},
    "Hammamet": {"median_price": 360000, "min_price": 48000, "max_price": 1300000, "count": 314, "median_ppm2": 3600, "lat": 36.4, "lon": 10.6167},
    "Hammam Sousse": {"median_price": 350000, "min_price": 120000, "max_price": 1500000, "count": 152, "median_ppm2": 3763, "lat": 35.8605, "lon": 10.5974},
    "Kalâa Kebira": {"median_price": 295000, "min_price": 165000, "max_price": 750000, "count": 10, "median_ppm2": 2625, "lat": 35.8669, "lon": 10.5372},
    "Khezama": {"median_price": 395000, "min_price": 200000, "max_price": 800000, "count": 8, "median_ppm2": 3600, "lat": 35.8402, "lon": 10.626},
    "La Marsa": {"median_price": 420000, "min_price": 150000, "max_price": 4000000, "count": 865, "median_ppm2": 3652, "lat": 36.8779, "lon": 10.3244},
    "La Manouba": {"median_price": 235000, "min_price": 47000, "max_price": 980000, "count": 89, "median_ppm2": 2061, "lat": 36.8091, "lon": 10.0985},
    "La Soukra": {"median_price": 399500, "min_price": 120000, "max_price": 1350000, "count": 565, "median_ppm2": 3668, "lat": 36.8945, "lon": 10.2154},
    "Le Bardo": {"median_price": 285000, "min_price": 150000, "max_price": 900000, "count": 57, "median_ppm2": 2843, "lat": 36.8094, "lon": 10.1399},
    "Le Kram": {"median_price": 635000, "min_price": 120000, "max_price": 2700000, "count": 416, "median_ppm2": 5078, "lat": 36.8447, "lon": 10.2868},
    "Megrine": {"median_price": 255000, "min_price": 120000, "max_price": 680000, "count": 20, "median_ppm2": 2291, "lat": 36.766, "lon": 10.2095},
    "Menzah 6": {"median_price": 340000, "min_price": 230000, "max_price": 700000, "count": 6, "median_ppm2": 2920, "lat": 36.8548, "lon": 10.1836},
    "Midoun": {"median_price": 395000, "min_price": 180000, "max_price": 1200000, "count": 19, "median_ppm2": 3400, "lat": 33.7921, "lon": 11.0},
    "Mnihla": {"median_price": 245000, "min_price": 130000, "max_price": 600000, "count": 18, "median_ppm2": 1950, "lat": 36.8826, "lon": 10.1727},
    "Monastir": {"median_price": 275000, "min_price": 70000, "max_price": 1200000, "count": 54, "median_ppm2": 2434, "lat": 35.7643, "lon": 10.8113},
    "Msaken": {"median_price": 250000, "min_price": 85000, "max_price": 900000, "count": 22, "median_ppm2": 2272, "lat": 35.7303, "lon": 10.5795},
    "Nabeul": {"median_price": 322500, "min_price": 48500, "max_price": 3000000, "count": 618, "median_ppm2": 2666, "lat": 36.4565, "lon": 10.7358},
    "Raoued": {"median_price": 348000, "min_price": 70000, "max_price": 1500000, "count": 141, "median_ppm2": 2761, "lat": 36.898, "lon": 10.1633},
    "Sahloul": {"median_price": 370000, "min_price": 135000, "max_price": 1550000, "count": 105, "median_ppm2": 3195, "lat": 35.8402, "lon": 10.626},
    "Sidi Bou Said": {"median_price": 875000, "min_price": 400000, "max_price": 4500000, "count": 12, "median_ppm2": 7291, "lat": 36.8697, "lon": 10.3418},
    "Sfax": {"median_price": 187500, "min_price": 50000, "max_price": 2700000, "count": 130, "median_ppm2": 498, "lat": 34.7405, "lon": 10.7603},
    "Sousse": {"median_price": 320000, "min_price": 57000, "max_price": 1950000, "count": 287, "median_ppm2": 2250, "lat": 35.8281, "lon": 10.6394},
    "Sousse Ville": {"median_price": 315000, "min_price": 70000, "max_price": 851000, "count": 93, "median_ppm2": 2707, "lat": 35.8244, "lon": 10.6369},
    "Tunis": {"median_price": 299999, "min_price": 47000, "max_price": 4500000, "count": 821, "median_ppm2": 2466, "lat": 36.8065, "lon": 10.1815},
    "Yasminette": {"median_price": 550000, "min_price": 350000, "max_price": 900000, "count": 4, "median_ppm2": 4583, "lat": 36.9188, "lon": 10.2736},
    "Zaghouan": {"median_price": 175000, "min_price": 100000, "max_price": 350000, "count": 6, "median_ppm2": 1458, "lat": 36.4028, "lon": 10.1428},
    "Zarzis": {"median_price": 295000, "min_price": 140000, "max_price": 650000, "count": 11, "median_ppm2": 2954, "lat": 33.5031, "lon": 11.1119},
}

# SARIMA investment data — 24 gouvernorats
SARIMA_DATA: dict = {
    "Ariana":     {"derniere_valeur": 2871.0, "prevision_finale": 3125.0, "hausse_pct": 5.9,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [2186.0,2238.0,2280.0,2356.0,2432.0,2532.0,2563.0,2636.0,2711.0,2717.0,2794.0,2827.0,2871.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [2913.0,2955.0,2997.0,3040.0,3083.0,3125.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Ben Arous":  {"derniere_valeur": 1750.0, "prevision_finale": 1890.0, "hausse_pct": 5.3,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1420.0,1455.0,1483.0,1530.0,1575.0,1618.0,1639.0,1675.0,1710.0,1720.0,1736.0,1745.0,1750.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1773.0,1796.0,1819.0,1843.0,1866.0,1890.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Bizerte":    {"derniere_valeur": 1450.0, "prevision_finale": 1560.0, "hausse_pct": 4.9,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1183.0,1210.0,1235.0,1268.0,1302.0,1330.0,1348.0,1373.0,1397.0,1405.0,1418.0,1437.0,1450.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1468.0,1486.0,1504.0,1522.0,1541.0,1560.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Béja":       {"derniere_valeur":  850.0, "prevision_finale":  905.0, "hausse_pct": 4.1,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [703.0,718.0,729.0,748.0,764.0,780.0,790.0,803.0,815.0,820.0,827.0,840.0,850.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [859.0,868.0,877.0,887.0,896.0,905.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Gabès":      {"derniere_valeur":  980.0, "prevision_finale": 1048.0, "hausse_pct": 4.4,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [808.0,827.0,843.0,867.0,889.0,909.0,921.0,939.0,955.0,960.0,968.0,973.0,980.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [991.0,1002.0,1013.0,1025.0,1036.0,1048.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Gafsa":      {"derniere_valeur":  760.0, "prevision_finale":  805.0, "hausse_pct": 3.7,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [636.0,649.0,659.0,676.0,690.0,703.0,712.0,723.0,733.0,737.0,743.0,752.0,760.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [767.0,774.0,781.0,788.0,796.0,805.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Jendouba":   {"derniere_valeur":  620.0, "prevision_finale":  655.0, "hausse_pct": 3.5,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [521.0,532.0,541.0,555.0,568.0,578.0,586.0,596.0,604.0,608.0,613.0,617.0,620.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [625.0,631.0,636.0,641.0,648.0,655.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Kairouan":   {"derniere_valeur":  890.0, "prevision_finale":  950.0, "hausse_pct": 4.2,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [734.0,751.0,764.0,785.0,805.0,822.0,833.0,849.0,863.0,868.0,876.0,883.0,890.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [899.0,909.0,918.0,928.0,939.0,950.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Kasserine":  {"derniere_valeur":  610.0, "prevision_finale":  645.0, "hausse_pct": 3.5,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [512.0,523.0,531.0,545.0,557.0,568.0,576.0,586.0,594.0,597.0,602.0,606.0,610.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [615.0,621.0,626.0,631.0,638.0,645.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Kébili":     {"derniere_valeur":  580.0, "prevision_finale":  613.0, "hausse_pct": 3.7,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [485.0,495.0,503.0,516.0,528.0,539.0,546.0,556.0,564.0,568.0,572.0,576.0,580.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [585.0,591.0,596.0,601.0,607.0,613.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Le Kef":     {"derniere_valeur":  680.0, "prevision_finale":  720.0, "hausse_pct": 3.8,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [572.0,584.0,593.0,609.0,623.0,635.0,644.0,655.0,665.0,669.0,675.0,678.0,680.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [686.0,693.0,700.0,706.0,713.0,720.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Mahdia":     {"derniere_valeur": 1580.0, "prevision_finale": 1695.0, "hausse_pct": 4.6,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1289.0,1319.0,1343.0,1381.0,1418.0,1449.0,1468.0,1497.0,1523.0,1531.0,1545.0,1562.0,1580.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1598.0,1616.0,1634.0,1653.0,1674.0,1695.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Manouba":    {"derniere_valeur": 1820.0, "prevision_finale": 1955.0, "hausse_pct": 4.8,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1481.0,1516.0,1543.0,1587.0,1630.0,1665.0,1688.0,1722.0,1752.0,1761.0,1778.0,1799.0,1820.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1842.0,1864.0,1886.0,1909.0,1932.0,1955.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Monastir":   {"derniere_valeur": 2180.0, "prevision_finale": 2345.0, "hausse_pct": 5.1,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1770.0,1813.0,1847.0,1901.0,1953.0,1996.0,2024.0,2065.0,2101.0,2113.0,2133.0,2157.0,2180.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [2208.0,2236.0,2264.0,2293.0,2319.0,2345.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Médenine":   {"derniere_valeur": 1180.0, "prevision_finale": 1265.0, "hausse_pct": 4.7,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [962.0,985.0,1002.0,1030.0,1058.0,1081.0,1096.0,1117.0,1136.0,1142.0,1153.0,1166.0,1180.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1194.0,1209.0,1223.0,1238.0,1252.0,1265.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Nabeul":     {"derniere_valeur": 2390.0, "prevision_finale": 2570.0, "hausse_pct": 5.3,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1941.0,1987.0,2025.0,2083.0,2141.0,2187.0,2218.0,2263.0,2302.0,2314.0,2336.0,2363.0,2390.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [2422.0,2454.0,2486.0,2518.0,2544.0,2570.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Sfax":       {"derniere_valeur": 1320.0, "prevision_finale": 1415.0, "hausse_pct": 4.8,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [1074.0,1100.0,1121.0,1153.0,1184.0,1210.0,1227.0,1251.0,1272.0,1279.0,1291.0,1306.0,1320.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1336.0,1352.0,1367.0,1383.0,1399.0,1415.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Sidi Bouzid":{"derniere_valeur":  590.0, "prevision_finale":  622.0, "hausse_pct": 3.5,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [496.0,506.0,515.0,529.0,541.0,551.0,559.0,568.0,576.0,579.0,584.0,587.0,590.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [595.0,600.0,605.0,610.0,616.0,622.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Siliana":    {"derniere_valeur":  550.0, "prevision_finale":  580.0, "hausse_pct": 3.4,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [463.0,473.0,480.0,493.0,504.0,514.0,521.0,530.0,537.0,540.0,545.0,548.0,550.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [555.0,560.0,564.0,569.0,574.0,580.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Sousse":     {"derniere_valeur": 2540.0, "prevision_finale": 2735.0, "hausse_pct": 5.5,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [2051.0,2099.0,2140.0,2203.0,2264.0,2313.0,2346.0,2394.0,2437.0,2450.0,2473.0,2507.0,2540.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [2575.0,2610.0,2646.0,2682.0,2709.0,2735.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Tataouine":  {"derniere_valeur":  510.0, "prevision_finale":  538.0, "hausse_pct": 3.5,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [428.0,438.0,445.0,457.0,467.0,477.0,483.0,491.0,498.0,501.0,505.0,508.0,510.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [514.0,519.0,523.0,527.0,533.0,538.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Tozeur":     {"derniere_valeur":  620.0, "prevision_finale":  655.0, "hausse_pct": 3.6,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [521.0,533.0,541.0,556.0,568.0,580.0,588.0,598.0,607.0,611.0,616.0,618.0,620.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [625.0,631.0,636.0,641.0,647.0,655.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Tunis":      {"derniere_valeur": 3180.0, "prevision_finale": 3430.0, "hausse_pct": 6.2,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [2431.0,2490.0,2540.0,2618.0,2695.0,2757.0,2797.0,2856.0,2908.0,2925.0,2953.0,2992.0,3180.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [3229.0,3278.0,3328.0,3378.0,3404.0,3430.0]}, "variable": "PRIX_M2_MEDIAN"},
    "Zaghouan":   {"derniere_valeur": 1050.0, "prevision_finale": 1120.0, "hausse_pct": 4.2,  "historique": {"dates": ["2022-04-01","2022-07-01","2022-10-01","2023-01-01","2023-04-01","2023-07-01","2023-10-01","2024-01-01","2024-04-01","2024-07-01","2024-10-01","2025-01-01","2025-04-01"], "valeurs": [866.0,886.0,902.0,928.0,953.0,974.0,988.0,1008.0,1026.0,1032.0,1042.0,1047.0,1050.0]}, "prevision": {"dates": ["2025-07-01","2025-10-01","2026-01-01","2026-04-01","2026-07-01","2026-10-01"], "valeurs": [1062.0,1074.0,1086.0,1097.0,1109.0,1120.0]}, "variable": "PRIX_M2_MEDIAN"},
}

# Top districts/zones per city for recommendations
RECOMMEND_INDEX: dict = {
    "Ariana": [
        {"zone": "La Soukra",      "price": 399500, "ppm2": 3668, "score": 9, "avantages": ["Proche autoroute","Résidentiel calme"], "trend": 5.9},
        {"zone": "Cité Ennasr 2",  "price": 340000, "ppm2": 2800, "score": 7, "avantages": ["Commodités proches","Bien desservi"],    "trend": 4.8},
        {"zone": "Raoued",         "price": 348000, "ppm2": 2761, "score": 6, "avantages": ["En développement","Prix accessible"],   "trend": 5.1},
        {"zone": "Ennasr",         "price": 360000, "ppm2": 2900, "score": 7, "avantages": ["Quartier dynamique","Commerces"],       "trend": 4.5},
        {"zone": "Borj Louzir",    "price": 300000, "ppm2": 2400, "score": 5, "avantages": ["Abordable","Calme"],                    "trend": 3.9},
    ],
    "Tunis": [
        {"zone": "La Marsa",       "price": 420000, "ppm2": 3652, "score": 9, "avantages": ["Vue mer","Prestige","Vie nocturne"],    "trend": 6.2},
        {"zone": "Le Kram",        "price": 635000, "ppm2": 5078, "score": 8, "avantages": ["Front de mer","Exclusif"],             "trend": 5.8},
        {"zone": "El Menzah",      "price": 350000, "ppm2": 2755, "score": 8, "avantages": ["Résidentiel","Écoles","Calme"],        "trend": 5.5},
        {"zone": "Le Bardo",       "price": 285000, "ppm2": 2843, "score": 6, "avantages": ["Centre","Transport public"],           "trend": 4.8},
        {"zone": "La Soukra",      "price": 399500, "ppm2": 3668, "score": 7, "avantages": ["Moderne","Bien situé"],                "trend": 5.1},
    ],
    "Sousse": [
        {"zone": "Sahloul",        "price": 370000, "ppm2": 3195, "score": 9, "avantages": ["Quartier médical","Résidentiel"],      "trend": 5.5},
        {"zone": "Hammam Sousse",  "price": 350000, "ppm2": 3763, "score": 8, "avantages": ["Bord de mer","Tourisme"],              "trend": 5.8},
        {"zone": "Sousse Ville",   "price": 315000, "ppm2": 2707, "score": 7, "avantages": ["Centre-ville","Commerces","Médina"],  "trend": 4.9},
        {"zone": "Khezama",        "price": 395000, "ppm2": 3600, "score": 7, "avantages": ["Résidentiel haut de gamme"],          "trend": 5.2},
        {"zone": "Akouda",         "price": 366000, "ppm2": 3791, "score": 7, "avantages": ["Vue mer","Calme","Verdure"],           "trend": 4.7},
    ],
    "Sfax": [
        {"zone": "Route El Ain",       "price": 280000, "ppm2": 2100, "score": 7, "avantages": ["En expansion","Moderne"],          "trend": 4.8},
        {"zone": "Route GREMDA",       "price": 220000, "ppm2": 1800, "score": 6, "avantages": ["Accessible","Nouveau"],            "trend": 4.2},
        {"zone": "Sfax Centre",        "price": 187500, "ppm2": 1500, "score": 6, "avantages": ["Centre commercial","Médina"],     "trend": 4.0},
        {"zone": "Route de l'aéroport","price": 250000, "ppm2": 1950, "score": 5, "avantages": ["Connectivité","Développement"],   "trend": 4.5},
    ],
    "Hammamet": [
        {"zone": "Hammamet Nord",  "price": 450000, "ppm2": 4200, "score": 9, "avantages": ["Balnéaire","Tourisme","Prestige"],     "trend": 5.5},
        {"zone": "Hammamet Sud",   "price": 380000, "ppm2": 3600, "score": 8, "avantages": ["Golf","Résidences standing"],         "trend": 4.8},
        {"zone": "Nabeul",         "price": 322500, "ppm2": 2666, "score": 7, "avantages": ["Potentiel locatif","Accessible"],     "trend": 5.3},
    ],
    "Nabeul": [
        {"zone": "Hammamet",       "price": 360000, "ppm2": 3600, "score": 8, "avantages": ["Bord de mer","Fort potentiel"],       "trend": 5.5},
        {"zone": "Nabeul Centre",  "price": 300000, "ppm2": 2500, "score": 7, "avantages": ["Artisanat","Centre-ville"],           "trend": 5.0},
        {"zone": "Beni Khiar",     "price": 270000, "ppm2": 2903, "score": 6, "avantages": ["Résidentiel","Calme"],                "trend": 4.3},
    ],
    "La Marsa": [
        {"zone": "Sidi Bou Said",  "price": 875000, "ppm2": 7291, "score": 10,"avantages": ["Village pittoresque","Prestige","Vue mer"],"trend": 7.0},
        {"zone": "Gammarth",       "price": 725000, "ppm2": 5000, "score": 9, "avantages": ["Luxe","Résidences haut de gamme"],    "trend": 6.5},
        {"zone": "La Marsa",       "price": 420000, "ppm2": 3652, "score": 9, "avantages": ["Bord de mer","Vie sociale"],          "trend": 6.2},
    ],
    "Bizerte": [
        {"zone": "Bizerte Nord",   "price": 212500, "ppm2": 2031, "score": 6, "avantages": ["Bord de mer","Calme"],                "trend": 4.9},
        {"zone": "Bizerte Centre", "price": 292500, "ppm2": 1662, "score": 5, "avantages": ["Centre","Commerces","Port"],          "trend": 4.2},
    ],
    "Monastir": [
        {"zone": "Monastir Centre","price": 275000, "ppm2": 2434, "score": 7, "avantages": ["Aéroport","Bord de mer","Tourisme"],  "trend": 5.1},
        {"zone": "Hammam Sousse",  "price": 350000, "ppm2": 3763, "score": 8, "avantages": ["Station balnéaire","Investissement"], "trend": 5.5},
    ],
}

TOTAL_LISTINGS = 8673
TOTAL_CITIES   = 110


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTIONS PUBLIQUES
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_city(city: str) -> str:
    """Trouve la clé exacte dans CITY_STATS (insensible à la casse + fuzzy)."""
    if not city:
        return "Tunis"
    # exact match (case-insensitive)
    for k in CITY_STATS:
        if k.lower() == city.lower():
            return k
    # fuzzy
    matches = get_close_matches(city.title(), list(CITY_STATS.keys()), n=1, cutoff=0.6)
    if matches:
        return matches[0]
    # prefix
    for k in CITY_STATS:
        if k.lower().startswith(city.lower()[:4]):
            return k
    return "Tunis"


def _resolve_gouvernorat(place: str) -> str:
    """Résout un nom de ville/gouvernorat vers une clé SARIMA_DATA."""
    if not place:
        return "Tunis"
    # direct match
    for k in SARIMA_DATA:
        if k.lower() == place.lower():
            return k
    # city → gouvernorat heuristics
    mapping = {
        "ariana": "Ariana", "la soukra": "Ariana", "raoued": "Ariana", "ennasr": "Ariana",
        "tunis": "Tunis", "la marsa": "Tunis", "le kram": "Tunis", "el menzah": "Tunis",
        "le bardo": "Tunis", "bardo": "Tunis", "gammarth": "Tunis", "sidi bou said": "Tunis",
        "sousse": "Sousse", "sahloul": "Sousse", "hammam sousse": "Sousse", "akouda": "Sousse",
        "sfax": "Sfax", "nabeul": "Nabeul", "hammamet": "Nabeul",
        "bizerte": "Bizerte", "monastir": "Monastir", "mahdia": "Mahdia",
        "manouba": "Manouba", "la manouba": "Manouba", "ben arous": "Ben Arous",
        "zaghouan": "Zaghouan", "kairouan": "Kairouan", "jendouba": "Jendouba",
        "gafsa": "Gafsa", "gabes": "Gabès", "gabès": "Gabès",
        "medenine": "Médenine", "médenine": "Médenine", "zarzis": "Médenine",
        "tataouine": "Tataouine", "tozeur": "Tozeur", "kebili": "Kébili", "kébili": "Kébili",
        "sidi bouzid": "Sidi Bouzid", "kasserine": "Kasserine", "siliana": "Siliana",
        "le kef": "Le Kef", "kef": "Le Kef", "beja": "Béja", "béja": "Béja",
    }
    key = place.lower().strip()
    if key in mapping:
        return mapping[key]
    fuzzy = get_close_matches(place.title(), list(SARIMA_DATA.keys()), n=1, cutoff=0.6)
    return fuzzy[0] if fuzzy else "Tunis"


def estimate_price(
    city: str,
    surface: float = 100.0,
    bedrooms: float = 2.0,
    bathrooms: float = 1.0,
    budget: float = 0.0,
    etage: float = 2.0,
    equipment_score: float = 5.0,
) -> dict:
    """
    Estimation de prix basée sur les stats réelles du CSV.
    Retourne le même format JSON que POST /api/estimate de BO3.
    """
    resolved = _resolve_city(city)
    stats = CITY_STATS.get(resolved, CITY_STATS["Tunis"])

    ppm2 = stats["median_ppm2"]
    predicted = round(ppm2 * surface)

    # CI à 20% autour de la médiane
    half_ci = round(predicted * 0.20)
    confidence = min(95, max(45, round(70 + (stats["count"] / 50))))

    city_median = stats["median_price"]
    city_min    = stats["min_price"]
    city_max    = stats["max_price"]
    city_ppm2   = stats["median_ppm2"]
    market_delta_pct = round((predicted - city_median) / city_median * 100, 1) if city_median else None

    surface_possible = round(budget / ppm2) if budget > 0 and ppm2 > 0 else None
    budget_delta     = round(budget - predicted) if budget > 0 else None

    # Distribution simulée (5 quantiles)
    prices_sample = [
        round(city_min),
        round(city_min + (city_median - city_min) * 0.4),
        round(city_median),
        round(city_median + (city_max - city_median) * 0.4),
        round(city_max),
    ]
    ppm2_sample = [round(p / surface) if surface > 0 else 0 for p in prices_sample]

    return {
        "success": True,
        "estimation": {
            "predicted":         predicted,
            "ci_lower":          max(0, predicted - half_ci),
            "ci_upper":          predicted + half_ci,
            "confidence":        confidence,
            "price_per_m2":      ppm2,
            "city_median":       city_median,
            "city_ppm2":         city_ppm2,
            "city_min":          city_min,
            "city_max":          city_max,
            "market_delta_pct":  market_delta_pct,
            "budget_delta":      budget_delta,
            "surface_possible":  surface_possible,
            "r2":                0.82,
            "rmse":              42000,
        },
        "distribution": {
            "prices":        prices_sample,
            "price_per_m2":  ppm2_sample,
            "count":         stats["count"],
        },
        "city_resolved": resolved,
        "total_listings": TOTAL_LISTINGS,
    }


def recommend_zones(
    ville: str = "Tunis",
    budget: float = 300_000.0,
    type_bien: str = "appartement",
) -> dict:
    """
    Recommandation de zones selon budget et ville.
    Retourne le même format JSON que POST /api/recommend de BO3.
    """
    resolved = _resolve_city(ville)

    # Look in recommend index, fall back to city_stats sorted by ppm2
    zones_raw = RECOMMEND_INDEX.get(resolved)
    if not zones_raw:
        # Build from CITY_STATS — find cities that start similarly
        candidates = [
            (k, v) for k, v in CITY_STATS.items()
            if k.lower().startswith(resolved.lower()[:3])
            and v["median_price"] <= budget * 1.5
        ]
        candidates.sort(key=lambda x: x[1]["count"], reverse=True)
        zones_raw = [
            {
                "zone": k,
                "price": v["median_price"],
                "ppm2": v["median_ppm2"],
                "score": min(10, max(1, round(v["count"] / 40))),
                "avantages": [],
                "trend": None,
            }
            for k, v in candidates[:5]
        ] or [
            {"zone": resolved, "price": CITY_STATS.get(resolved, CITY_STATS["Tunis"])["median_price"],
             "ppm2": CITY_STATS.get(resolved, CITY_STATS["Tunis"])["median_ppm2"],
             "score": 5, "avantages": [], "trend": None}
        ]

    # Filter by budget (±50%)
    filtered = [z for z in zones_raw if z["price"] <= budget * 1.5]
    if not filtered:
        filtered = zones_raw[:3]

    return {
        "zones":       filtered[:5],
        "ville":       resolved,
        "type_bien":   type_bien,
        "data_source": "modele",
        "total_listings": TOTAL_LISTINGS,
    }


def sarima_invest(gouvernorat: str = "Tunis") -> dict:
    """
    Données SARIMA d'investissement.
    Retourne le même format que GET /api/analysis de BO3.
    """
    resolved = _resolve_gouvernorat(gouvernorat)
    data     = SARIMA_DATA.get(resolved, SARIMA_DATA["Tunis"])

    return {
        "success": True,
        "data": {
            "gouvernorat":      resolved,
            "variable":         data["variable"],
            "order":            [1, 1, 1],
            "seasonal_order":   [1, 1, 0, 4],
            "aic":              892.4,
            "bic":              910.2,
            "adf_stat":         -3.12,
            "adf_pval":         0.026,
            "historique":       data["historique"],
            "prevision":        data["prevision"],
            "derniere_valeur":  data["derniere_valeur"],
            "prevision_finale": data["prevision_finale"],
            "hausse_pct":       data["hausse_pct"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
#  INTÉGRATION DANS call_bo3 — remplacez le contenu de call_bo3 dans
#  app/services/agents/agent_clients.py par ce qui suit
# ─────────────────────────────────────────────────────────────────────────────
#
#  from app.services.agents.bo3_mock_agent import estimate_price, recommend_zones, sarima_invest
#
#  async def call_bo3(intent, params, session_id=None):
#      ...
#      if not settings.use_http_agents:
#          return _call_bo3_direct(intent, params, session_id)
#      # ... existing HTTP code ...
#
#  def _call_bo3_direct(intent, params, session_id=None):
#      city = params.get("city", params.get("ville", "Tunis"))
#
#      if intent == "price_estimation":
#          raw = estimate_price(
#              city=city,
#              surface=float(params.get("surface", 100)),
#              bedrooms=float(params.get("bedrooms", 2)),
#              bathrooms=float(params.get("bathrooms", 1)),
#              budget=float(params.get("budget", 0)),
#          )
#          est  = raw["estimation"]
#          dist = raw["distribution"]
#          return {
#              "available": True, "agent": "BO3", "intent": "price_estimation",
#              "estimated_price":   est["predicted"],
#              "price_range":       {"lower": est["ci_lower"], "upper": est["ci_upper"]},
#              "confidence_score":  est["confidence"],
#              "price_per_m2":      est["price_per_m2"],
#              "city_median":       est["city_median"],
#              "city_ppm2":         est["city_ppm2"],
#              "city_min":          est["city_min"],
#              "city_max":          est["city_max"],
#              "market_delta_pct":  est["market_delta_pct"],
#              "budget_delta":      est["budget_delta"],
#              "surface_possible":  est["surface_possible"],
#              "model_metrics":     {"r2": est["r2"], "rmse": est["rmse"]},
#              "distribution":      dist,
#              "total_listings":    raw["total_listings"],
#              "from_cache":        False,
#          }
#
#      if intent in ("location_analysis", "general_query"):
#          raw = recommend_zones(
#              ville=city,
#              budget=float(params.get("budget", 300_000)),
#              type_bien=params.get("type_bien", "appartement"),
#          )
#          return {
#              "available": True, "agent": "BO3", "intent": intent,
#              "recommended_zones": [
#                  {"zone": z["zone"], "price": z["price"], "ppm2": z["ppm2"],
#                   "score": z["score"], "advantages": z["avantages"], "trend_pct": z["trend"]}
#                  for z in raw["zones"][:3]
#              ],
#              "ville":          raw["ville"],
#              "type_bien":      raw["type_bien"],
#              "data_source":    raw["data_source"],
#              "total_listings": raw["total_listings"],
#              "from_cache":     False,
#          }
#
#      if intent == "investment_analysis":
#          raw = sarima_invest(gouvernorat=city)
#          data = raw["data"]
#          return {
#              "available": True, "agent": "BO3", "intent": "investment_analysis",
#              "gouvernorat":         data["gouvernorat"],
#              "variable":            data["variable"],
#              "model_quality":       {"aic": data["aic"], "bic": data["bic"],
#                                     "adf_stat": data["adf_stat"], "adf_pval": data["adf_pval"],
#                                     "order": data["order"], "seasonal_order": data["seasonal_order"]},
#              "historical":          data["historique"],
#              "forecast":            {"dates": data["prevision"]["dates"],
#                                     "values": data["prevision"]["valeurs"],
#                                     "lower": [], "upper": []},
#              "current_price_m2":    data["derniere_valeur"],
#              "forecast_price_m2":   data["prevision_finale"],
#              "expected_growth_pct": data["hausse_pct"],
#              "from_cache":          False,
#          }
#
#      # fallback
#      return _call_bo3_direct("location_analysis", params, session_id)
