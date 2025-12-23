# gusto/__init__.py
"""
Gusto integration package.
Production-ready scaffold.
No demo logic. No hardcoded credentials.
"""

from .config import GustoConfig
from .client import GustoClient
__all__= [
    "GustoConfig",
    "GustoClient",
]
