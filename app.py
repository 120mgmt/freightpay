from flask import Flask, request
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "FreightPay is running"

@app.route("/gusto/callback")
def gusto_callback():
    code = request.args.get("code")
    return f"Gusto callback received. Code: {code}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

