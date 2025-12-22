
from flask import Flask, jsonify
from config import Config
from db import db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

@app.route("/")
def index():
    return jsonify({"status": "FreightPay running"})

if __name__ == "__main__":
    app.run()
