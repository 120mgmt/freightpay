# File: payroll/contractor_pay.py
# Purpose: FULL deployment contractor pay engine (miles/rate/gross/net) + accessorials + deductions + statement output
# Status: Production deployment-ready

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from payroll.settlement_models import Settlement, SettlementLineItem, LineItemType


TWOPLACES = Decimal("0.01")


def _d(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if x is None:
        return Decimal("0")
    return Decimal(str(x))


def _money(x: Any) -> Decimal:
    return _d(x).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _nonneg(name: str, v: Decimal) -> None:
    if v < 0:
        raise ValueError(f"{name} must be >= 0")


# -------------------------
# PAY MODES
# -------------------------

@dataclass
class MilesPay:
    # Supports both simple and split miles
    miles: Decimal = Decimal("0")
    rate_per_mile: Decimal = Decimal("0")

    loaded_miles: Decimal = Decimal("0")
    empty_miles: Decimal = Decimal("0")
    loaded_rate: Decimal = Decimal("0")
    empty_rate: Decimal = Decimal("0")

    @classmethod
    def simple(cls, miles: Any, rate_per_mile: Any) -> "MilesPay":
        m = _d(miles)
        r = _d(rate_per_mile)
        _nonneg("miles", m)
        _nonneg("rate_per_mile", r)
        return cls(miles=m, rate_per_mile=r)

    @classmethod
    def split(
        cls,
        loaded_miles: Any,
        empty_miles: Any,
        loaded_rate: Any,
        empty_rate: Any,
    ) -> "MilesPay":
        lm = _d(loaded_miles)
        em = _d(empty_miles)
        lr = _d(loaded_rate)
        er = _d(empty_rate)

        _nonneg("loaded_miles", lm)
        _nonneg("empty_miles", em)
        _nonneg("loaded_rate", lr)
        _nonneg("empty_rate", er)

        return cls(
            loaded_miles=lm,
            empty_miles=em,
            loaded_rate=lr,
            empty_rate=er,
        )

    def total_miles(self) -> Decimal:
        if self.loaded_miles > 0 or self.empty_miles > 0:
            return self.loaded_miles + self.empty_miles
        return self.miles

    def gross_from_miles(self) -> Decimal:
        if self.loaded_miles > 0 or self.empty_miles > 0:
            gross = (self.loaded_miles * self.loaded_rate) + (self.empty_miles * self.empty_rate)
            return _money(gross)
        gross = self.miles * self.rate_per_mile
        return _money(gross)


@dataclass
class FlatPay:
    gross_pay: Decimal

    @classmethod
    def from_inputs(cls, gross_pay: Any) -> "FlatPay":
        g = _d(gross_pay)
        _nonneg("gross_pay", g)
        return cls(gross_pay=g)

    def gross(self) -> Decimal:
        return _money(self.gross_pay)


@dataclass
class PercentPay:
    revenue: Decimal
    percent: Decimal  # 0-100

    @classmethod
    def from_inputs(cls, revenue: Any, percent: Any) -> "PercentPay":
        r = _d(revenue)
        p = _d(percent)
        _nonneg("revenue", r)
        _nonneg("percent", p)
        if p > 100:
            raise ValueError("percent must be <= 100")
        return cls(revenue=r, percent=p)

    def gross(self) -> Decimal:
        return _money(self.revenue * (self.percent / Decimal("100")))


# -------------------------
# CONTRACTOR PAY STATEMENT
# -------------------------

@dataclass
class ContractorPayStatement:
    contractor_id: str

    # One pay mode is required
    miles_pay: Optional[MilesPay] = None
    flat_pay: Optional[FlatPay] = None
    percent_pay: Optional[PercentPay] = None

    settlements: List[Settlement] = field(default_factory=list)

    period_start: Optional[str] = None
    period_end: Optional[str] = None
    reference: Optional[str] = None

    def validate(self) -> None:
        modes = [self.miles_pay is not None, self.flat_pay is not None, self.percent_pay is not None]
        if sum(1 for x in modes if x) != 1:
            raise ValueError("Exactly one pay mode must be set: miles_pay OR flat_pay OR percent_pay")

        for s in self.settlements:
            if not isinstance(s, Settlement):
                raise ValueError("settlements must contain Settlement objects")
            for li in s.line_items:
                if not isinstance(li, SettlementLineItem):
                    raise ValueError("Settlement.line_items must contain SettlementLineItem objects")
                li.validate()

    # ---- totals ----

    def base_gross(self) -> Decimal:
        if self.miles_pay is not None:
            return self.miles_pay.gross_from_miles()
        if self.flat_pay is not None:
            return self.flat_pay.gross()
        if self.percent_pay is not None:
            return self.percent_pay.gross()
        raise ValueError("No pay mode configured")

    def accessorials_total(self) -> Decimal:
        total = Decimal("0")
        for s in self.settlements:
            total += _d(s.total_accessorials())
        return _money(total)

    def deductions_total(self) -> Decimal:
        total = Decimal("0")
        for s in self.settlements:
            total += _d(s.total_deductions())
        return _money(total)

    def gross_total(self) -> Decimal:
        return _money(self.base_gross() + self.accessorials_total())

    def net_total(self) -> Decimal:
        return _money(self.gross_total() - self.deductions_total())

    # ---- audit ----

    def line_items(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for s in self.settlements:
            for li in s.line_items:
                out.append(
                    {
                        "driver_id": getattr(s, "driver_id", None),
                        "type": li.item_type.value,
                        "code": li.code,
                        "description": li.description,
                        "amount": float(_money(li.amount)),
                    }
                )
        return out

    def categorized_totals(self) -> Dict[str, Dict[str, float]]:
        buckets: Dict[str, Dict[str, Decimal]] = {
            "accessorial": {},
            "deduction": {},
            "reimbursement": {},
        }
        for s in self.settlements:
            for li in s.line_items:
                t = li.item_type.value
                buckets.setdefault(t, {})
                buckets[t][li.code] = buckets[t].get(li.code, Decimal("0")) + _d(li.amount)

        return {t: {code: float(_money(amt)) for code, amt in codes.items()} for t, codes in buckets.items()}

    def summary(self) -> Dict[str, Any]:
        self.validate()

        pay_mode = "miles" if self.miles_pay is not None else "flat" if self.flat_pay is not None else "percent"

        payload: Dict[str, Any] = {
            "contractor_id": self.contractor_id,
            "pay_mode": pay_mode,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "reference": self.reference,
            "base_gross": float(self.base_gross()),
            "accessorials_total": float(self.accessorials_total()),
            "deductions_total": float(self.deductions_total()),
            "gross_total": float(self.gross_total()),
            "net_total": float(self.net_total()),
            "categorized_totals": self.categorized_totals(),
            "line_items": self.line_items(),
        }

        if self.miles_pay is not None:
            payload["miles"] = {
                "miles": float(_money(self.miles_pay.miles)),
                "rate_per_mile": float(_money(self.miles_pay.rate_per_mile)),
                "loaded_miles": float(_money(self.miles_pay.loaded_miles)),
                "empty_miles": float(_money(self.miles_pay.empty_miles)),
                "loaded_rate": float(_money(self.miles_pay.loaded_rate)),
                "empty_rate": float(_money(self.miles_pay.empty_rate)),
                "total_miles": float(_money(self.miles_pay.total_miles())),
                "gross_from_miles": float(self.miles_pay.gross_from_miles()),
            }

        if self.flat_pay is not None:
            payload["flat"] = {"gross_pay": float(_money(self.flat_pay.gross_pay))}

        if self.percent_pay is not None:
            payload["percent"] = {
                "revenue": float(_money(self.percent_pay.revenue)),
                "percent": float(_money(self.percent_pay.percent)),
                "gross": float(self.percent_pay.gross()),
            }

        return payload


# -------------------------
# FACTORY: BUILD STATEMENT FROM RAW INPUT (what your UI/API sends)
# -------------------------

def build_contractor_statement(payload: Dict[str, Any]) -> ContractorPayStatement:
    """
    Accepts payload shaped like your existing repo patterns:
      - id / contractor_id
      - pay_type: mile | flat | percent
      - mile: miles + rate_per_mile OR split (loaded/empty)
      - accessorials: list of {code, description, amount}
      - deductions: list of {code, description, amount}

    CPM Gate (profit floor) triggers ONLY when these are present:
      - company_id
      - trip miles (trip_miles OR miles OR loaded_miles+empty_miles)
      - offered/customer rate (offered_rate_per_mile OR offered_rate_total OR customer_total)
    """
    contractor_id = payload.get("contractor_id") or payload.get("id")
    if not contractor_id:
        raise ValueError("Missing contractor_id")

    pay_type = str(payload.get("pay_type", "flat")).strip().lower()

    # -------------------------
    # CPM PROFIT GATE (BEGINNING)
    # -------------------------
    company_id = payload.get("company_id")
    offered_rate_per_mile = payload.get("offered_rate_per_mile")
    offered_rate_total = payload.get("offered_rate_total")

    # Support customer-side naming if used by UI
    if offered_rate_total is None:
        offered_rate_total = payload.get("customer_total")

    # Trip miles resolution
    trip_miles = payload.get("trip_miles")
    if trip_miles is None:
        if payload.get("loaded_miles") is not None or payload.get("empty_miles") is not None:
            trip_miles = (payload.get("loaded_miles") or 0) + (payload.get("empty_miles") or 0)
        else:
            trip_miles = payload.get("miles")

    should_gate = (
        company_id is not None
        and trip_miles is not None
        and (offered_rate_per_mile is not None or offered_rate_total is not None)
    )

    if should_gate:
        from services.pricing_cpm_gate import evaluate_offer  # local import to avoid hard coupling

        evaluate_offer(
            int(company_id),
            trip_miles=_d(trip_miles),
            offered_rate_total=_d(offered_rate_total) if offered_rate_total is not None else None,
            offered_rate_per_mile=_d(offered_rate_per_mile) if offered_rate_per_mile is not None else None,
        )

    # settlements -> convert accessorials/deductions into Settlement/LineItems (driver_id may be contractor_id)
    driver_id = payload.get("driver_id") or contractor_id
    line_items: List[SettlementLineItem] = []

    # accessorials
    for a in payload.get("accessorials", []) or []:
        line_items.append(
            SettlementLineItem(
                code=str(a.get("code", "")).strip().upper(),
                description=str(a.get("description", "")).strip(),
                amount=float(a.get("amount", 0)),
                item_type=LineItemType.ACCESSORIAL,
            )
        )

    # deductions
    for d in payload.get("deductions", []) or []:
        line_items.append(
            SettlementLineItem(
                code=str(d.get("code", "")).strip().upper(),
                description=str(d.get("description", "")).strip(),
                amount=float(d.get("amount", 0)),
                item_type=LineItemType.DEDUCTION,
            )
        )

    settlements = [Settlement(driver_id=driver_id, line_items=line_items)]

    miles_pay: Optional[MilesPay] = None
    flat_pay: Optional[FlatPay] = None
    percent_pay: Optional[PercentPay] = None

    if pay_type == "mile":
        # split preferred if present
        if (payload.get("loaded_miles") is not None or payload.get("empty_miles") is not None) and (
            payload.get("loaded_rate") is not None or payload.get("empty_rate") is not None
        ):
            miles_pay = MilesPay.split(
                loaded_miles=payload.get("loaded_miles", 0),
                empty_miles=payload.get("empty_miles", 0),
                loaded_rate=payload.get("loaded_rate", 0),
                empty_rate=payload.get("empty_rate", 0),
            )
        else:
            miles_pay = MilesPay.simple(
                miles=payload.get("miles", 0),
                rate_per_mile=payload.get("rate_per_mile", payload.get("rate", 0)),
            )

    elif pay_type == "percent":
        percent_pay = PercentPay.from_inputs(
            revenue=payload.get("revenue", 0),
            percent=payload.get("percent", 0),
        )

    else:  # flat
        flat_pay = FlatPay.from_inputs(payload.get("gross_pay", payload.get("gross", 0)))

    stmt = ContractorPayStatement(
        contractor_id=str(contractor_id),
        miles_pay=miles_pay,
        flat_pay=flat_pay,
        percent_pay=percent_pay,
        settlements=settlements,
        period_start=payload.get("period_start"),
        period_end=payload.get("period_end"),
        reference=payload.get("reference"),
    )

    stmt.validate()
    return stmt


def compute_contractor_pay(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function: build + return summary dict (gross/net + breakdown).
    """
    return build_contractor_statement(payload).summary()
