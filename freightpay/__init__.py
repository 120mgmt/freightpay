from flask import Flask
def create app():
    app = Flask(__name__)
    @app.route("/")
    def home():
        return "FreightPay is running"
    return app
