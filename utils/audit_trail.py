# File: utils/audit_trail.py
# Fix: remove trailing whitespace

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from flask import current_app


def record_audit_event(
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """
    Write audit log entry.
    """

    current_app.logger.info(
        "audit_event",
        extra={
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
