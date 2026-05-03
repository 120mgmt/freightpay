# compliance/export.py
# Secure export utilities for compliance data (CSV/JSON) – backend only
# No overlap with existing files

import csv
from io import StringIO
from datetime import datetime

from flask import Response, request, jsonify
from flask_login import login_required, current_user

from compliance.models import LegalDocument, UserLegalAcceptance
from compliance.audit import ComplianceAuditLog


def _is_admin() -> bool:
    return bool(
        getattr(current_user, "is_admin", False)
        or getattr(current_user, "is_staff", False)
        or (getattr(current_user, "role", None) == "admin")
    )


@login_required
def export_compliance_csv():
    if not _is_admin():
        return jsonify({"error": "forbidden"}), 403

    kind = request.args.get("kind", "acceptances")  # acceptances | audit | documents

    si = StringIO()
    writer = csv.writer(si)

    if kind == "documents":
        writer.writerow(["id", "doc_key", "version", "checksum", "effective_at", "is_active"])
        rows = LegalDocument.query.order_by(LegalDocument.doc_key, LegalDocument.effective_at.desc()).all()
        for r in rows:
            writer.writerow([r.id, r.doc_key, r.version, r.checksum, r.effective_at, r.is_active])

    elif kind == "audit":
        writer.writerow([
            "id", "user_id", "actor_type", "event_type", "doc_key",
            "version", "path", "method", "ip", "user_agent", "detail", "created_at"
        ])
        rows = ComplianceAuditLog.query.order_by(ComplianceAuditLog.created_at.desc()).limit(5000).all()
        for r in rows:
            writer.writerow([
                r.id, r.user_id, r.actor_type, r.event_type, r.doc_key,
                r.version, r.path, r.method, r.ip, r.user_agent, r.detail, r.created_at
            ])

    else:  # acceptances
        writer.writerow(["id", "user_id", "doc_key", "version", "accepted", "accepted_at"])
        rows = UserLegalAcceptance.query.order_by(UserLegalAcceptance.accepted_at.desc()).limit(5000).all()
        for r in rows:
            writer.writerow([r.id, r.user_id, r.doc_key, r.version, r.accepted, r.accepted_at])

    output = si.getvalue()
    si.close()

    filename = f"compliance_{kind}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
