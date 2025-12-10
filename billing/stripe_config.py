
import stripe

def stripe_init(app):
    stripe.api_key = app.config.get("STRIPE_SECRET_KEY")
