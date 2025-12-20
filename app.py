from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "FreightPay is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", po
@app.route("/gusto/callback")
def gusto_callback():
    return "Gusto callback reached"
from flask import request

@app.route("/gusto/callback")
def gusto_callback():
    code = request.args.get("code")
    return f"Gusto callback received. Code: {code}"
