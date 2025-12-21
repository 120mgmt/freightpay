from flask import Flask, request
def create_app():
    app = Flask(__name__)
    @app.route("/")
    def home():
        return "FreightPay is running"
    @app.route("oauth/gusto/callback")
    def gusto_callback():
        code = request.args.get("c0de")
        return f"Gusto callback received. Code: {code}"
    return app
