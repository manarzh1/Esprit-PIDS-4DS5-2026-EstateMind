"""app/api/v1/endpoints/report.py — PDF Report generation endpoint."""
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.models.schemas import ReportCreateRequest, ReportResponse
from app.services.report.pdf_generator import generate_pdf_report

router = APIRouter()

# Stockage en mémoire des rapports générés (session)
_reports: dict[str, str] = {}


class DirectReportRequest(BaseModel):
    session_id: str | None = None
    report_type: str = "general"
    agent_data: dict[str, Any] = {}
    language: str = "fr"


@router.post("/report/generate", tags=["Reports"])
async def generate_report_direct(req: DirectReportRequest):
    """
    Génère un rapport PDF à partir des données brutes d'un agent.
    Utilisé par le bouton 'Télécharger rapport PDF' du frontend.
    Retourne directement le fichier PDF en réponse.
    """
    sid = req.session_id or str(uuid.uuid4())
    try:
        path = await generate_pdf_report(
            session_id=sid,
            report_type=req.report_type,
            agent_data=req.agent_data,
            language=req.language,
        )
        report_id = uuid.uuid4().hex[:8]
        _reports[report_id] = path
        return FileResponse(
            path=path,
            media_type="application/pdf",
            filename=f"estate_mind_{req.report_type}_{report_id}.pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur génération PDF : {e}")


@router.post("/report", response_model=ReportResponse, tags=["Reports"])
async def create_report(req: ReportCreateRequest, db: AsyncSession = Depends(get_db)):
    """Crée un rapport et retourne l'URL de téléchargement (ancien endpoint)."""
    from app.services.agents.agent_clients import call_bo2
    agent_data = await call_bo2(
        intent="report_generation",
        params={"city": "Tunis", "budget": 300_000},
        session_id=str(req.session_id),
    )
    path = await generate_pdf_report(req.session_id, req.report_type, agent_data, req.language)
    report_id = uuid.uuid4()
    _reports[str(report_id)] = path
    return ReportResponse(
        report_id=report_id,
        session_id=req.session_id,
        report_type=req.report_type,
        download_url=f"/api/v1/report/{report_id}/download",
        created_at=datetime.now(),
        summary=f"Rapport {req.report_type} généré — {os.path.basename(path)}",
    )


@router.get("/report/{report_id}/download", tags=["Reports"])
async def download_report(report_id: str):
    """Télécharge un rapport PDF généré précédemment."""
    path = _reports.get(str(report_id))
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Rapport non trouvé ou expiré.")
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"estate_mind_{report_id}.pdf",
    )
