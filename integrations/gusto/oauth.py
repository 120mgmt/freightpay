import os
import requests
from flask import Blueprint, redirect, request, jsonify

gusto_bp = Blueprint("gusto", __name__)

GUSTO_ENV = os.getenv("GUSTO_ENV", "demo")  # demo or prod
CLIENT_ID = os.getenv("GUSTO_CLIENT_ID")
CLIENT_SECRET = os.getenv("GUSTO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GUSTO_REDIRECT_URI")

BASE_URL = "https://api.gusto-demo.com" if GUSTO_ENV == "demo" else "https://api.gusto.com"
AUTH_URL = f"{BASE_URL}/oauth/authorize"
TOKEN_URL = f"{BASE_URL}/oauth/token"


@gusto_bp.route("/oauth/gusto/login")
def gusto_login():
    return redirect(
        f"{AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=contractors companies"
    )


@gusto_bp.route("/oauth/gusto/callback")
def gusto_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing authorization code"}), 400

    token_resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
    )

    token_data = token_resp.json()

    return jsonify({
        "status": "connected",
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
    })

