"""Stub User model so AUTH_USER_MODEL resolves during Foundation.

The real User model (UUID PK, email login, custom manager) lands in the
auth spec. This stub exists only so `config.settings.base` can be
imported before the auth spec ships.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Placeholder User; the auth spec replaces this with the real model."""

    class Meta:
        """Django meta options for the placeholder User model."""

        app_label = "accounts"
