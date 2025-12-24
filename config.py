# config.py
import os


class Config:
    APP_ENV = os.getenv("APP_ENV", "prod")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "change-me"))
