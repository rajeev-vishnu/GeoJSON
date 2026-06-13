"""Application config for the features app."""

from django.apps import AppConfig


class FeaturesConfig(AppConfig):
    """Placeholder config. The Feature model and API land in the feature specs."""

    default_auto_field = "django.db.models.UUIDField"
    name = "features"
    verbose_name = "Features"
