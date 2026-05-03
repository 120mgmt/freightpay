# compliance/cli.py
# CLI helpers for seeding versioned legal documents (LedgerHaul)

from __future__ import annotations

import hashlib
from datetime import datetime

import click
from flask import current_app

from db import db
from compliance.models import LegalDocument


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def register_compliance_cli(app):
    @app.cli.command("seed-legal")
    @click.option("--version", required=True, help="Version string, e.g. 2026-01-25")
    @click.option("--effective-at", default=None, help="ISO datetime; defaults to now (UTC)")
    def seed_legal(version: str, effective_at: str | None):
        """
        Seeds active Terms + Privacy documents into legal_documents.
        Reads ./legal/terms.md and ./legal/privacy.md if present; otherwise uses placeholders.
        """
        base = current_app.root_path
        def read_file(rel):
            try:
                with open(f"{base}/legal/{rel}", "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                return ""

        terms_text = read_file("terms.md")
        privacy_text = read_file("privacy.md")

        if not effective_at:
            eff = datetime.utcnow()
        else:
            eff = datetime.fromisoformat(effective_at.replace("Z", "+00:00")).replace(tzinfo=None)

        def upsert(doc_key: str, body: str):
            # deactivate previous actives
            LegalDocument.query.filter_by(doc_key=doc_key, is_active=True).update({"is_active": False})

            checksum = _sha256(body) if body else None
            doc = LegalDocument(
                doc_key=doc_key,
                version=version,
                checksum=checksum,
                effective_at=eff,
                is_active=True,
            )
            db.session.add(doc)

        upsert("terms", terms_text)
        upsert("privacy", privacy_text)

        db.session.commit()
        click.echo(f"Seeded legal documents: terms/privacy version={version} effective_at={eff.isoformat()}")
