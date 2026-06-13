"""Custom User model: email login, UUID PK, no username or admin flags."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser
from django.db import models

from accounts.manager import UserManager


class User(AbstractBaseUser):
    """Email-based user with a UUID primary key.

    Inherits `AbstractBaseUser` only (no `PermissionsMixin`): there is no
    `is_staff`, no `is_superuser`, no `last_login`, and no `date_joined`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        """Django meta options for the custom User model."""

        app_label = "accounts"

    def __str__(self) -> str:
        """Return the email as the human-readable identifier."""
        return self.email
