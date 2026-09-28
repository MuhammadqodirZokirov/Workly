from sqlalchemy.ext.asyncio import AsyncSession

from workly.infrastructure.db.models import AuditLog, StateTransition


def record_transition(
    db: AsyncSession,
    object_type: str,
    object_id: int,
    from_state: str | None,
    to_state: str,
    actor_id: int | None,
    reason: str | None = None,
) -> None:
    db.add(
        StateTransition(
            object_type=object_type,
            object_id=object_id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            reason=reason,
        )
    )


def audit(
    db: AsyncSession,
    actor_id: int | None,
    action: str,
    object_type: str,
    object_id: int | None,
    *,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before=before,
            after=after,
            ip=ip,
        )
    )
