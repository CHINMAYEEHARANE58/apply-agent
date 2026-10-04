import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.audit.models import AuditEvent
from app.audit.schemas import AuditEventCreate, AuditEventRead
from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import Page
from app.security.errors import not_found

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=Page[AuditEventRead])
def list_audit_events(current_user: CurrentUser, session: SessionDep, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> Page[AuditEventRead]:
    statement = select(AuditEvent).where(AuditEvent.user_id == current_user.id).order_by(AuditEvent.created_at.desc())
    total = session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.user_id == current_user.id)) or 0
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return Page(
        items=[AuditEventRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=AuditEventRead, status_code=status.HTTP_201_CREATED)
def create_audit_event(payload: AuditEventCreate, current_user: CurrentUser, session: SessionDep) -> AuditEvent:
    event = AuditEvent(
        user_id=current_user.id,
        event_type=payload.event_type,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        event_metadata=payload.metadata,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/{event_id}", response_model=AuditEventRead)
def get_audit_event(event_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> AuditEvent:
    event = session.scalar(select(AuditEvent).where(AuditEvent.id == event_id, AuditEvent.user_id == current_user.id))
    if event is None:
        raise not_found("Audit event")
    return event
