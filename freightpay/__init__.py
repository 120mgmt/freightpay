from flask import redirect
import os
import urllib.parse

@app.route("/oauth/gusto/login")
def gusto_login():
    params = {
        "client_id": os.environ["GUSTO_CLIENT_ID"],
        "redirect_uri": "https://freightpay.onrender.com/oauth/gusto/callback",
        "response_type": "code",
        "scope": "companies:read employees:read contractors:read"
    }

    url = "https://api.gusto.com/oauth/authorize?" + urllib.parse.urlencode(params)
    return redirect(url)
