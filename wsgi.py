"""Production entry point:  gunicorn wsgi:app"""
from portfolio import create_app

app = create_app()
