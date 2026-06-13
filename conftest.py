"""Root pytest conftest — shared fixtures for every test module in the repo.

Pytest auto-discovers this conftest for every test file (the rootdir
is the parent of this file). The `user` and `other_user` fixtures
are defined here so both the `accounts` and `features` test suites
can depend on them without cross-directory `pytest_plugins`
re-imports, which collide when the full suite runs (`accounts/tests/
conftest.py` is loaded natively first, then a re-import tries to
register the same module and pytest raises `ValueError: Plugin
already registered`).
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
