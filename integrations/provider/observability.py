# File: integrations/provider/observability.py
# Purpose: Enterprise Observability + Correlation + Retry Layer (Provider-Agnostic)
# Status: Enterprise Hardened
# Date: 2026-02-26
#
# NOTE:
# - Provider-agnostic (no vendor names)
# - Import-safe (no outbound calls)
# - Works even if Flask request context is not present (CLI/tasks/tests)
# - Emits correlation id in logs + response headers when wired in app.py

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Type, TypeVar

# Flask is optional here so the module is safe for non-request contexts
try:
    from flask import g, request  # type: ignore
except Exception:  # pragma: no cover
    g = None  # type: ignore
    request = None  # type: ignore

T = TypeVar("T")

logger = logging.getLogger("ledgerhaul.provider")


# ============================================================
# CONFIG
# ============================================================

def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float((os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        return default


PROVIDER_LOG_LEVEL = (os.getenv("PROVIDER_LOG_LEVEL") or "INFO").strip().upper()
if PROVIDER_LOG_LEVEL in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    logger.setLevel(getattr(logging, PROVIDER_LOG_LEVEL))

PROVIDER_RETRY_MAX_ATTEMPTS = max(
    1,
    _get_int("PROVIDER_RETRY_MAX_ATTEMPTS", 3),
)
PROVIDER_RETRY_BASE_DELAY_SEC = max(
    0.05,
    _get_float("PROVIDER_RETRY_BASE_DELAY_SEC", 0.35),
)
PROVIDER_RETRY_MAX_DELAY_SEC = max(
    PROVIDER_RETRY_BASE_DELAY_SEC,
    _get_float("PROVIDER_RETRY_MAX_DELAY_SEC", 4.0),
)
PROVIDER_RETRY_JITTER_SEC = max(
    0.0,
    _get_float("PROVIDER_RETRY_JITTER_SEC", 0.15),
)
PROVIDER_RETRY_ENABLED = not _truthy(
    os.getenv("PROVIDER_RETRY_DISABLED", "0"),
)


# ============================================================
# CORRELATION ID (REQUEST-SAFE)
# ============================================================

_CORRELATION_KEY = "correlation_id"
_HEADER_NAME = "X-Correlation-Id"


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


def _flask_has_context() -> bool:
    return request is not None and g is not None


def attach_correlation_id() -> str:
    """
    - If called in a Flask request context, stores correlation id in flask.g
    - If not in a request context, returns a generated id (no storage)
    """
    cid = None
    if _flask_has_context():
        try:
            hdr = request.headers.get(_HEADER_NAME)  # type: ignore[attr-defined]
            if isinstance(hdr, str) and hdr.strip():
                cid = hdr.strip()
        except Exception:
            cid = None

        if not cid:
            cid = generate_correlation_id()

        try:
            setattr(g, _CORRELATION_KEY, cid)  # type: ignore[attr-defined]
        except Exception:
            pass
        return cid

    return generate_correlation_id()


def get_correlation_id() -> Optional[str]:
    if _flask_has_context():
        try:
            v = getattr(g, _CORRELATION_KEY, None)  # type: ignore[attr-defined]
            return v if isinstance(v, str) and v.strip() else None
        except Exception:
            return None
    return None


def add_correlation_header(resp) -> Any:
    """
    Call this in app.after_request to emit correlation id to clients.
    Safe to no-op if not present.
    """
    try:
        cid = get_correlation_id()
        if cid:
            resp.headers.setdefault(_HEADER_NAME, cid)
    except Exception:
        pass
    return resp


# ============================================================
# STRUCTURED EVENT
# ============================================================

@dataclass(frozen=True)
class ProviderEvent:
    action: str
    company_id: int
    success: bool
    duration_ms: float
    detail: str = ""
    provider: str = ""
    status_code: Optional[int] = None
    error_type: str = ""


def log_provider_event(evt: ProviderEvent) -> None:
    payload: Dict[str, Any] = {
        "correlation_id": get_correlation_id(),
        "action": evt.action,
        "company_id": evt.company_id,
        "provider": evt.provider or None,
        "success": bool(evt.success),
        "duration_ms": round(float(evt.duration_ms), 2),
        "detail": evt.detail or None,
        "status_code": evt.status_code,
        "error_type": evt.error_type or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    logger.info(payload)


# ============================================================
# RETRY WITH EXPONENTIAL BACKOFF + JITTER (ENTERPRISE SAFE)
# ============================================================

def _sleep_seconds(attempt_index: int) -> float:
    """
    attempt_index: 1 for first retry, 2 for second retry, etc.
    """
    base = PROVIDER_RETRY_BASE_DELAY_SEC * (2 ** max(0, attempt_index - 1))
    if base > PROVIDER_RETRY_MAX_DELAY_SEC:
        base = PROVIDER_RETRY_MAX_DELAY_SEC

    jitter = PROVIDER_RETRY_JITTER_SEC * (0.5 + (time.time() % 1.0))
    return min(PROVIDER_RETRY_MAX_DELAY_SEC, base + jitter)


def retry_with_backoff(
    func: Callable[..., T],
    *,
    action: str = "provider_call",
    company_id: int = 0,
    provider: str = "",
    max_attempts: int = PROVIDER_RETRY_MAX_ATTEMPTS,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    should_retry: Optional[Callable[[Exception], bool]] = None,
    on_error_detail: Optional[Callable[[Exception], str]] = None,
    **kwargs: Any,
) -> T:
    """
    Enterprise behavior:
    - Retry disabled via env PROVIDER_RETRY_DISABLED=1
    - Exponential backoff + jitter
    - Optional should_retry(exception) hook to avoid retrying non-transient errors
    - Emits structured log event on final failure
    """
    start = time.time()
    attempts = 0
    last_err: Optional[Exception] = None

    if max_attempts < 1:
        max_attempts = 1

    while attempts < max_attempts:
        try:
            attempts += 1
            return func(**kwargs)
        except retry_exceptions as e:
            last_err = e
            if not PROVIDER_RETRY_ENABLED:
                break

            if should_retry is not None:
                try:
                    if not bool(should_retry(e)):
                        break
                except Exception:
                    break

            if attempts >= max_attempts:
                break

            time.sleep(_sleep_seconds(attempts))

    duration_ms = (time.time() - start) * 1000.0
    detail = ""
    if last_err is not None and on_error_detail is not None:
        try:
            detail = str(on_error_detail(last_err))
        except Exception:
            detail = ""

    log_provider_event(
        ProviderEvent(
            action=action,
            company_id=int(company_id),
            provider=provider,
            success=False,
            duration_ms=duration_ms,
            detail=detail or (str(last_err) if last_err else ""),
            error_type=type(last_err).__name__ if last_err else "unknown",
        )
    )

    if last_err:
        raise last_err

    raise RuntimeError("retry_with_backoff failed without captured exception")


__all__ = [
    "generate_correlation_id",
    "attach_correlation_id",
    "get_correlation_id",
    "add_correlation_header",
    "ProviderEvent",
    "log_provider_event",
    "retry_with_backoff",
]
