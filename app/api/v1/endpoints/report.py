"""app/api/v1/endpoints/report.py — PDF Report generation"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.engine import get_db
from app.models.schemas import ReportCreateRequest, ReportResponse
from app.services.report.pdf_generator import generate_pdf_report
from app.services.agents.agent_clients import call_bo2

router = APIRouter()

@router.post("/report", response_model=ReportResponse, tags=["Reports (DSO2)"])
async def create_report(req: ReportCreateRequest, db: AsyncSession = Depends(get_db)):
    agent_data, _ = await call_bo2(query=f"report {req.report_type}", session_id=str(req.session_id))
    path = await generate_pdf_report(req.session_id, req.report_type, agent_data, req.language)
    report_id = uuid.uuid4()
    return ReportResponse(
        report_id=report_id,
        session_id=req.session_id,
        report_type=req.report_type,
        download_url=f"/api/v1/report/{report_id}/download",
        created_at=datetime.now(),
        summary=f"Rapport {req.report_type} généré.",
    )

@router.get("/report/{report_id}/download", tags=["Reports (DSO2)"])
async def download_report(report_id: uuid.UUID):
    raise HTTPException(status_code=404, detail="Report not found or expired.")
