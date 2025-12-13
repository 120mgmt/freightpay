
class Config:
    SECRET_KEY = "CHANGE_THIS_KEY"
    SQLALCHEMY_DATABASE_URI = "sqlite:///freightpay.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STRIPE_PUBLIC_KEY = "your_stripe_pub_key"
    STRIPE_SECRET_KEY = "your_stripe_secret_key"
