def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(default)

def compute_earnings(earnings: dict) -> dict:
    """
    Earnings add to taxable gross (unless you later separate taxable/non-taxable by worker type).
    Standard trucking earnings:
      - detention (hours * rate)
      - layover (flat)
      - stop pay (stops * rate)
      - TONU (flat)
      - breakdown (hours * rate) or flat if you use breakdown_flat
      - bonuses (flat)
      - minimum guarantee (weekly guarantee logic handled in engine)
    """
    e = earnings or {}

    detention = _f(e.get("detention_hours")) * _f(e.get("detention_rate"))
    layover = _f(e.get("layover"))
    stop_pay = _f(e.get("stops")) * _f(e.get("stop_rate"))
    tonu = _f(e.get("tonu"))

    breakdown = (_f(e.get("breakdown_hours")) * _f(e.get("breakdown_rate"))) + _f(e.get("breakdown_flat"))
    bonuses = _f(e.get("bonuses"))

    total = round(detention + layover + stop_pay + tonu + breakdown + bonuses, 2)

    return {
        "detention": round(detention, 2),
        "layover": round(layover, 2),
        "stop_pay": round(stop_pay, 2),
        "tonu": round(tonu, 2),
        "breakdown": round(breakdown, 2),
        "bonuses": round(bonuses, 2),
        "total_earnings_accessorials": total,
    }

def compute_reimbursements(reimbursements: dict) -> dict:
    """
    Reimbursements are pass-through payments.
    These generally DO NOT reduce taxable gross; they are paid in addition to net.
    """
    r = reimbursements or {}
    tolls = _f(r.get("tolls"))
    scales = _f(r.get("scales"))
    parking = _f(r.get("parking"))
    lumper = _f(r.get("lumper"))
    washout = _f(r.get("washout"))
    other = _f(r.get("other"))

    total = round(tolls + scales + parking + lumper + washout + other, 2)

    return {
        "tolls": round(tolls, 2),
        "scales": round(scales, 2),
        "parking": round(parking, 2),
        "lumper": round(lumper, 2),
        "washout": round(washout, 2),
        "other": round(other, 2),
        "total_reimbursements": total,
    }

def compute_deductions(deductions: dict, taxable_gross: float) -> dict:
    """
    Deductions reduce net pay.
    Standard trucking deductions:
      - percent (e.g., 0.10)
      - fixed
      - fuel_advance_repay
      - escrow_hold (subtract)
      - escrow_release (add back as negative deduction)
      - equipment_rental
      - insurance
      - chargebacks
      - garnishments
      - other
    """
    d = deductions or {}

    percent = _f(d.get("percent"))
    if percent > 1:  # allows user to pass 10 for 10%
        percent = percent / 100.0

    percent_amt = taxable_gross * percent
    fixed = _f(d.get("fixed"))
    fuel_adv = _f(d.get("fuel_advance_repay"))
    escrow_hold = _f(d.get("escrow_hold"))
    escrow_release = _f(d.get("escrow_release"))
    equip = _f(d.get("equipment_rental"))
    insurance = _f(d.get("insurance"))
    chargebacks = _f(d.get("chargebacks"))
    garnishments = _f(d.get("garnishments"))
    other = _f(d.get("other"))

    # escrow_release reduces deductions (adds back to driver)
    total = percent_amt + fixed + fuel_adv + escrow_hold + equip + insurance + chargebacks + garnishments + other - escrow_release
    total = round(total, 2)

    return {
        "percent": round(percent, 4),
        "percent_amt": round(percent_amt, 2),
        "fixed": round(fixed, 2),
        "fuel_advance_repay": round(fuel_adv, 2),
        "escrow_hold": round(escrow_hold, 2),
        "escrow_release": round(escrow_release, 2),
        "equipment_rental": round(equip, 2),
        "insurance": round(insurance, 2),
        "chargebacks": round(chargebacks, 2),
        "garnishments": round(garnishments, 2),
        "other": round(other, 2),
        "total_deductions": total,
    }
