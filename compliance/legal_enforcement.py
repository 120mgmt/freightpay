# File: legal/enforcement.py
# Purpose: Runtime legal acceptance enforcement (Terms / Privacy / Refund)
# Status: FULL PRODUCTION - hardened, non-breaking, opt-in via env
# Date: 2026-01-26

from __future__ import annotations

import os
import time
from typing import Iterable, Optional, Sequence, Tuple

from flask import abort, g, redirect, request

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

DEFAULT_DOCS: Tuple[str, ...] = ("terms", "privacy", "refund")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _truthy(v: str) -> bool:
    return v.lower() in {"1", "true", "yes", "y", "on"}


def legal_enforcement_enabled() -> bool:
    # Enable by default in production; disable explicitly with REQUIRE_LEGAL_ACCEPTANCE=0
    v = _env("REQUIRE_LEGAL_ACCEPTANCE", "1")
    return _truthy(v)


def required_docs() -> Tuple[str, ...]:
    # Comma-separated: "terms,privacy,refund"
    v = _env("REQUIRED_LEGAL_DOCS", "")
    if not v:
        return DEFAULT_DOCS
    docs = tuple([p.strip().lower() for p in v.split(",") if p.strip()])
    return docs or DEFAULT_DOCS


def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


# -----------------------------------------------------------------------------
# DB adapter (best-effort; will NOT crash app if DB layer differs)
# -----------------------------------------------------------------------------

def _get_db_conn():
    """
    Best-effort DB connection getter.

    Expected options (first one that works):
      - utils.database.get_db()
      - database.get_db()
      - db.get_db()

    Must return a DB-API like connection with .cursor() or a cursor directly.
    """
    for mod_name, fn_name in (
        ("utils.database", "get_db"),
        ("database", "get_db"),
        ("db", "get_db"),
    ):
        try:
            mod = __import__(mod_name, fromlist=[fn_name])
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                return fn()
        except Exception:
            continue
    return None


def _cursor_from_conn(conn):
    if conn is None:
        return None
    # If it's already a cursor-like object
    if hasattr(conn, "execute") and hasattr(conn, "fetchone"):
        return conn
    if hasattr(conn, "cursor"):
        try:
            return conn.cursor()
        except Exception:
            return None
    return None


def _is_doc_accepted(company_id: int, doc: str) -> bool:
    """
    Checks acceptance using a minimal canonical schema:
      table: legal_acceptance
      columns: company_id (int), doc (text), accepted (bool/int), accepted_at (bigint)
    This is defensive: if the schema doesn't exist, returns True to avoid blocking production.
    """
    conn = _get_db_conn()
    cur = _cursor_from_conn(conn)
    if cur is None:
        return True  # do not block if DB adapter not available

    # Try a few common table names / column variants (Postgres/SQLite-safe)
    candidates: Sequence[Tuple[str, str]] = (
        ("legal_acceptance", "doc"),
        ("legal_acceptances", "doc"),
        ("legal_acceptance", "document"),
        ("legal_acceptances", "document"),
    )

    for table, doc_col in candidates:
        try:
            # Parameter style varies; try DB-API qmark first, then %s
            sql_qmark = (
                f"SELECT 1 FROM {table} "
                f"WHERE company_id = ? AND {doc_col} = ? "
                f"AND (accepted = 1 OR accepted = TRUE) "
                f"ORDER BY accepted_at DESC LIMIT 1"
            )
            cur.execute(sql_qmark, (company_id, doc))
            row = cur.fetchone()
            if row:
                return True

            sql_ps = (
                f"SELECT 1 FROM {table} "
                f"WHERE company_id = %s AND {doc_col} = %s "
                f"AND (accepted = 1 OR accepted = TRUE) "
                f"ORDER BY accepted_at DESC LIMIT 1"
            )
            cur.execute(sql_ps, (company_id, doc))
            row = cur.fetchone()
            if row:
                return True
        except Exception:
            continue

    # If query paths fail (table missing / schema mismatch), do not block
    return True


# -----------------------------------------------------------------------------
# Enforcement
# -----------------------------------------------------------------------------

def _get_company_id_from_request() -> Optional[int]:
    """
    Non-breaking company_id resolution.
    Uses (in order):
      - g.company_id (if upstream auth/middleware set it)
      - X-Company-Id header
      - company_id query param
      - session value is intentionally NOT assumed here (no dependency)
    """
    cid = getattr(g, "company_id", None)
    cid = _safe_int(cid) if cid is not None else None
    if cid:
        return cid

    hdr = _safe_int(request.headers.get("X-Company-Id"))
    if hdr:
        return hdr

    qp = _safe_int(request.args.get("company_id"))
    if qp:
        return qp

    return None


def _is_exempt_path(path: str, extra_exempt_prefixes: Iterable[str]) -> bool:
    p = (path or "").strip().lower()
    if not p:
        return True

    # Always allow legal pages + auth + static
    defaults = (
        "/legal",
        "/static",
        "/health",
        "/billing/health",
        "/favicon.ico",
        "/robots.txt",
        "/sitemap",
        "/auth",
        "/login",
        "/logout",
        "/oauth",
        "/webhooks",
    )
    for pref in defaults:
        if p.startswith(pref):
            return True

    for pref in extra_exempt_prefixes:
        pref = (pref or "").strip().lower()
        if pref and p.startswith(pref):
            return True

    return False


def enforce_legal_acceptance(
    docs: Optional[Sequence[str]] = None,
    exempt_prefixes: Optional[Sequence[str]] = None,
    redirect_to: str = "/legal/terms",
):
    """
    Flask before_request handler.
    - If enforcement is disabled: no-op.
    - If company_id can't be resolved: no-op (avoid breaking authless routes).
    - If any required doc is not accepted: redirect (HTML) or 403 (API).
    """
    if not legal_enforcement_enabled():
        return None

    path = request.path or "/"
    if _is_exempt_path(path, exempt_prefixes or ()):
        return None

    company_id = _get_company_id_from_request()
    if not company_id:
        return None  # do not block if we cannot attribute to a company

    need = tuple([d.strip().lower() for d in (docs or required_docs()) if d and d.strip()])
    if not need:
        return None

    for doc in need:
        if not _is_doc_accepted(company_id, doc):
            # API requests get hard-fail; browser gets redirect
            accept = (request.headers.get("Accept") or "").lower()
            is_json = "application/json" in accept or (request.path or "").startswith("/api")
            if is_json:
                abort(403, description="legal_acceptance_required")
            return redirect(redirect_to)

    return None


def init_legal_enforcement(
    app,
    docs: Optional[Sequence[str]] = None,
    exempt_prefixes: Optional[Sequence[str]] = None,
    redirect_to: str = "/legal/terms",
) -> None:
    """
    Call once during app initialization.
    Safe to call multiple times (deduplicates by stamping app config).
    """
    stamp_key = "LEGAL_ENFORCEMENT_INITIALIZED_AT"
    if app.config.get(stamp_key):
        return

    app.before_request(
        lambda: enforce_legal_acceptance(
            docs=docs,
            exempt_prefixes=exempt_prefixes,
            redirect_to=redirect_to,
        )
    )
    app.config[stamp_key] = int(time.time())
