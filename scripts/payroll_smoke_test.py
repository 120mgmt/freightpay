# File: scripts/payroll_smoke_test.py
# Purpose: End-to-end smoke test for Payroll Runs + Execute + Provider Map + Finalize (production-safe)
# Date: 2026-02-23
#
# Usage:
#   export API_BASE_URL="https://api.ledgerhaul.com"
#   # If your API requires JWT:
#   export API_AUTH_HEADER="Authorization: Bearer <token>"
#   # If your API requires company scoping (recommended):
#   export X_COMPANY_ID="0"
#   python scripts/payroll_smoke_test.py
#
# Notes:
# - Provider mapping endpoint is mapping-only and should not require provider credentials.
# - If your subscription gate blocks requests, ensure the user/token has an active plan.

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:10000").rstrip("/")
API_AUTH_HEADER = os.getenv("API_AUTH_HEADER", "").strip()  # e.g. 'Authorization: Bearer xxx'
X_COMPANY_ID = os.getenv("X_COMPANY_ID", "").strip()  # optional; recommended


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if API_AUTH_HEADER:
        # expects "Key: Value"
        if ":" in API_AUTH_HEADER:
            k, v = API_AUTH_HEADER.split(":", 1)
            h[k.strip()] = v.strip()
    if X_COMPANY_ID:
        h["X-Company-Id"] = X_COMPANY_ID
    return h


def _req(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
    url = f"{API_BASE_URL}{path}"
    r = requests.request(method, url, headers=_headers(), json=body, timeout=45)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def _require_run_id(data: Any) -> str:
    if not isinstance(data, dict):
        raise ValueError("Response is not JSON object")
    run_id = (data or {}).get("run_id")
    if not run_id or not isinstance(run_id, str):
        raise ValueError("Missing run_id")
    return run_id


def main() -> int:
    # ------------------------------------------------------------
    # 1) Create run
    # ------------------------------------------------------------
    create_payload = {
        "period": "2026-01-01 to 2026-01-15",
        "company_id": int(X_COMPANY_ID) if X_COMPANY_ID else 0,
        "contractors": [
            {
                "contractor_id": "drv_001",
                "worker_type": "contractor",
                "worker_uuid": "contractor-uuid-1",
                "base_gross": 2000,
                "accessorials": {"detention": 150, "fuel_bonus": 75},
                "deductions": {"insurance": 120, "escrow": 50},
                "mileage": {"miles": 100, "rate_per_mile": 0.67},
            },
            {
                "contractor_id": "emp_001",
                "worker_type": "employee",
                "worker_uuid": "employee-uuid-1",
                "base_gross": 0,
                "hourly": {"hours": 40, "rate": 25, "overtime_hours": 5, "overtime_multiplier": 1.5},
                "accessorials": {"stop_pay": 25},
                "deductions": {"insurance": 100},
                "mileage": {"miles": 50, "rate_per_mile": 0.67},
            },
        ],
    }

    status, data = _req("POST", "/payroll/runs", create_payload)
    if status not in (200, 201):
        print("CREATE RUN FAILED:", status, data)
        return 1

    try:
        run_id = _require_run_id(data)
    except Exception as e:
        print("CREATE RUN INVALID RESPONSE:", str(e), data)
        return 1

    print("RUN CREATED:", run_id)

    # ------------------------------------------------------------
    # 2) Execute run
    # ------------------------------------------------------------
    exec_body: Dict[str, Any] = {}
    if not X_COMPANY_ID:
        exec_body["company_id"] = 0

    status, data = _req("POST", f"/payroll/runs/{run_id}/execute", exec_body)
    if status != 200:
        print("EXECUTE FAILED:", status, data)
        return 1

    if not isinstance(data, dict) or not (data.get("results") is not None):
        print("EXECUTE MISSING results:", data)
        return 1

    print("RUN EXECUTED:", run_id)

    # ------------------------------------------------------------
    # 3) Execute + Map to Provider payloads (mapping-only)
    # ------------------------------------------------------------
    status, data = _req("POST", f"/payroll/runs/{run_id}/execute-provider-map", exec_body)
    if status != 200:
        print("PROVIDER MAP FAILED:", status, data)
        return 1

    if not isinstance(data, dict):
        print("PROVIDER MAP INVALID RESPONSE:", data)
        return 1

    provider_payloads = (data or {}).get("provider_payloads") or []
    if not isinstance(provider_payloads, list):
        print("PROVIDER MAP INVALID payload list:", data)
        return 1

    print("PROVIDER PAYLOADS:", json.dumps(provider_payloads, indent=2, default=str))

    # ------------------------------------------------------------
    # 4) Finalize
    # ------------------------------------------------------------
    status, data = _req("POST", f"/payroll/runs/{run_id}/finalize", exec_body)
    if status != 200:
        print("FINALIZE FAILED:", status, data)
        return 1

    if not isinstance(data, dict) or not data.get("finalized"):
        print("FINALIZE INVALID RESPONSE:", data)
        return 1

    print("RUN FINALIZED:", run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
