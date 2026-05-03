# compliance/seed_guard.py
# Startup guard: hard-fail app boot if active legal docs are not seeded
# Backend-only, no route overlap

from compliance.models import LegalDocument


def verify_legal_seeded():
    """
    Call once at app startup AFTER db.init_app(app).
    Raises RuntimeError if Terms or Privacy are not active.
    """
    missing = []
    for key in ("terms", "privacy"):
        doc = (
            LegalDocument.query
            .filter_by(doc_key=key, is_active=True)
            .order_by(LegalDocument.effective_at.desc())
            .first()
        )
        if not doc:
            missing.append(key)

    if missing:
        raise RuntimeError(
            f"Compliance boot blocked: active legal documents missing: {', '.join(missing)}. "
            "Run: flask seed-legal --version YYYY-MM-DD"
        )
