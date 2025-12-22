import os
import requests
from flask import Flask, request, redirect

def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "FreightPay is running"

    @app.route("/oauth/gusto/authorize")
    def gusto_authorize():
        client_id = os.environ.get("GUSTO_CLIENT_ID")
        redirect_uri = "https://freightpay.onrender.com/oauth/gusto/callback"

        return redirect(
            f"https://api.gusto.com/oauth/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
        )

    @app.route("/oauth/gusto/callback")
    def gusto_callback():
        code = request.args.get("code")
        return f"Gusto callback received. Code: {code}"

    return app

