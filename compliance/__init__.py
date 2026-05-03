# compliance/__init__.py
# Single import point for compliance (blueprints + CLI registration)

from compliance.routes import compliance_bp
from compliance.cli import register_compliance_cli


def init_compliance(app):
    """
    Call once during app startup after app/db/login are initialized.
    """
    app.register_blueprint(compliance_bp)
    register_compliance_cli(app)
