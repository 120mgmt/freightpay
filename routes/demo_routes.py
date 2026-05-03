# File: routes/demo_routes.py
# Purpose: Self-guided demo (marketing-safe) + in-app navigation guide
# Status: Production-ready (no DB writes; no auth required; zero side-effects)
# Date: 2026-02-14

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Blueprint, jsonify, make_response


demo_bp = Blueprint("demo", __name__, url_prefix="/demo")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _base_url() -> str:
    return (os.getenv("BASE_URL") or "").strip().rstrip("/") or "https://ledgerhaul.com"


def _demo_enabled() -> bool:
    v = (os.getenv("DEMO_ENABLED") or "1").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _demo_mode() -> str:
    return (os.getenv("DEMO_MODE") or "guided").strip().lower()


def _html_page(title: str, body_html: str) -> str:
    base = _base_url()
    mode_label = "Mode: guided" if _demo_mode() == "guided" else "Mode: public"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0b1220;
      --card: #101a2e;
      --text: #e8eefc;
      --muted: #b7c5e6;
      --accent: #3b82f6;
      --border: rgba(255,255,255,0.10);
      --code: #0a0f1d;
    }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background:
        radial-gradient(
          1200px 800px at 20% 10%,
          rgba(59,130,246,.25),
          transparent 60%
        ),
        radial-gradient(
          900px 600px at 80% 20%,
          rgba(16,185,129,.18),
          transparent 55%
        ),
        var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 48px; }}
    .top {{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      border: 1px solid var(--border);
      background: rgba(16,26,46,.70);
      padding: 16px 18px;
      border-radius: 14px;
      backdrop-filter: blur(8px);
    }}
    .brand {{
      display:flex;
      flex-direction:column;
      gap:4px;
    }}
    .brand h1 {{ margin:0; font-size: 18px; letter-spacing:.2px; }}
    .brand p {{ margin:0; color: var(--muted); font-size: 13px; }}
    .btn {{
      display:inline-block;
      padding: 10px 14px;
      border-radius: 12px;
      background: linear-gradient(
        180deg,
        rgba(59,130,246,.95),
        rgba(59,130,246,.78)
      );
      color: white;
      text-decoration:none;
      font-weight: 600;
      border: 1px solid rgba(255,255,255,.12);
    }}
    .grid {{
      display:grid;
      grid-template-columns: 1.2fr .8fr;
      gap: 14px;
      margin-top: 14px;
    }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      border: 1px solid var(--border);
      background: rgba(16,26,46,.70);
      border-radius: 14px;
      padding: 16px 18px;
      backdrop-filter: blur(8px);
    }}
    .card h2 {{ margin: 0 0 10px; font-size: 15px; }}
    .muted {{ color: var(--muted); font-size: 13px; }}
    ol {{ padding-left: 18px; margin: 10px 0; }}
    li {{ margin: 7px 0; }}
    code, pre {{
      background: var(--code);
      border: 1px solid rgba(255,255,255,.10);
      border-radius: 12px;
      padding: 10px 12px;
      display:block;
      overflow-x:auto;
      color: #dbe7ff;
      font-size: 12.5px;
    }}
    .pill {{
      display:inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.06);
      color: var(--muted);
      font-size: 12px;
    }}
    .row {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
    .foot {{ margin-top: 14px; color: var(--muted); font-size: 12px; }}
    a.link {{ color: #9cc2ff; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand">
        <h1>LedgerHaul — Self-Guided Demo</h1>
        <p>Walkthrough + sample flows. No data changes. {mode_label}</p>
      </div>
      <div class="row">
        <span class="pill">timestamp: {_utc_iso()}</span>
        <a class="btn" href="{base}" target="_blank" rel="noreferrer">
          Go to Live App
        </a>
      </div>
    </div>

    {body_html}

    <div class="foot">
      If you want the demo hidden, set
      <span class="pill">DEMO_ENABLED=0</span>.
      For a lighter marketing page, set
      <span class="pill">DEMO_MODE=public</span>.
    </div>
  </div>
</body>
</html>"""


def _guide_payload() -> Dict[str, Any]:
    return {
        "demo": {
            "enabled": _demo_enabled(),
            "mode": _demo_mode(),
            "timestamp": _utc_iso(),
            "base_url": _base_url(),
        },
        "self_guided_steps": [
            {
                "title": "1) Create company + admin user",
                "what_you_do": "Sign up, then log in.",
                "what_to_expect": (
                    "You land on your dashboard with empty books "
                    "and a clean starting point."
                ),
            },
            {
                "title": "2) Chart of Accounts baseline",
                "what_you_do": "Open Chart of Accounts and confirm defaults exist.",
                "what_to_expect": (
                    "System accounts cannot be deleted; custom accounts can be added."
                ),
            },
            {
                "title": "3) Import bookkeeping (migration-ready)",
                "what_you_do": (
                    "Upload your export files (CSV) from prior system "
                    "(ex: QuickBooks)."
                ),
                "what_to_expect": (
                    "You map columns once, then LedgerHaul enforces "
                    "the structure going forward."
                ),
            },
            {
                "title": "4) Reconciliation",
                "what_you_do": "Connect bank/transactions (or upload statement CSV).",
                "what_to_expect": (
                    "Match transactions to ledger and close the month cleanly."
                ),
            },
            {
                "title": "5) Payroll (provider-agnostic)",
                "what_you_do": (
                    "Run payroll workflow inside LedgerHaul; "
                    "provider handles the money-move."
                ),
                "what_to_expect": (
                    "Ledger entries post automatically from payroll results "
                    "for clean books."
                ),
            },
        ],
        "demo_endpoints": {
            "guide_json": "/demo/guide",
            "health": "/demo/health",
            "sample_requests": "/demo/sample-requests",
        },
    }


def _render_steps_html(steps: list[dict[str, str]]) -> str:
    items: list[str] = []

    for step in steps:
        items.append(
            (
                f"<li><b>{step['title']}</b><br/>"
                f"<span class='muted'>{step['what_you_do']} — "
                f"{step['what_to_expect']}</span></li>"
            )
        )

    return "".join(items)


@demo_bp.get("")
@demo_bp.get("/")
def demo_home():
    if not _demo_enabled():
        return jsonify({"error": "not_found"}), 404

    guide = _guide_payload()
    steps_html = _render_steps_html(guide["self_guided_steps"])

    body = f"""
    <div class="grid">
      <div class="card">
        <h2>What this is</h2>
        <div class="muted">
          A self-guided walkthrough you can link from marketing pages.
          It does not create, update, or delete any customer data.
        </div>

        <h2 style="margin-top:14px;">Walkthrough</h2>
        <ol>
          {steps_html}
        </ol>
      </div>

      <div class="card">
        <h2>Demo links</h2>
        <div class="muted">
          Use these in your website nav:
          <span class="pill">/demo</span>
          and
          <span class="pill">/demo/guide</span>
        </div>
        <div style="height:10px;"></div>
        <div class="row">
          <a class="link" href="/demo/guide">Open guide JSON</a>
          <a class="link" href="/demo/sample-requests">Sample API requests</a>
          <a class="link" href="/demo/health">Demo health</a>
        </div>

        <h2 style="margin-top:14px;">Shareable marketing copy</h2>
        <div class="muted">
          “Try the self-guided demo to see onboarding, bookkeeping migration,
          reconciliation, and payroll posting flow.”
        </div>
      </div>
    </div>
    """
    return make_response(_html_page("LedgerHaul Demo", body), 200)


@demo_bp.get("/guide")
def demo_guide():
    if not _demo_enabled():
        return jsonify({"error": "not_found"}), 404
    return jsonify(_guide_payload()), 200


@demo_bp.get("/health")
def demo_health():
    if not _demo_enabled():
        return jsonify({"error": "not_found"}), 404

    return (
        jsonify(
            {
                "status": "ok",
                "demo": True,
                "mode": _demo_mode(),
                "timestamp": _utc_iso(),
            }
        ),
        200,
    )


@demo_bp.get("/sample-requests")
def demo_sample_requests():
    if not _demo_enabled():
        return jsonify({"error": "not_found"}), 404

    if _demo_mode() == "public":
        return (
            jsonify(
                {
                    "demo": "public",
                    "message": (
                        "Sample requests hidden in public mode. "
                        "Set DEMO_MODE=guided to expose them."
                    ),
                    "timestamp": _utc_iso(),
                }
            ),
            200,
        )

    examples = [
        {
            "title": "Check basic health",
            "method": "GET",
            "path": "/health",
            "notes": "Confirms API is up.",
        },
        {
            "title": "List payroll runs (example)",
            "method": "GET",
            "path": "/payroll/runs?limit=20",
            "headers": {"X-Company-Id": "0"},
            "notes": "Requires subscription gating if enabled.",
        },
        {
            "title": "Create payroll run (example)",
            "method": "POST",
            "path": "/payroll/runs",
            "headers": {
                "Content-Type": "application/json",
                "X-Company-Id": "0",
            },
            "body": {
                "company_id": 0,
                "period_start": "2026-02-03",
                "period_end": "2026-02-09",
                "pay_date": "2026-02-10",
                "workers": [],
            },
            "notes": "Body format depends on your payroll engine contract.",
        },
        {
            "title": "Chart of accounts (example)",
            "method": "GET",
            "path": "/coa",
            "headers": {"X-Company-Id": "0"},
            "notes": "Shows chart accounts for the tenant.",
        },
    ]

    return (
        jsonify(
            {
                "demo": "guided",
                "timestamp": _utc_iso(),
                "examples": examples,
                "tip": (
                    "Use /demo as the marketing link; "
                    "this endpoint is just supporting material."
                ),
            }
        ),
        200,
    )


__all__ = ["demo_bp"]
