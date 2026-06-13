"""Application config for the accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Config for the accounts app: custom User model with UUID PKs."""

    default_auto_field = "django.db.models.UUIDField"
    name = "accounts"
    verbose_name = "Accounts"
