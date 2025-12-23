# FreightPay/bookkeeping/ledger.py

from datetime import datetime
from typing import List, Dict

# In-memory ledger (replace with DB later)
LEDGER: List[Dict] = []


def record_payroll_run(
    pay_period: str,
    contractor_id: str,
    gross: float,
    reimbursements: float,
    deductions: float,
    net: float,
) -> Dict:
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "pay_period": pay_period,
   "contractor_id": contractor_id,
        "gross": round(float(gross), 2),
        "reimbursements": round(float(reimbursements), 2),
        "deductions": round(float(deductions), 2),
        "net": round(float(net), 2),
    }
    LEDGER.append(entry)
    return entry


def get_ledger() -> List[Dict]:
    return LEDGER


def clear_ledger() -> None:
    LEDGER.clear()


> On Dec 22, 2025, at 7:39 PM, Ashley Ross <info@120mgmt.com> wrote:
>
> ﻿# integrations/gusto/config.py

> import os
>
>
> class GustoConfig:
>    """
>    Centralized Gusto configuration.
>    Uses environment variables only.
>    No demo logic. No hardcoded values.
>    """
>
>    def __init__(self):
>        self.client_id = os.getenv("GUSTO_CLIENT_ID")
>        self.client_secret = os.getenv("GUSTO_CLIENT_SECRET")
>        self.redirect_uri = os.getenv("GUSTO_REDIRECT_URI")
>        self.environment = os.getenv("GUSTO_ENV", "production").lower()
>
>        if not all([self.client_id, self.client_secret, self.redirect_uri]):
>            raise RuntimeError("Missing required Gusto environment variables")
>
>    @property
>    def authorize_url(self):
>        if self.environment == "production":
>            return "https://api.gusto.com/oauth/authorize"
>        return "https://api.gusto-demo.com/oauth/authorize"
>
>    @property
>    def token_url(self):
>        if self.environment == "production":
>            return "https://api.gusto.com/oauth/token"
>        return "https://api.gusto-demo.com/oauth/token"
>
>    @property
>    def api_base(self):
>        if self.environment == "production":
>            return "https://api.gusto.com"
>        return "https://api.gusto-demo.com"

  
