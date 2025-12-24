from decimal import Decimal, ROUND_HALF_UP

def _d(x) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0")

def _money(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def run_payroll(contractors: list) -> dict:
    """
    Each contractor can include:
      - name
      - miles, rate_per_mile
      - hourly_hours, hourly_rate
      - accessorials: { detention, layover, tonu, lumper, stop_pay, hazmat, tolls, other }
      - deductions: { fuel_advance, insurance, escrow, other }
    """
    totals = {
        "gross_pay": Decimal("0"),
        "deductions": Decimal("0"),
        "net_pay": Decimal("0"),
    }

    items = []

    for c in contractors or []:
        name = c.get("name", "Contractor")
        miles = _d(c.get("miles", 0))
        rpm = _d(c.get("rate_per_mile", 0))
        mile_pay = miles * rpm

        hours = _d(c.get("hourly_hours", 0))
        hr_rate = _d(c.get("hourly_rate", 0))
        hourly_pay = hours * hr_rate

        access = c.get("accessorials", {}) or {}
        access_total = (
            _d(access.get("detention", 0)) +
            _d(access.get("layover", 0)) +
            _d(access.get("tonu", 0)) +
            _d(access.get("lumper", 0)) +
            _d(access.get("stop_pay", 0)) +
            _d(access.get("hazmat", 0)) +
            _d(access.get("tolls", 0)) +
            _d(access.get("other", 0))
        )

        gross = mile_pay + hourly_pay + access_total

        ded = c.get("deductions", {}) or {}
        deductions_total = (
            _d(ded.get("fuel_advance", 0)) +
            _d(ded.get("insurance", 0)) +
            _d(ded.get("escrow", 0)) +
            _d(ded.get("other", 0))
        )

        net = gross - deductions_total

        totals["gross_pay"] += gross
        totals["deductions"] += deductions_total
        totals["net_pay"] += net

        items.append({
            "name": name,
            "miles": float(miles),
            "rate_per_mile": float(rpm),
            "mile_pay": _money(mile_pay),
            "hourly_hours": float(hours),
            "hourly_rate": float(hr_rate),
            "hourly_pay": _money(hourly_pay),
            "accessorials_total": _money(access_total),
            "gross_pay": _money(gross),
            "deductions_total": _money(deductions_total),
            "net_pay": _money(net),
        })

    return {
        "contractors": items,
        "totals": {
            "gross_pay": _money(totals["gross_pay"]),
            "deductions": _money(totals["deductions"]),
            "net_pay": _money(totals["net_pay"]),
        }
    }
