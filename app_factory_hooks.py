# app_factory_hooks.py — optional; not used by default wsgi->app startup (app.py uses before_request).

from __future__ import annotations

from legal.middleware import require_legal_acceptance


def apply_legal_enforcement(app):
    """
    Apply legal acceptance enforcement to protected blueprints.
    Call AFTER blueprints are registered. Optional; app.py uses before_request for legal guard.
    """

    # Example: protect client/admin APIs
    protected_prefixes = (
        "/dashboard",
        "/billing",
        "/payroll",
        "/reports",
        "/admin",
    )

    for rule in list(app.url_map.iter_rules()):
        if any(rule.rule.startswith(p) for p in protected_prefixes):
            view = app.view_functions.get(rule.endpoint)
            if view and "require_legal_acceptance" not in getattr(view, "__name__", ""):
                app.view_functions[rule.endpoint] = require_legal_acceptance(view)
