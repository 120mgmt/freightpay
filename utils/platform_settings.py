# File: utils/platform_settings.py
# Purpose: DB-backed runtime settings (admin-managed), overriding env vars.
# Why: the hosting dashboard has repeatedly shown env values the runtime
#      never received. Settings written here reach the process reliably:
#      applied to os.environ at boot (see env_bootstrap.py) and immediately
#      when saved through the admin API.
# Date: 2026-07-16

from __future__ import annotations

import os
from typing import Dict, Optional

from sqlalchemy import text

from db import db

# settings key -> env var it overrides
ENV_BACKED_KEYS: Dict[str, str] = {
    "stripe_secret_key": "STRIPE_SECRET_KEY",
    "stripe_webhook_secret": "STRIPE_WEBHOOK_SECRET",
}


def get_setting(key: str) -> Optional[str]:
    try:
        row = db.session.execute(
            text("SELECT value FROM platform_settings WHERE key = :k"),
            {"k": key},
        ).first()
        val = (row[0] or "").strip() if row else ""
        return val or None
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def set_setting(key: str, value: Optional[str]) -> None:
    """Upsert the setting and apply it to this process's env immediately."""
    val = (value or "").strip() or None
    db.session.execute(
        text(
            "INSERT INTO platform_settings (key, value, updated_at) "
            "VALUES (:k, :v, now()) "
            "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = now()"
        ),
        {"k": key, "v": val},
    )
    db.session.commit()

    env_name = ENV_BACKED_KEYS.get(key)
    if env_name:
        if val:
            os.environ[env_name] = val
        else:
            os.environ.pop(env_name, None)


def secret_hint(value: Optional[str]) -> str:
    """Prefix (public account id) + last 4 — never the secret middle."""
    v = (value or "").strip()
    if len(v) < 12:
        return "unset"
    return f"{v[:17]}...{v[-4:]}" if len(v) > 25 else f"{v[:6]}...{v[-4:]}"
