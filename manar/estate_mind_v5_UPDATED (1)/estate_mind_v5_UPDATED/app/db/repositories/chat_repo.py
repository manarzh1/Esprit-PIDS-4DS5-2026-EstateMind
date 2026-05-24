"""app/db/repositories/chat_repo.py — CRUD historique BO6."""
import os, uuid
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.models.chat import ChatInteraction, ChatSession, ReportRecord
from app.models.schemas import HistoryResponse, InteractionSummary

log = get_logger(__name__)


async def get_or_create_session(db: AsyncSession, session_id, user_id=None):
    if session_id:
        r = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        s = r.scalar_one_or_none()
        if s: return s
    s = ChatSession(user_id=user_id)
    db.add(s)
    await db.flush()
    return s


async def save_interaction(
    db: AsyncSession, *, session, original_query, detected_language,
    translated_query, detected_intent, intent_confidence, intent_probabilities,
    routed_to_agent, agent_url, agent_raw_response, response_text,
    explanation_json, pipeline_steps_json, confidence_score, processing_ms,
    report_generated=False, report_path=None, error_message=None,
    is_darija=False, darija_terms=None, top_ngrams=None,
):
    cnt = await db.execute(select(func.count()).where(ChatInteraction.session_id == session.id))
    seq = (cnt.scalar() or 0) + 1
    i = ChatInteraction(
        session_id=session.id, sequence_number=seq, original_query=original_query,
        detected_language=detected_language, translated_query=translated_query,
        detected_intent=detected_intent, intent_confidence=intent_confidence,
        intent_probabilities=intent_probabilities, routed_to_agent=routed_to_agent,
        agent_url=agent_url, agent_raw_response=agent_raw_response,
        response_text=response_text, explanation_json=explanation_json,
        pipeline_steps_json=pipeline_steps_json, confidence_score=confidence_score,
        processing_ms=processing_ms, report_generated=report_generated,
        report_path=report_path, error_message=error_message,
        is_darija=is_darija, darija_terms=darija_terms, top_ngrams=top_ngrams,
    )
    db.add(i)
    await db.flush()
    return i


async def get_history(db: AsyncSession, session_id=None, user_id=None, page=1, page_size=20):
    """Retourne l'historique paginé des interactions."""
    offset = (page - 1) * page_size

    # Requête de base
    stmt = select(ChatInteraction).order_by(desc(ChatInteraction.created_at))
    count_stmt = select(func.count()).select_from(ChatInteraction)

    # Filtres optionnels
    if session_id:
        stmt = stmt.where(ChatInteraction.session_id == session_id)
        count_stmt = count_stmt.where(ChatInteraction.session_id == session_id)
    elif user_id:
        stmt = stmt.join(ChatSession).where(ChatSession.user_id == user_id)
        count_stmt = count_stmt.join(ChatSession).where(ChatSession.user_id == user_id)

    # Total
    total = (await db.execute(count_stmt)).scalar() or 0

    # Page courante
    stmt = stmt.offset(offset).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    # Construction des summaries — uniquement les champs définis dans InteractionSummary
    summaries = [
        InteractionSummary(
            interaction_id=row.id,
            session_id=row.session_id,
            original_query=row.original_query or "",
            detected_language=row.detected_language or "unknown",
            detected_intent=row.detected_intent,
            response_text=row.response_text,
            confidence_score=row.confidence_score,
            report_generated=row.report_generated or False,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return HistoryResponse(
        session_id=session_id,
        total=total,
        page=page,
        page_size=page_size,
        interactions=summaries,
    )


async def save_report(db: AsyncSession, *, session_id, report_type, file_path, parameters, summary):
    size = os.path.getsize(file_path) if os.path.exists(file_path) else None
    r = ReportRecord(session_id=session_id, report_type=report_type,
                     file_path=file_path, file_size_bytes=size,
                     parameters=parameters, summary=summary)
    db.add(r)
    await db.flush()
    return r


async def get_report(db: AsyncSession, report_id):
    r = await db.execute(select(ReportRecord).where(ReportRecord.id == report_id))
    return r.scalar_one_or_none()


async def list_reports(db: AsyncSession, session_id, limit=10):
    r = await db.execute(
        select(ReportRecord).where(ReportRecord.session_id == session_id)
        .order_by(desc(ReportRecord.created_at)).limit(limit)
    )
    return list(r.scalars().all())