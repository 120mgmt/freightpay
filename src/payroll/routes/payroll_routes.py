from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from payroll.engine import run_payroll
from models import db, PayrollRun

payroll_bp = Blueprint("payroll_api", __name__, url_prefix="/payroll")

@payroll_bp.post("/run")
@jwt_required()
def run_payroll_route():
    data = request.get_json(force=True) or {}
    contractors = data.get("contractors", []) or []
    results = run_payroll(contractors)

    user_id = int(get_jwt_identity())
    pr = PayrollRun(user_id=user_id, payload=data, results=results)
    db.session.add(pr)
    db.session.commit()

    return jsonify({"status": "ok", "results": results, "payroll_run_id": pr.id}), 200

@payroll_bp.get("/runs")
@jwt_required()
def list_runs():
    user_id = int(get_jwt_identity())
    runs = (
        PayrollRun.query
        .filter_by(user_id=user_id)
        .order_by(PayrollRun.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        "status": "ok",
        "runs": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "payload": r.payload,
                "results": r.results,
            } for r in runs
        ]
    }), 200
