from flask import Blueprint, redirect, request
import requests
import os

gusto_bp = Blueprint("gusto", __name__)

GUSTO_CLIENT_ID = os.getenv("GUSTO_CLIENT_ID")
GUSTO_CLIENT_SECRET = os.getenv("GUSTO_CLIENT_SECRET")
GUSTO_REDIRECT_URI = os.getenv("GUSTO_REDIRECT_URI")
GUSTO_ENV = os.getenv("GUSTO_ENV", "demo")

AUTH_URL = (
    "https://api.gusto-demo.com/oauth/authorize"
    if GUSTO_ENV == "demo"
    else "https://api.gusto.com/oauth/authorize"
)

TOKEN_URL = (
    "https://api.gusto-demo.com/oauth/token"
    if GUSTO_ENV == "demo"
    else "https://api.gusto.com/oauth/token"
)

@gusto_bp.route("/gusto/login")
def gusto_login():
    return redirect(
        f"{AUTH_URL}?client_id={GUSTO_CLIENT_ID}"
        f"&redirect_uri={GUSTO_REDIRECT_URI}"
        f"&response_type=code&scope=payroll:read payroll:write"
    )

@gusto_bp.route("/gusto/callback")
def gusto_callback():
    code = request.args.get("code")

    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": GUSTO_CLIENT_ID,
            "client_secret": GUSTO_CLIENT_SECRET,
            "redirect_uri": GUSTO_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code": code,
        },
    )

    return response.json()
    
