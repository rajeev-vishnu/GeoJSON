"""ASGI entrypoint. Not used in v1 (gunicorn runs WSGI) but provided for completeness."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
