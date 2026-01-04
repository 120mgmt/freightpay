# create_tables.py
# RUN ONCE — creates all tables from existing models

from app import app
from db import db

with app.app_context():
    db.create_all()
    print("ALL TABLES CREATED")
