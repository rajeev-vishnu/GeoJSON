"""Tests for the accounts serializers."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.serializers import LoginSerializer, RegisterSerializer, UserSerializer

User = get_user_model()


@pytest.fixture
def existing_user(db: object) -> User:
    """Create a user that the read-only serializer can serialize."""
    return User.objects.create_user(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )


def test_user_serializer_returns_id_and_email(existing_user: User) -> None:
    """UserSerializer.to_representation is exactly {id, email}."""
    body = UserSerializer(existing_user).data

    assert set(body.keys()) == {"id", "email"}
    assert body["email"] == "alice@example.com"
    assert body["id"] == str(existing_user.pk)


def test_user_serializer_is_read_only() -> None:
    """UserSerializer has no writable fields (id, email, is_active are all read-only)."""
    serializer = UserSerializer()

    for field in serializer.fields.values():
        assert field.read_only is True, f"Field {field.name} should be read-only"


def test_register_serializer_fields() -> None:
    """RegisterSerializer exposes email, password, password_confirm."""
    serializer = RegisterSerializer()

    assert set(serializer.fields.keys()) == {"email", "password", "password_confirm"}


def test_register_serializer_rejects_password_mismatch(db: object) -> None:
    """When password != password_confirm, the serializer raises a validation error."""
    payload = {
        "email": "carol@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "different-password-here",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "password_confirm" in serializer.errors


def test_register_serializer_rejects_short_password(db: object) -> None:
    """7-char password is rejected by the 8-char MinimumLengthValidator.

    Errors raised from `validate()` (which is where validate_password runs) are
    surfaced under `non_field_errors` by DRF, not under the password field.
    """
    payload = {
        "email": "dave@example.com",
        "password": "abcdefg",
        "password_confirm": "abcdefg",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors
    assert any("too short" in str(error).lower() for error in serializer.errors["non_field_errors"])


def test_register_serializer_rejects_duplicate_email(db: object) -> None:
    """Registering with an already-used email returns a uniqueness error."""
    User.objects.create_user(
        email="erin@example.com",
        password="correct-horse-battery-staple",
    )

    payload = {
        "email": "erin@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "correct-horse-battery-staple",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "email" in serializer.errors


def test_register_serializer_creates_user(db: object) -> None:
    """On valid input, save() creates a user with the email and a hashed password."""
    payload = {
        "email": "frank@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "correct-horse-battery-staple",
    }
    serializer = RegisterSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    user = serializer.save()

    assert isinstance(user, User)
    assert user.email == "frank@example.com"
    assert user.check_password("correct-horse-battery-staple") is True
    assert user.password != "correct-horse-battery-staple"


def test_register_serializer_runs_all_password_validators(db: object) -> None:
    """The 4 AUTH_PASSWORD_VALIDATORS run on register (smoke: common password rejected).

    Errors raised from `validate()` (which is where validate_password runs) are
    surfaced under `non_field_errors` by DRF, not under the password field.
    """
    payload = {
        "email": "common@example.com",
        "password": "password",
        "password_confirm": "password",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors
    assert any("common" in str(error).lower() for error in serializer.errors["non_field_errors"])


def test_validate_password_helper_invokes_common_validator() -> None:
    """validate_password from django.contrib.auth.password_validation runs the validators.

    This is a smoke check that the import path used by RegisterSerializer is
    wired up correctly. The deeper test is the register-rejects-common-password
    test above.
    """
    validate_password("correct-horse-battery-staple")
    with pytest.raises(ValidationError):
        validate_password("password")


def test_login_serializer_fields() -> None:
    """LoginSerializer exposes only email and password (no confirm, no extras)."""
    serializer = LoginSerializer()

    assert set(serializer.fields.keys()) == {"email", "password"}


def test_login_serializer_passes_through_unknown_email() -> None:
    """LoginSerializer.is_valid() returns True for an unknown email.

    SimpleJWT's TokenObtainPairView is the actual auth; the serializer is
    fields-only. The serializer must NOT raise on a missing user (the
    enumeration-leak prevention is at the view layer).
    """
    payload = {"email": "nobody@example.com", "password": "irrelevant"}
    serializer = LoginSerializer(data=payload)

    assert serializer.is_valid()
