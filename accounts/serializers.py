"""Serializers for the accounts app: register, login, and user read-out."""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Read-only `{id, email}` representation of a User."""

    class Meta:
        """ModelSerializer metadata for the read-only user payload."""

        model = User
        fields = ("id", "email")
        read_only_fields = ("id", "email")


class RegisterSerializer(serializers.ModelSerializer):
    """`{email, password, password_confirm}` — creates a User on save.

    Validates:
      - `password == password_confirm`
      - email uniqueness (inherited from the `User.email` unique field)
      - the 4 `AUTH_PASSWORD_VALIDATORS` via `validate_password()`
    """

    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        """ModelSerializer metadata for the register payload."""

        model = User
        fields = ("email", "password", "password_confirm")
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Confirm passwords match and run the configured password validators."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data: dict[str, object]) -> User:
        """Create a user via the manager; drop the confirm field before persisting."""
        validated_data.pop("password_confirm")
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )


class LoginSerializer(serializers.Serializer):
    """`{email, password}` — fields-only validation; SimpleJWT does the auth.

    The serializer does not include the user object in errors and the view
    returns the same generic failure whether the email is unknown or the
    password is wrong (auth spec §4, "Login enumeration").
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
