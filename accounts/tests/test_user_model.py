"""Tests for the custom User model field set and manager."""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_user_pk_is_uuid() -> None:
    """The primary key is a UUID4 (not an integer)."""
    user = User.objects.create_user(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )

    assert isinstance(user.pk, uuid.UUID)


def test_user_email_is_unique() -> None:
    """Two users cannot share an email."""
    User.objects.create_user(
        email="bob@example.com",
        password="correct-horse-battery-staple",
    )
    with pytest.raises(Exception) as excinfo:
        User.objects.create_user(
            email="bob@example.com",
            password="correct-horse-battery-staple",
        )

    assert "email" in str(excinfo.value).lower() or "unique" in str(excinfo.value).lower()


def test_user_has_no_username_field() -> None:
    """The custom User model drops the username column entirely."""
    field_names = {field.name for field in User._meta.get_fields()}

    assert "username" not in field_names


def test_user_has_no_is_staff_or_is_superuser() -> None:
    """Admin flags are deferred to v2; the fields are absent on the model."""
    field_names = {field.name for field in User._meta.get_fields()}

    assert "is_staff" not in field_names
    assert "is_superuser" not in field_names


def test_user_email_is_login_field() -> None:
    """USERNAME_FIELD is 'email' and REQUIRED_FIELDS is empty."""
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []


def test_create_user_hashes_password() -> None:
    """create_user runs set_password; the stored value is not the raw password."""
    user = User.objects.create_user(
        email="carol@example.com",
        password="correct-horse-battery-staple",
    )

    assert user.password != "correct-horse-battery-staple"
    assert user.check_password("correct-horse-battery-staple") is True


def test_create_user_rejects_blank_email() -> None:
    """The manager rejects an empty email (ValueError from normalize_email)."""
    with pytest.raises((TypeError, ValueError)):
        User.objects.create_user(
            email="",
            password="correct-horse-battery-staple",
        )


def test_user_is_active_defaults_true() -> None:
    """Newly created users are active by default."""
    user = User.objects.create_user(
        email="dave@example.com",
        password="correct-horse-battery-staple",
    )

    assert user.is_active is True
