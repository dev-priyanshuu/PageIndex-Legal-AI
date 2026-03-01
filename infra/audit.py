from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class AuditEvent:
    timestamp: str
    event_type: str
    actor: str
    document_id: str | None
    details: dict[str, str]


AUDIT_LOG: list[AuditEvent] = []


def log_event(event_type: str, actor: str, document_id: str | None, details: dict[str, str]) -> None:
    AUDIT_LOG.append(
        AuditEvent(
            timestamp=datetime.now(UTC).isoformat(),
            event_type=event_type,
            actor=actor,
            document_id=document_id,
            details=details,
        )
    )

