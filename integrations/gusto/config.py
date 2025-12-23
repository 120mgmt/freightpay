# integrations/gusto/config.py
import os


class GustoConfig:
    """
    Centralized Gusto configuration.
    Uses environment variables only.
    No demo logic. No hardcoded values.
    """

    def __init__(self):
        self.client_id = os.getenv("GUSTO_CLIENT_ID")
        self.client_secret = os.getenv("GUSTO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GUSTO_REDIRECT_URI")
        self.environment = os.getenv("GUSTO_ENV", "production").lower()

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise RuntimeError("Missing required Gusto environment variables")

    @property
    def authorize_url(self):
        if self.environment == "production":
            return "https://api.gusto.com/oauth/authorize"
        return "https://api.gusto-demo.com/oauth/authorize"

    @property
    def token_url(self):
        if self.environment == "production":
            return "https://api.gusto.com/oauth/token"
        return "https://api.gusto-demo.com/oauth/token"

    @property
    def api_base(self):
        if self.environment == "production":
            return "https://api.gusto.com"
        return "https://api.gusto-demo.com"
