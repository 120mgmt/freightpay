from flask import Flask, request, jsonify
from payroll.engine import run_payroll

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "service": "FreightPay",
        "mode": "production"
    }), 200


@app.route("/api/payroll/run", methods=["POST"])
def payroll_run():
    try:
        payload = request.get_json(force=True)
        result = run_payroll(payload)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "error": "PAYROLL_EXECUTION_FAILED",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
