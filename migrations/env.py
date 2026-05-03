# File: migrations/env.py
# Purpose: Alembic environment for Flask-Migrate (LedgerHaul)
# Status: Production-ready
# Date: 2026-02-11

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app

# Alembic Config object (accesses values in alembic.ini).
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_engine_url() -> str:
    """
    Pull SQLAlchemy URL from Flask app config (set by Flask-SQLAlchemy).
    Supports SQLAlchemy 2.x style URL objects.
    """
    engine = current_app.extensions["migrate"].db.engine
    try:
        return str(engine.url)
    except Exception:
        return engine.url.render_as_string(hide_password=False)


def get_metadata():
    """
    Use Flask-SQLAlchemy metadata from the active app.
    """
    return current_app.extensions["migrate"].db.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    """
    url = get_engine_url()
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    """
    connectable = current_app.extensions["migrate"].db.engine

    def process_revision_directives(_context, _revision, directives):
        """
        Prevent creating empty migration files.
        """
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            process_revision_directives=process_revision_directives,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
