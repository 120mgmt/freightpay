# billing/__init__.py

from billing.subscription_gate import require_active_subscription

__all__ = ["require_active_subscription"]
