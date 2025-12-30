# freightpay/models/__init__.py
# Explicit model imports to ensure metadata registration on app startup

from .user import User
from .base import Base
from .company import Company
from .driver import Driver
from .pay_config import PayConfig
from .payroll_run import PayrollRun
from .settlement import Settlement
from .ledger import LedgerEntry
from .legal_acceptance import LegalAcceptance

__all__ = [
    "User",
    "Base",
    "Company",
    "Driver",
    "PayConfig",
    "PayrollRun",
    "Settlement",
    "LedgerEntry",
    "LegalAcceptance"
]
