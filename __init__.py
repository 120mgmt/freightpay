from flask import flask

def create_app():
    app = FLask(__name__)

# import blueprints here (after app exists)
from payroll.payroll_routes import payroll_bp
app.register_blueprint(payroll_bp, url_prefix="/payroll")

@app.route("/")
def root():
    return {"app": "freightpay", "status": "running"}

return app
