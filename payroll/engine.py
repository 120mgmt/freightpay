from decimal import Decimal, ROUND_HALF_UP

# ---------- helpers ----------
def _d(v) -> Decimal:
    try:
        if v is None or v == "":
            return Decimal("0.00")
        return Decimal(str(v))
    except Exception:
        return Decimal("0.00")

def _money(v) -> Decimal:
    return _d(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _pct(v) -> Decimal:
    # accepts 5, "5", 0.05, "0.05"
    x = _d(v)
    if x > 1:
        x = x / Decimal("100")
    if x < 0:
        x = Decimal("0")
    return x


# ---------- trucking payroll building blocks ----------
def calculate_miles_pay(miles, rate_per_mile) -> Decimal:
    return (_money(miles) * _money(rate_per_mile)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def compute_earnings(earnings: dict) -> dict:
    """
    Taxable accessorial earnings:
    detention, layover, stop_pay, tonu, breakdown, bonus, other_earnings
    """
    e = earnings or {}

    detention_hours = _money(e.get("detention_hours"))
    detention_rate = _money(e.get("detention_rate"))
    detention = _money(detention_hours * detention_rate)

    layover = _money(e.get("layover"))
    stop_pay = _money(e.get("stop_pay"))
    stops = _money(e.get("stops"))
    # allow stop total to be passed directly OR computed via stops * stop_rate
    stop_rate = _money(e.get("stop_rate"))
    stop_calc = _money(stops * stop_rate)
    stop_total = _money(stop_pay + stop_calc)

    tonu = _money(e.get("tonu"))
    breakdown = _money(e.get("breakdown"))
    bonus = _money(e.get("bonus"))
    other_earnings = _money(e.get("other_earnings"))

    total = _money(detention + layover + stop_total + tonu + breakdown + bonus + other_earnings)

    return {
        "detention": float(detention),
        "layover": float(layover),
        "stop_total": float(stop_total),
        "tonu": float(tonu),
        "breakdown": float(breakdown),
        "bonus": float(bonus),
        "other_earnings": float(other_earnings),
        "total_earnings_accessorials": float(total),
    }

def compute_reimbursements(reimbursements: dict) -> dict:
    """
    Non-taxable reimbursements:
    tolls, scales, parking, lumper, washout, other_reimbursements
    """
    r = reimbursements or {}
    tolls = _money(r.get("tolls"))
    scales = _money(r.get("scales"))
    parking = _money(r.get("parking"))
    lumper = _money(r.get("lumper"))
    washout = _money(r.get("washout"))
    other_reimbursements = _money(r.get("other_reimbursements"))

    total = _money(tolls + scales + parking + lumper + washout + other_reimbursements)

    return {
        "tolls": float(tolls),
        "scales": float(scales),
        "parking": float(parking),
        "lumper": float(lumper),
        "washout": float(washout),
        "other_reimbursements": float(other_reimbursements),
        "total_reimbursements": float(total),
    }

def compute_deductions(deductions: dict, taxable_gross: Decimal) -> dict:
    """
    Deductions:
    fixed + percentage-based + common trucking chargebacks
    """
    d = deductions or {}

    # common fixed deductions
    fuel = _money(d.get("fuel"))
    advances = _money(d.get("advances"))
    escrow = _money(d.get("escrow"))
    insurance = _money(d.get("insurance"))
    equipment = _money(d.get("equipment"))
    chargebacks = _money(d.get("chargebacks"))
    garnishments = _money(d.get("garnishments"))
    other_deductions = _money(d.get("other_deductions"))

    fixed_total = _money(fuel + advances + escrow + insurance + equipment + chargebacks + garnishments + other_deductions)

    # optional percent deduction off taxable gross (example: admin_fee_pct: 5)
    admin_fee_pct = _pct(d.get("admin_fee_pct"))
    admin_fee = _money(taxable_gross * admin_fee_pct)

    # optional percent fuel surcharge / factoring fee etc.
    factoring_fee_pct = _pct(d.get("factoring_fee_pct"))
    factoring_fee = _money(taxable_gross * factoring_fee_pct)

    total = _money(fixed_total + admin_fee + factoring_fee)

    return {
        "fuel": float(fuel),
        "advances": float(advances),
        "escrow": float(escrow),
        "insurance": float(insurance),
        "equipment": float(equipment),
        "chargebacks": float(chargebacks),
        "garnishments": float(garnishments),
        "other_deductions": float(other_deductions),
        "admin_fee": float(admin_fee),
        "factoring_fee": float(factoring_fee),
        "total_deductions": float(total),
    }


# ---------- main engine ----------
def run_payroll(contractors):
    """
    contractors = [
      {
        "contractor_id": "drv_001",
        "pay_type": "mile" | "flat",
        "miles": 1200,
        "rate_per_mile": 0.65,
        "gross_pay": 2500,
        "earnings": {...},         # detention, layover, stops, tonu, etc
        "reimbursements": {...},   # tolls, lumper, etc
        "deductions": {...}        # fuel, escrow, % fees, etc
      }
    ]
    """
    contractors = contractors or []
    results = []

    for c in contractors:
        pay_type = (c.get("pay_type") or "flat").lower()

        if pay_type == "mile":
            base_gross = calculate_miles_pay(c.get("miles"), c.get("rate_per_mile"))
        else:
            base_gross = _money(c.get("gross_pay"))

        earnings_breakdown = compute_earnings(c.get("earnings") or {})
        earnings_total = _money(earnings_breakdown.get("total_earnings_accessorials"))

        taxable_gross = _money(base_gross + earnings_total)

        reimburse_breakdown = compute_reimbursements(c.get("reimbursements") or {})
        reimburse_total = _money(reimburse_breakdown.get("total_reimbursements"))

        deductions_breakdown = compute_deductions(c.get("deductions") or {}, taxable_gross)
        deductions_total = _money(deductions_breakdown.get("total_deductions"))

        net = _money(taxable_gross - deductions_total + reimburse_total)

        results.append({
            "contractor_id": c.get("contractor_id"),
            "pay_type": pay_type,
            "base_gross": float(base_gross),
            "taxable_gross": float(taxable_gross),
            "earnings": earnings_breakdown,
            "reimbursements": reimburse_breakdown,
            "deductions": deductions_breakdown,
            "net_pay": float(net),
        })

    return results
