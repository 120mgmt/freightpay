from decimal import Decimal, ROUND_HALF_UP

def d(val):
    return Decimal(str(val or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def run_payroll(payload: dict):
    """
    Expected payload structure:
    {
      "period": "2025-01",
      "workers": [
        {
          "id": "drv_001",
          "type": "contractor",  // or "employee"
          "pay": {
            "miles": 2500,
            "rate_per_mile": 0.65,
            "hourly_hours": 0,
            "hourly_rate": 0,
            "salary": 0
          },
          "accessorials": {
            "detention_hours": 6,
            "detention_rate": 30,
            "layover": 150,
            "stop_pay": 75,
            "tolls": 120,
            "other": 50
          },
          "deductions": {
            "advances": 200,
            "escrow": 50,
            "fuel": 300,
            "insurance": 100
          },
          "bonuses": {
            "safety": 100,
            "performance": 150
          }
        }
      ]
    }
    """

    results = []
    grand_total = d(0)

    for w in payload.get("workers", []):
        pay = w.get("pay", {})
        acc = w.get("accessorials", {})
        ded = w.get("deductions", {})
        bon = w.get("bonuses", {})

        mileage_pay = d(pay.get("miles")) * d(pay.get("rate_per_mile"))
        hourly_pay = d(pay.get("hourly_hours")) * d(pay.get("hourly_rate"))
        salary_pay = d(pay.get("salary"))

        detention_pay = d(acc.get("detention_hours")) * d(acc.get("detention_rate"))

        accessorial_total = (
            detention_pay
            + d(acc.get("layover"))
            + d(acc.get("stop_pay"))
            + d(acc.get("tolls"))
            + d(acc.get("other"))
        )

        bonus_total = d(bon.get("safety")) + d(bon.get("performance"))

        gross = mileage_pay + hourly_pay + salary_pay + accessorial_total + bonus_total

        deductions_total = (
            d(ded.get("advances"))
            + d(ded.get("escrow"))
            + d(ded.get("fuel"))
            + d(ded.get("insurance"))
        )

        net = gross - deductions_total

        grand_total += net

        results.append({
            "worker_id": w.get("id"),
            "worker_type": w.get("type"),
            "gross_pay": float(gross),
            "total_deductions": float(deductions_total),
            "net_pay": float(net)
        })

    return {
        "period": payload.get("period"),
        "total_workers": len(results),
        "total_net_pay": float(grand_total),
        "details": results
    }
