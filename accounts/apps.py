"""Application config for the accounts app."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Placeholder config. The User model and auth code land in the auth spec."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts"
