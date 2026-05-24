"""app/api/v1/endpoints/chat.py — POST /api/v1/chat"""
import json
from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.engine import get_db
from app.models.schemas import ChatRequest, ChatResponse
from app.services.orchestrator import run_pipeline
from app.core.logging import get_logger

router = APIRouter()
log = get_logger(__name__)


@router.post("/chat", status_code=status.HTTP_200_OK,
             summary="Envoyer une question en FR/EN/AR/Darija",
             tags=["Chat (DSO1)"])
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> Response:
    log.info("chat_request", query=request.query[:80], lang=request.language_override)
    result: ChatResponse = await run_pipeline(request=request, db=db)
    # Force UTF-8 encoding to prevent Arabic/special chars JSON errors
    content = json.dumps(result.model_dump(), ensure_ascii=False, default=str)
    return Response(content=content, media_type="application/json; charset=utf-8")
