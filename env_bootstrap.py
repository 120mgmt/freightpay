# File: env_bootstrap.py
# Purpose: Apply DB-stored platform settings to os.environ BEFORE any module
#          reads them. Must be imported first in app.py — several blueprints
#          validate env vars at import time.
# Why: the hosting dashboard has repeatedly displayed env values the runtime
#      never received; the database is the channel that reliably reaches
#      production, so admin-managed secrets live there (platform_settings).
# Date: 2026-07-16

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

_log = logging.getLogger("ledgerhaul.env_bootstrap")

# Keep in sync with utils/platform_settings.ENV_BACKED_KEYS (not imported
# here: that module needs the Flask db, which does not exist yet).
_DB_ENV_KEYS = {
    "stripe_secret_key": "STRIPE_SECRET_KEY",
    "stripe_webhook_secret": "STRIPE_WEBHOOK_SECRET",
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_password": "SMTP_PASSWORD",
    "from_email": "FROM_EMAIL",
}


def _apply_db_env_overrides() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return
    engine = None
    try:
        import sqlalchemy as sa

        engine = sa.create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT key, value FROM platform_settings WHERE key IN :keys").bindparams(
                    sa.bindparam("keys", expanding=True)
                ),
                {"keys": list(_DB_ENV_KEYS.keys())},
            ).all()
        for key, value in rows:
            env_name = _DB_ENV_KEYS.get(key)
            val = (value or "").strip()
            if env_name and val:
                os.environ[env_name] = val
                _log.info("env override applied from platform_settings: %s", env_name)
    except Exception as e:
        # First boot (table not created yet), transient DB issues, etc. —
        # never block startup; env vars remain whatever the host provided.
        _log.warning("platform_settings env overrides skipped: %s", e)
    finally:
        try:
            if engine is not None:
                engine.dispose()
        except Exception:
            pass


_apply_db_env_overrides()
