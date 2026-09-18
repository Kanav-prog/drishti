"""Audit logging utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from typing import Any

from backend.db.models import AuditEvent
from backend.db.session import db_session

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuditRecord:
    trace_id: str
    actor: str
    action: str
    resource: str
    status_code: int
    details: dict[str, Any]


def write_audit_event(record: AuditRecord) -> None:
    """Persist an audit event to DB and mirror to logs."""
    try:
        with db_session() as db:
            db.add(
                AuditEvent(
                    trace_id=record.trace_id,
                    actor=record.actor,
                    action=record.action,
                    resource=record.resource,
                    status_code=record.status_code,
                    details=json.dumps(record.details, default=str),
                )
            )
        logger.info("AUDIT %s", json.dumps(asdict(record), default=str))
    except Exception as exc:
        logger.warning("Failed to persist audit event: %s", exc)
