# File: middleware/request_id.py
# Purpose: Enterprise request ID + correlation propagation (multi-service traceability)
# Status: Enterprise Hardened (no PII, deterministic headers, safe defaults)
# Date: 2026-02-26

from __future__ import annotations

import uuid
from typing import Optional

from flask import Flask, g, request, Response


REQUEST_ID_HEADER = "X-Request-Id"
CORRELATION_ID_HEADER = "X-Correlation-Id"


def _new_id() -> str:
    return str(uuid.uuid4())


def _get_header(name: str) -> Optional[str]:
    v = request.headers.get(name)
    if not v:
        return None
    v = v.strip()
    return v if v else None


def init_request_ids(app: Flask) -> None:
    @app.before_request
    def _attach_ids() -> None:
        rid = _get_header(REQUEST_ID_HEADER) or _new_id()
        cid = _get_header(CORRELATION_ID_HEADER) or _new_id()

        g.request_id = rid
        g.correlation_id = cid

    @app.after_request
    def _emit_ids(resp: Response) -> Response:
        try:
            rid = getattr(g, "request_id", None)
            cid = getattr(g, "correlation_id", None)

            if rid:
                resp.headers.setdefault(REQUEST_ID_HEADER, str(rid))
            if cid:
                resp.headers.setdefault(CORRELATION_ID_HEADER, str(cid))
        except Exception:
            pass
        return resp


__all__ = ["init_request_ids", "REQUEST_ID_HEADER", "CORRELATION_ID_HEADER"]
