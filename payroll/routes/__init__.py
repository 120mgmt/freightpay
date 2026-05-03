# File: payroll/routes/__init__.py
# Purpose: Export payroll blueprints for app.py registration (import-safe)
# Status: Production-ready
# Date: 2026-02-23

from __future__ import annotations

from .payroll_routes import payroll_bp, provider_submit_bp  # noqa: F401

__all__ = ["payroll_bp", "provider_submit_bp"]
