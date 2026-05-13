"""app/api/v1/endpoints/history.py — GET /api/v1/history"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.engine import get_db
from app.db.repositories.chat_repo import get_history
from app.models.schemas import HistoryResponse

router = APIRouter()

@router.get("/history", response_model=HistoryResponse, tags=["History (DSO3)"])
async def history(
    session_id: uuid.UUID | None = None,
    user_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await get_history(db, session_id=session_id, user_id=user_id, page=page, page_size=page_size)
