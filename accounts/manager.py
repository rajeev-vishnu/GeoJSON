"""Custom user manager: email is the unique identifier, no superuser method."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import BaseUserManager

if TYPE_CHECKING:
    from accounts.models import User


class UserManager(BaseUserManager):
    """Manager that uses email as the unique identifier.

    `create_superuser` is intentionally not defined; admin is out of scope
    for v1 (see auth spec §2 and the overview spec's out-of-scope list).
    Users are created via the public register endpoint.
    """

    use_in_migrations = True

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        """Create and save a User with the given email and hashed password."""
        if not email:
            raise ValueError("Users must have an email address")
        normalized_email = self.normalize_email(email)
        user = self.model(email=normalized_email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
