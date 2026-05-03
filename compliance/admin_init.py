# compliance/admin_init.py
# Registers the admin compliance blueprint without touching existing compliance init code.

from compliance.admin_routes import admin_compliance_bp


def register_admin_compliance(app):
    """
    Call once during app startup (after app is created):
        from compliance.admin_init import register_admin_compliance
        register_admin_compliance(app)
    """
    app.register_blueprint(admin_compliance_bp)
