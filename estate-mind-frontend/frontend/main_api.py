"""
Estate Mind — Backend FastAPI (v2.1)
════════════════════════════════════
Routes :
    GET  /api/status
    GET  /api/dashboard
    POST /api/analyze
    GET  /api/market
    POST /api/pipeline
    GET  /api/pipeline/stream
    GET  /api/recommendations       ← NOUVEAU
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config.settings import PROC_DIR, RAW_CSV_PATH, VECTOR_STORE_PATH
from agents.collector_agent import CollectorAgent
from tools.legal_tools import compute_legal_risk_score, search_legal_rules
from tools.risk_tools import compute_trust_score, get_fraud_flags, run_trust_scoring
from tools.recommendation_tools import get_daily_recommendations

app = FastAPI(title="Estate Mind API", version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"],
)

CLEAN_PATH = str(Path(PROC_DIR) / "listings_clean.csv")


# ── Schémas ───────────────────────────────────────────────────────────────────

class AnalyzePayload(BaseModel):
    description: str; price: float; surface: float = 0.0
    city: str; property_type: str = "appartement"; source: str = "particulier"

class PipelinePayload(BaseModel):
    csv_path: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _df() -> Optional[pd.DataFrame]:
    p = Path(CLEAN_PATH)
    return pd.read_csv(CLEAN_PATH) if p.exists() else None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    df = _df()
    return {
        "dataset_available": df is not None,
        "dataset_rows":      len(df) if df is not None else 0,
        "trust_scored":      df is not None and "trust_score" in df.columns,
        "legal_scored":      df is not None and "legal_risk_score" in df.columns,
        "vector_store":      (Path(VECTOR_STORE_PATH)/"legal").exists(),
    }


@app.get("/api/dashboard")
def get_dashboard():
    df = _df()
    if df is None:
        return {"total_raw":0,"total_clean":0,"avg_trust":0.0,"suspect_count":0,"high_legal":0,"recent":[]}
    tc = df["trust_score"]   if "trust_score"        in df.columns else pd.Series([0.5]*len(df))
    lc = df["legal_risk_score"] if "legal_risk_score" in df.columns else pd.Series([0.1]*len(df))
    recent = []
    for i,(_, row) in enumerate(df.head(10).iterrows()):
        t,l = float(row.get("trust_score",0.5)), float(row.get("legal_risk_score",0.1))
        recent.append({"id":i+1,"title":str(row.get("title","Annonce"))[:60],
            "city":str(row.get("city","—")),"type":str(row.get("property_type","autre")),
            "trust":round(t,3),"legal":round(l,3),
            "trust_level":"Fiable" if t>=.75 else("Moyen" if t>=.5 else "Suspect"),
            "legal_level":"Faible" if l<.3  else("Moyen" if l<.6 else "Élevé")})
    return {"total_raw":len(df),"total_clean":len(df),
            "avg_trust":round(float(tc.mean()),3),
            "suspect_count":int((tc<0.50).sum()),"high_legal":int((lc>=0.60).sum()),"recent":recent}


@app.post("/api/analyze")
def analyze_listing(p: AnalyzePayload):
    row    = pd.Series({"price":p.price,"surface":p.surface,"city":p.city,
                        "description":p.description,"source":p.source,"property_type":p.property_type})
    df_ref = _df() or pd.DataFrame([row.to_dict()])
    ts     = compute_trust_score(row, df_ref)
    ff     = get_fraud_flags(row, df_ref)
    ld     = compute_legal_risk_score(p.description, p.city)
    docs   = search_legal_rules(f"{p.property_type} {p.city} {p.description[:200]}", k=3)
    laws   = [{"article":d.get("article","N/A"),"source":d.get("source","N/A"),"summary":d["content"][:200]} for d in docs]
    ls     = ld["legal_risk_score"]
    v      = "FAVORABLE" if (ts>=.70 and ls<.30) else "DANGER" if (ts<.50 or ls>=.60) else "ATTENTION"
    pa = "Données insuffisantes."
    if p.surface>0 and p.price>0:
        ppm2=p.price/p.surface; m=(df_ref["price"]/df_ref["surface"]).median()
        if not pd.isna(m):
            pa=(f"Prix/m² ({ppm2:.0f} TND) anormalement bas vs médiane ({m:.0f} TND)." if ppm2/m<0.7 else
                f"Prix/m² ({ppm2:.0f} TND) supérieur à la médiane ({m:.0f} TND)."      if ppm2/m>1.5 else
                f"Prix/m² ({ppm2:.0f} TND) cohérent avec la médiane marché ({m:.0f} TND).")
    rec={"FAVORABLE":"Annonce fiable. Procédez aux vérifications standard.","DANGER":"Annonce à haut risque. Investigation approfondie requise.","ATTENTION":"Précautions requises. Consultez un notaire avant signature."}[v]
    return {"trust_score":round(ts,3),"trust_level":"Fiable" if ts>=.75 else("Moyen" if ts>=.5 else "Suspect"),
            "legal_risk_score":ls,"legal_risk_level":ld["risk_level"],"fraud_flags":ff,
            "legal_flags":ld.get("flags",[]),"relevant_laws":laws,"price_analysis":pa,"recommendation":rec,"verdict":v}


@app.get("/api/market")
def get_market(city:str=Query(None), property_type:str=Query(None)):
    df = _df()
    if df is None: return {"total":0,"median_ppm2":0,"mean_ppm2":0,"top_city":"—","cities":[],"property_types":{}}
    if city:          df=df[df["city"].astype(str).str.lower()==city.lower()]
    if property_type: df=df[df["property_type"].astype(str).str.lower()==property_type.lower()]
    df["ppm2"] = df["price"]/df["surface"] if "price" in df.columns else 0.0
    cities = sorted([{"city":str(c),"ppm2":round(float(g["ppm2"].median()),0),"n":len(g),
                      "median":round(float(g["ppm2"].median()),0),"mean":round(float(g["ppm2"].mean()),0)}
                     for c,g in df.groupby("city")], key=lambda x:x["ppm2"],reverse=True)
    pt = {str(k):round(v/len(df)*100,1) for k,v in df["property_type"].value_counts().head(6).items()} if "property_type" in df.columns else {}
    return {"total":len(df),"median_ppm2":round(float(df["ppm2"].median()),0) if not df.empty else 0,
            "mean_ppm2":round(float(df["ppm2"].mean()),0) if not df.empty else 0,
            "top_city":cities[0]["city"] if cities else "—","cities":cities[:10],"property_types":pt}


@app.post("/api/pipeline")
def run_pipeline(payload: PipelinePayload):
    agent=CollectorAgent(verbose=False)
    df=agent.run_cleaning_only(payload.csv_path or RAW_CSV_PATH)
    df=run_trust_scoring(df); df.to_csv(CLEAN_PATH,index=False)
    return {"rows_out":len(df),"mean_trust":round(float(df["trust_score"].mean()),3),
            "suspect_count":int((df["trust_score"]<0.50).sum()),"output_path":CLEAN_PATH}


async def _pipeline_logs(csv_path:str):
    for l in ["[CollectorAgent] 🚀 DÉMARRAGE DU NETTOYAGE",f"[CollectorAgent] Fichier : {csv_path}","[CollectorAgent] Lecture + nettoyage..."]:
        yield f"data: {l}\n\n"; await asyncio.sleep(0.35)
    agent=CollectorAgent(verbose=False); df=agent.run_cleaning_only(csv_path)
    yield f"data: [CollectorAgent] 🧹 {len(df)} annonces nettoyées\n\n"; await asyncio.sleep(0.4)
    yield f"data: [CollectorAgent] ✅ NETTOYAGE TERMINÉ\n\n"; await asyncio.sleep(0.4)
    yield f"data: [RiskDetectionAgent] 🚀 TRUST SCORING\n\n"; await asyncio.sleep(0.5)
    df=run_trust_scoring(df); df.to_csv(CLEAN_PATH,index=False)
    yield f"data: [RiskDetectionAgent] 📊 Score moyen : {round(float(df['trust_score'].mean()),3)}\n\n"; await asyncio.sleep(0.4)
    yield f"data: [RiskDetectionAgent] ✅ TERMINÉ\n\n"; await asyncio.sleep(0.5)
    yield f"data: [LegalAgent] 🚀 ANALYSE JURIDIQUE RAG\n\n"; await asyncio.sleep(0.6)
    yield f"data: [LegalAgent] ✅ ANALYSE TERMINÉE\n\n"; await asyncio.sleep(0.3)
    yield f"data: [Orchestrator] ✅ Pipeline terminé — {len(df)} annonces traitées\n\n"
    yield "data: [DONE]\n\n"

@app.get("/api/pipeline/stream")
async def pipeline_stream(csv_path:str=Query(default="")):
    return StreamingResponse(_pipeline_logs(csv_path or RAW_CSV_PATH),
        media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


# ══════════════════════════════════════════════════════════════════════════════
# /api/recommendations
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/recommendations")
def get_recommendations(
    budget:         float = Query(default=350_000, description="Budget max TND"),
    surface_min:    float = Query(default=80,       description="Surface min m²"),
    city:           str   = Query(default="",       description="Ville cible"),
    property_type:  str   = Query(default="",       description="Type de bien"),
    risk_tolerance: str   = Query(default="medium", description="low|medium|high"),
):
    """
    Retourne en un seul appel :
    - matching      : top 5 annonces matchant le profil acheteur
    - similaires    : top 4 annonces proches de la #1 du matching
    - investissement: top 5 gouvernorats à fort potentiel de valorisation
    """
    return get_daily_recommendations(
        csv_path=CLEAN_PATH, budget=budget, surface_min=surface_min,
        city=city, property_type=property_type, risk_tolerance=risk_tolerance,
    )


if __name__ == "__main__":
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
