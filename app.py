@app.route("/oauth/gusto/login")
def gusto_login():
    import os
    from urllib.parse import urlencode

    params = {
        "client_id": os.environ["GUSTO_CLIENT_ID"],
        "redirect_uri": "https://freightpay.onrender.com/oauth/gusto/callback",
        "response_type": "code",
        "scope": "payroll:companies payroll:employees payroll:contractors",
    }

    return redirect(
        "https://api.gusto.com/oauth/authorize?" + urlencode(params)
    )
