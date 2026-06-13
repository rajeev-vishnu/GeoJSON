"""Shared pytest fixtures for the accounts test suite.

The `user` and `other_user` fixtures are auto-discovered by pytest for any
test module under the repo (including the `features` app's tests; see the
Feature API spec §9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from accounts.models import User

UserModel: type[User] = get_user_model()


@pytest.fixture
def user(db: object) -> User:
    """Return a freshly created regular user, committed to the test DB."""
    return UserModel.objects.create_user(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )


@pytest.fixture
def other_user(db: object) -> User:
    """Return a second user, for tests that need two principals."""
    return UserModel.objects.create_user(
        email="bob@example.com",
        password="correct-horse-battery-staple",
    )
