"""Application config for the frontend app."""

from django.apps import AppConfig


class FrontendConfig(AppConfig):
    """Placeholder config. Templates and views land in the frontend spec."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "frontend"
    verbose_name = "Frontend"
