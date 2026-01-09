# wsgi.py
# REQUIRED ENTRYPOINT FOR RENDER / GUNICORN
# DO NOT DELETE

from app import app

# Gunicorn looks for `app` here:
# gunicorn wsgi:app
