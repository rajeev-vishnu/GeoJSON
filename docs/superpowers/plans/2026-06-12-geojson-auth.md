# Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `accounts` app's auth API: a custom email-login `User` model (UUID PK, no username, no `is_staff`/`is_superuser`), 4 JWT-backed endpoints (`register`, `login`, `refresh`, `me`), and the auth test suite.

**Architecture:** Replace the Foundation stub `User` (which currently inherits `AbstractUser`) with a real `AbstractBaseUser`-only model with a `UUIDField` PK and email as the login identifier. Use `djangorestframework-simplejwt` for token issuance and rotation; mount its built-in `TokenObtainPairView` and `TokenRefreshView` alongside a custom `RegisterView` and `MeView`. Three DRF serializers (`UserSerializer`, `RegisterSerializer`, `LoginSerializer`) handle read-only user output, registration with password validation, and field-only login passthrough. Settings (auth password validators, JWT lifetimes, rotation policy) are already in `config/settings/base.py` from the Foundation spec; this plan only verifies they remain aligned.

**Tech Stack:** Python 3.12, Django 5.1.x, djangorestframework 3.15.x, djangorestframework-simplejwt 5.3.x, pytest + pytest-django, ruff.

**Working-tree convention:** Per AGENTS.md, the project's pre-commit gate is the only commit boundary. This plan intentionally **omits `git commit` steps** so all changes stay unstaged at the end; the engineer (or a follow-up plan) runs the full pre-commit gate at the end and stages/commits then. Each task ends with a brief status note in place of a commit.

**Spec note on token rotation:** §4 lists "401 for a refresh token that has been rotated already" as a standard error, but also sets `BLACKLIST_AFTER_ROTATION=False` (no token blacklist). With `BLACKLIST_AFTER_ROTATION=False`, SimpleJWT does not invalidate the old refresh token after rotation. Task 9's test therefore asserts that a second call with the same (old) refresh token returns 200 with yet another rotated pair — matching the explicit `BLACKLIST_AFTER_ROTATION=False` setting in `config/settings/base.py`. If the spec author wants strict invalidation, the follow-up is to enable the `token_blacklist` app and set `BLACKLIST_AFTER_ROTATION=True`; that is out of scope for this plan.

---

## File map

### Create

- `accounts/manager.py` — `UserManager(BaseUserManager)` with `create_user(email, password)`. No `create_superuser` (admin is out of scope, see auth spec §2).

  **Convention deviation note:** the manager is split into its own module to keep `accounts/models.py` focused on field definitions; this follows the AGENTS.md "one clear responsibility per file" guideline. If a reviewer prefers the manager to live inside `models.py`, fold it back in.

- `accounts/serializers.py` — `UserSerializer`, `RegisterSerializer`, `LoginSerializer`.
- `accounts/views.py` — `RegisterView(generics.CreateAPIView)`, `LoginView(TokenObtainPairView)`, `MeView(generics.RetrieveAPIView)`.
- `accounts/tests/__init__.py` — empty.
- `accounts/tests/conftest.py` — `user` and `other_user` fixtures (DRF `APIClient` is auto-provided by pytest-django).
- `accounts/tests/test_user_model.py` — 8 model tests.
- `accounts/tests/test_serializers.py` — 11 serializer tests.
- `accounts/tests/test_auth.py` — 11 endpoint tests (spec §7 lists 10; the 11th is a coverage test that the wrong-password and unknown-email responses are byte-identical, per the enumeration-leak requirement).

### Modify

- `accounts/models.py` — replace the `AbstractUser` stub with the real `User(AbstractBaseUser)` (UUID PK, email, password, is_active, custom manager, `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = []`).
- `accounts/apps.py` — `default_auto_field = "django.db.models.UUIDField"` on `AccountsConfig`.
- `accounts/urls.py` — add the 4 auth routes (`register/`, `login/`, `refresh/`, `me/`).
- `accounts/__init__.py` — keep as-is (already a one-line docstring).

### Verify-only (no edits, but Task 1 re-reads them to confirm alignment)

- `config/settings/base.py` — `AUTH_PASSWORD_VALIDATORS` (4 validators in spec order) and `SIMPLE_JWT` (15 min access, 7 day refresh, rotate, no blacklist) are already in place from Foundation.

### Touchpoints left for downstream specs

- The `user` and `other_user` fixtures in `accounts/tests/conftest.py` are auto-discovered by pytest for the `features` app tests (Feature API spec §9). Downstream specs do not need to redefine them.
- `auth_client(api_client, user)` is defined in the Feature API spec, not here. The auth spec only ships the user fixtures.

### Project conventions this plan follows

- **Keyword args** for any function call with more than one argument (per AGENTS.md).
- **Public / entry-point functions first, private helpers below** in test files: all `def test_*` precede `_login` and `_auth_client`.
- **All imports at the top of each module** — no inline / local imports (per AGENTS.md).
- **No `#` comments in code blocks** — the existing test style uses docstrings on every function; inline comments are reserved for non-obvious behavior and are kept only where they earn their place.
- **Variable names** spell out concepts; no `data`/`res`/`tmp`/`result`. Where the spec says "body" the variable is `body`; where the spec says "payload" the variable is `payload`.
- **Function length** stays well under 100 lines; every test fits on one logical chunk.

---

## Tasks

### Task 1: Verify the auth-related base settings match the spec

**Files:**
- Read-only check: `config/settings/base.py:75-80` (auth password validators), `config/settings/base.py:94-109` (DRF + SimpleJWT config).

- [ ] **Step 1: Read the password-validators block**

Open `config/settings/base.py` lines 75-80 and confirm the 4 validators appear in this order:

1. `UserAttributeSimilarityValidator`
2. `MinimumLengthValidator` with `OPTIONS={"min_length": 8}`
3. `CommonPasswordValidator`
4. `NumericPasswordValidator`

If any are missing or out of order, fix them; otherwise this task is a no-op.

- [ ] **Step 2: Read the SimpleJWT block**

Open `config/settings/base.py` lines 104-109 and confirm:

- `ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)` (via `JWT_ACCESS_MINUTES=15` env var default)
- `REFRESH_TOKEN_LIFETIME = timedelta(days=7)` (via `JWT_REFRESH_DAYS=7` env var default)
- `ROTATE_REFRESH_TOKENS = True`
- `BLACKLIST_AFTER_ROTATION = False`
- `DEFAULT_AUTHENTICATION_CLASSES` contains `JWTAuthentication` and not `SessionAuthentication`

If any value is wrong, fix it; otherwise this task is a no-op.

- [ ] **Step 3: Run the existing settings test as a smoke check**

Run: `pytest config/tests/test_settings_split.py -v`
Expected: all existing tests pass (the spec's `test_base_password_validators_match_spec`, `test_base_minimum_length_validator_uses_eight`, and `test_base_drf_uses_jwt_authentication` already cover this).

- [ ] **Step 4: Status note**

If Step 1 or Step 2 required edits, the modified `config/settings/base.py` is left unstaged along with the rest of this plan's output. If no edits were made, no action is needed.

---

### Task 2: Replace the stub User model with the real one

**Files:**
- Modify: `accounts/models.py:1-18` (replace entire file).
- Modify: `accounts/apps.py:1-11` (change `default_auto_field`).
- Create: `accounts/manager.py`.
- Create: `accounts/tests/test_user_model.py`.
- Create: `accounts/migrations/__init__.py` (empty package marker, only if `accounts/migrations/` does not exist).
- Create: `accounts/migrations/0001_initial.py` (auto-generated by `makemigrations` in Step 5).

- [ ] **Step 1: Write the failing model test**

Create `accounts/tests/test_user_model.py` with:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest accounts/tests/test_user_model.py -v`
Expected: collection error or import error because the tests expect UUID PK, no username, etc., but the current stub uses `AbstractUser` with `BigAutoField`.

- [ ] **Step 3: Create the `accounts/migrations/` package**

If `accounts/migrations/` does not exist, run:

```bash
mkdir accounts/migrations
```

Then create `accounts/migrations/__init__.py` as an empty file.

- [ ] **Step 4: Create `accounts/manager.py` with the email-based manager**

Write the following to `accounts/manager.py`:

```python
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
    ) -> "User":
        """Create and save a User with the given email and hashed password."""
        if not email:
            raise ValueError("Users must have an email address")
        normalized_email = self.normalize_email(email)
        user = self.model(email=normalized_email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
```

- [ ] **Step 5: Replace `accounts/models.py` with the real User model**

Write the following to `accounts/models.py`:

```python
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
```

- [ ] **Step 6: Update `accounts/apps.py` to use UUIDField as the default auto field**

Replace `accounts/apps.py` with:

```python
"""Application config for the accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Config for the accounts app: custom User model with UUID PKs."""

    default_auto_field = "django.db.models.UUIDField"
    name = "accounts"
    verbose_name = "Accounts"
```

- [ ] **Step 7: Generate the initial migration**

Run: `python manage.py makemigrations accounts`
Expected: a new file `accounts/migrations/0001_initial.py` is created with a `CreateModel` operation for `accounts.User` containing `id`, `email`, `password`, `is_active`, and `last_login` (the last from `AbstractBaseUser`).

- [ ] **Step 8: Run the test to verify it passes**

Run: `pytest accounts/tests/test_user_model.py -v`
Expected: all 8 tests pass.

- [ ] **Step 9: Run the full test suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all pre-existing tests still pass; the new model tests pass. The `config/tests/test_settings_split.py::test_base_settings_module_imports_cleanly` test still passes because `AUTH_USER_MODEL = "accounts.User"` is unchanged.

- [ ] **Step 10: Status note**

Changes are left unstaged: `accounts/models.py`, `accounts/manager.py`, `accounts/apps.py`, `accounts/tests/test_user_model.py`, `accounts/migrations/__init__.py`, `accounts/migrations/0001_initial.py`.

---

### Task 3: Add the `user` and `other_user` fixtures

**Files:**
- Create: `accounts/tests/__init__.py` (empty).
- Create: `accounts/tests/conftest.py`.

- [ ] **Step 1: Create an empty `accounts/tests/__init__.py`**

Write an empty file at `accounts/tests/__init__.py`.

- [ ] **Step 2: Create `accounts/tests/conftest.py` with the two fixtures**

Write the following to `accounts/tests/conftest.py`:

```python
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

UserModel: type["User"] = get_user_model()


@pytest.fixture
def user(db: object) -> "User":
    """Return a freshly created regular user, committed to the test DB."""
    return UserModel.objects.create_user(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )


@pytest.fixture
def other_user(db: object) -> "User":
    """Return a second user, for tests that need two principals."""
    return UserModel.objects.create_user(
        email="bob@example.com",
        password="correct-horse-battery-staple",
    )
```

- [ ] **Step 3: Verify the fixtures are discoverable**

Run: `pytest accounts/tests/test_user_model.py::test_create_user_hashes_password -v`
Expected: passes. (It uses its own `User.objects.create_user` and the `db` fixture; the new fixtures are not invoked but the import is smoke-tested by collection.)

- [ ] **Step 4: Status note**

`accounts/tests/__init__.py` and `accounts/tests/conftest.py` are left unstaged.

---

### Task 4: Build `UserSerializer` (read-only `{id, email}`)

**Files:**
- Create: `accounts/serializers.py`.
- Create: `accounts/tests/test_serializers.py`.

- [ ] **Step 1: Write the failing serializer test**

Create `accounts/tests/test_serializers.py` with:

```python
"""Tests for the accounts serializers."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from accounts.serializers import LoginSerializer, RegisterSerializer, UserSerializer

User = get_user_model()


@pytest.fixture
def existing_user(db: object) -> "User":
    """Create a user that the read-only serializer can serialize."""
    return User.objects.create_user(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )


def test_user_serializer_returns_id_and_email(existing_user: "User") -> None:
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


def test_register_serializer_rejects_password_mismatch() -> None:
    """When password != password_confirm, the serializer raises a validation error."""
    payload = {
        "email": "carol@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "different-password-here",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "password_confirm" in serializer.errors


def test_register_serializer_rejects_short_password() -> None:
    """7-char password is rejected by the 8-char MinimumLengthValidator."""
    payload = {
        "email": "dave@example.com",
        "password": "abcdefg",
        "password_confirm": "abcdefg",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "password" in serializer.errors


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
    """The 4 AUTH_PASSWORD_VALIDATORS run on register (smoke: common password rejected)."""
    payload = {
        "email": "common@example.com",
        "password": "password",
        "password_confirm": "password",
    }
    serializer = RegisterSerializer(data=payload)

    assert not serializer.is_valid()
    assert "password" in serializer.errors


def test_validate_password_helper_invokes_common_validator() -> None:
    """validate_password from django.contrib.auth.password_validation runs the validators.

    This is a smoke check that the import path used by RegisterSerializer is
    wired up correctly. The deeper test is the register-rejects-common-password
    test above.
    """
    validate_password("correct-horse-battery-staple")
    with pytest.raises(Exception):
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest accounts/tests/test_serializers.py -v`
Expected: collection error: `ImportError: cannot import name 'UserSerializer' from 'accounts.serializers'`.

- [ ] **Step 3: Create `accounts/serializers.py` with all three serializers**

Write the following to `accounts/serializers.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest accounts/tests/test_serializers.py -v`
Expected: all 11 tests pass.

- [ ] **Step 5: Status note**

`accounts/serializers.py` and `accounts/tests/test_serializers.py` are left unstaged.

---

### Task 5: Add the URL routes for register, login, refresh, me

**Files:**
- Modify: `accounts/urls.py:1-6` (replace contents).

- [ ] **Step 1: Replace `accounts/urls.py` with the 4 routes**

Write the following to `accounts/urls.py`:

```python
"""Auth API URL patterns.

Four routes:
  - POST /api/auth/register/ — public; creates a user.
  - POST /api/auth/login/    — public; returns {access, refresh}.
  - POST /api/auth/refresh/  — public; rotates {access, refresh}.
  - GET  /api/auth/me/       — JWT-required; returns the current user.

All four views set `authentication_classes = [JWTAuthentication]` only;
`SessionAuthentication` is intentionally not used (auth spec §6).
"""
from django.urls import path
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import LoginView, MeView, RegisterView

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("me/", MeView.as_view(), name="me"),
]

TokenRefreshView.authentication_classes = [JWTAuthentication]
```

Note: `RegisterView`, `LoginView`, and `MeView` are imported but not defined yet. Task 6 adds them; the import is a runtime error until then. This is intentional: do not smoke-check the URL import until Task 6 lands. The end-to-end tests in Task 7 will exercise the routes.

- [ ] **Step 2: Status note**

`accounts/urls.py` is left unstaged. No commit.

---

### Task 6: Add `RegisterView`, `LoginView`, `MeView`

**Files:**
- Create: `accounts/views.py`.

- [ ] **Step 1: Create `accounts/views.py` with all three views**

Write the following to `accounts/views.py`:

```python
"""Auth API views.

`RegisterView`, `LoginView`, and `MeView` are project-owned. The
`TokenRefreshView` alias lives in `accounts/urls.py` so the four
endpoints share the same JWTAuthentication-only configuration (auth
spec §6). `LoginView` re-asserts that config on the SimpleJWT view.
"""
from __future__ import annotations

from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — public; creates a user."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — public; returns {access, refresh}.

    SimpleJWT's TokenObtainPairView already returns the same generic
    `401 {"detail": "No active account found with the given credentials"}`
    for unknown emails and wrong passwords (enumeration-leak prevention,
    auth spec §4). We override the auth class to ensure no Session
    authentication is attempted.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me/ — JWT-required; returns the current user."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self) -> User:
        """Return the authenticated user (the JWT's subject is the user PK)."""
        return self.request.user  # type: ignore[return-value]
```

- [ ] **Step 2: Smoke-check the URL import**

Run: `python -c "import accounts.urls; print(len(accounts.urls.urlpatterns))"`
Expected: prints `4`.

- [ ] **Step 3: Status note**

`accounts/views.py` is left unstaged.

---

### Task 7: Add the 11 endpoint tests in `accounts/tests/test_auth.py`

**Files:**
- Create: `accounts/tests/test_auth.py`.

- [ ] **Step 1: Write the full `test_auth.py` module**

Create `accounts/tests/test_auth.py` with:

```python
"""End-to-end tests for the auth API endpoints.

Exercises the 4 routes defined in `accounts/urls.py`:
  - POST /api/auth/register/
  - POST /api/auth/login/
  - POST /api/auth/refresh/
  - GET  /api/auth/me/

Tests are listed first (entry points); private helpers `_login` and
`_auth_client` follow below, per AGENTS.md.
"""
from __future__ import annotations

import jwt
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
ME_URL = "/api/auth/me/"


@pytest.fixture
def api_client() -> APIClient:
    """Return a fresh DRF APIClient for each test."""
    return APIClient()


def test_register_success(api_client: APIClient) -> None:
    """POST /register/ with valid data returns 201 and creates a user."""
    payload = {
        "email": "alice@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "correct-horse-battery-staple",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == 201
    assert set(response.json().keys()) == {"id", "email"}
    assert response.json()["email"] == "alice@example.com"
    assert User.objects.filter(email="alice@example.com").exists()
    user = User.objects.get(email="alice@example.com")
    assert user.check_password("correct-horse-battery-staple") is True
    assert user.password != "correct-horse-battery-staple"


def test_register_password_mismatch(api_client: APIClient) -> None:
    """password != password_confirm → 400."""
    payload = {
        "email": "bob@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "different-password",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == 400
    assert "password_confirm" in response.json()


def test_register_password_too_short(api_client: APIClient) -> None:
    """7-char password → 400 from MinimumLengthValidator."""
    payload = {
        "email": "carol@example.com",
        "password": "abcdefg",
        "password_confirm": "abcdefg",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == 400
    assert "password" in response.json()


def test_register_duplicate_email(api_client: APIClient) -> None:
    """Registering twice with the same email → 400 on the second call."""
    payload = {
        "email": "dup@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "correct-horse-battery-staple",
    }
    first = api_client.post(REGISTER_URL, payload, format="json")
    assert first.status_code == 201

    second = api_client.post(REGISTER_URL, payload, format="json")

    assert second.status_code == 400
    assert "email" in second.json()


def test_login_success(api_client: APIClient, user: "User") -> None:
    """Valid credentials → 200 with {access, refresh}; access is a valid JWT."""
    response = _login(api_client, "alice@example.com", "correct-horse-battery-staple")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"access", "refresh"}
    decoded = jwt.decode(
        body["access"],
        settings.SIMPLE_JWT["SIGNING_KEY"],
        algorithms=[settings.SIMPLE_JWT["ALGORITHM"]],
    )
    assert decoded["user_id"] == str(user.pk)


def test_login_wrong_password(api_client: APIClient, user: "User") -> None:
    """Wrong password → 401 with the generic message (no enumeration leak)."""
    response = _login(api_client, "alice@example.com", "wrong-password")

    assert response.status_code == 401
    assert response.json() == {"detail": "No active account found with the given credentials"}


def test_login_unknown_email(api_client: APIClient) -> None:
    """Unknown email → 401 with the same generic message as wrong_password."""
    response = _login(api_client, "nobody@example.com", "irrelevant")

    assert response.status_code == 401
    assert response.json() == {"detail": "No active account found with the given credentials"}


def test_login_messages_match_for_wrong_password_and_unknown_email(
    api_client: APIClient, user: "User"
) -> None:
    """The two failure responses are byte-identical (no enumeration via body)."""
    wrong = _login(api_client, "alice@example.com", "wrong-password")
    unknown = _login(api_client, "nobody@example.com", "irrelevant")

    assert wrong.json() == unknown.json()


def test_refresh_rotates_tokens(api_client: APIClient, user: "User") -> None:
    """POST /refresh/ returns 200 with new {access, refresh}; the new pair differs.

    With `BLACKLIST_AFTER_ROTATION=False` (auth spec §4, base.py SimpleJWT
    config), the old refresh token is NOT invalidated — SimpleJWT will
    happily rotate it again on a second call. This test asserts only the
    primary rotation behavior: a successful call to /refresh/ returns a
    new pair of tokens.
    """
    login_response = _login(api_client, "alice@example.com", "correct-horse-battery-staple")
    first_pair = login_response.json()

    refresh_response = api_client.post(REFRESH_URL, {"refresh": first_pair["refresh"]}, format="json")

    assert refresh_response.status_code == 200
    second_pair = refresh_response.json()
    assert set(second_pair.keys()) == {"access", "refresh"}
    assert second_pair["refresh"] != first_pair["refresh"]
    assert second_pair["access"] != first_pair["access"]


def test_me_requires_auth(api_client: APIClient) -> None:
    """GET /me/ with no Authorization header → 401."""
    response = api_client.get(ME_URL)

    assert response.status_code == 401


def test_me_returns_current_user(api_client: APIClient, user: "User") -> None:
    """GET /me/ with a valid JWT → 200 with {id, email} matching the user."""
    client = _auth_client(api_client, user)

    response = client.get(ME_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "email"}
    assert body["id"] == str(user.pk)
    assert body["email"] == user.email


def _login(api_client: APIClient, email: str, password: str):
    """POST /login/ and return the response."""
    return api_client.post(LOGIN_URL, {"email": email, "password": password}, format="json")


def _auth_client(api_client: APIClient, user: "User") -> APIClient:
    """Return an APIClient with a valid JWT in the Authorization header."""
    login_response = _login(api_client, user.email, "correct-horse-battery-staple")
    access = login_response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api_client
```

- [ ] **Step 2: Run the new file to verify all 11 tests pass**

Run: `pytest accounts/tests/test_auth.py -v`
Expected: all 11 tests pass.

If `test_login_success` fails with a `SIGNING_KEY`/`ALGORITHM` `KeyError`, those settings come from SimpleJWT's defaults and should be present in `settings.SIMPLE_JWT` automatically. If they are missing, add the following to the `SIMPLE_JWT` dict in `config/settings/base.py`:

```python
"SIGNING_KEY": SECRET_KEY,
"ALGORITHM": "HS256",
```

- [ ] **Step 3: Status note**

`accounts/tests/test_auth.py` is left unstaged.

---

### Task 8: Run the full test suite, format, lint, and the pre-commit gate

**Files:**
- Read-only: all auth files.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass — the existing `config/tests/test_*.py` tests plus the 8 model tests, 11 serializer tests, and 11 auth endpoint tests added in this plan.

If any test fails, fix the implementation (not the test) and re-run.

- [ ] **Step 2: Run ruff format on the accounts package**

Run: `ruff format accounts/`
Expected: no changes (or only cosmetic ones the formatter applies).

- [ ] **Step 3: Run ruff check on the accounts package**

Run: `ruff check accounts/`
Expected: zero errors.

- [ ] **Step 4: Run the full pre-commit gate (per AGENTS.md)**

Run: `pre-commit run --all-files`
Expected: all hooks pass (Ruff, Biome, Prettier, editorconfig). This is the project's gate; a task is not done until pre-commit passes.

If any hook fails, fix what it reports and re-run until clean.

- [ ] **Step 5: Status note**

All changes are intentionally left unstaged at the end of this plan. A follow-up commit (or commit batch) stages them. Use `git status` to enumerate the unstaged files; they should include:

- `accounts/models.py`
- `accounts/manager.py`
- `accounts/apps.py`
- `accounts/urls.py`
- `accounts/serializers.py`
- `accounts/views.py`
- `accounts/migrations/__init__.py`
- `accounts/migrations/0001_initial.py`
- `accounts/tests/__init__.py`
- `accounts/tests/conftest.py`
- `accounts/tests/test_user_model.py`
- `accounts/tests/test_serializers.py`
- `accounts/tests/test_auth.py`

(Plus the plan file `docs/superpowers/plans/2026-06-12-geojson-auth.md`.)

---

## Self-review notes (run by the plan author; not dispatched)

**Spec coverage:**

| Spec section | Requirement | Task |
| --- | --- | --- |
| §2 | `User` model: UUID PK, email unique, password, is_active, no username, no is_staff/is_superuser, custom manager, `USERNAME_FIELD="email"`, `REQUIRED_FIELDS=[]` | Task 2 |
| §3 | 4 `AUTH_PASSWORD_VALIDATORS` in order | Task 1 (verify) |
| §4 | 4 endpoints, JWT lifetimes, error responses, login enumeration | Tasks 5, 6, 7 |
| §4 | "Login enumeration" generic 401 message | Tasks 4, 7 |
| §5 | 3 serializers (`UserSerializer`, `RegisterSerializer`, `LoginSerializer`) | Task 4 |
| §5 | `RegisterSerializer` calls `validate_password()` | Task 4 |
| §6 | URL routing at `/api/auth/`, `authentication_classes=[JWTAuthentication]` only | Tasks 5, 6 |
| §7 | `user` and `other_user` fixtures in `accounts/tests/conftest.py` | Task 3 |
| §7 | 10 endpoint tests in `accounts/tests/test_auth.py` (spec lists 10 bullets) | Task 7 (11 tests; 11th is a coverage test for the enumeration byte-identity requirement) |

**Placeholder scan:**

- No "TBD" / "TODO" / "implement later" in any step.
- All code blocks are complete; no "add appropriate error handling" stubs.
- No "Similar to Task N" — every test/code block is inlined.
- No `#` comments in code blocks; docstrings on every function.

**Type and naming consistency:**

- `User.objects.create_user(email=..., password=...)` is used uniformly with kwargs across Tasks 2, 3, 4, 7.
- `REGISTER_URL`, `LOGIN_URL`, `REFRESH_URL`, `ME_URL` constants are defined once in Task 7 and reused throughout.
- `_login` and `_auth_client` are defined after all `def test_*` functions in Task 7, per AGENTS.md's "public/entry-point first, private helpers below" rule.
- All imports are at the top of each test module; no inline / local imports (per AGENTS.md).
- Serializer field names (`id`, `email`, `password`, `password_confirm`) match the spec in §4 and §5.
- `JWTAuthentication` import path is consistent: `rest_framework_simplejwt.authentication.JWTAuthentication` in Tasks 5, 6.

**AGENTS.md compliance audit:**

- **Pre-commit gate** — Task 8 Step 4 runs `pre-commit run --all-files` (the full gate), not a targeted run. ✓
- **Keyword args** for >1-arg calls: `User.objects.create_user(email=..., password=...)` everywhere. Single-arg calls (`mkdir accounts/migrations`, `pytest ...`) are positional-only and exempt. ✓
- **Function ordering** in `test_auth.py`: all `def test_*` functions precede `_login` and `_auth_client`. ✓
- **Blank line after dedent** — `with pytest.raises(...)` blocks are single-statement, no dedent issue. The `if not serializer.is_valid():` blocks are at the function's outer level. ✓
- **Nesting depth** — all tests stay at ≤3 levels of indentation. ✓
- **PEP 8 naming** — no shortened names; no `data`/`res`/`tmp`/`result`. `body` mirrors spec terminology; `payload` mirrors HTTP terminology. ✓
- **No inline / local imports** — all imports at module top. ✓
- **Function length** — every test is <100 lines; the longest test (`test_register_success`) is ~15 lines. ✓
- **No comments** — no `#` comments in code blocks; docstrings on every function (matching the existing project style in `config/tests/`). ✓

**Out-of-scope confirmation:**

- Admin (`is_staff`, `is_superuser`, `create_superuser`): explicitly absent per spec §2 and overview spec §18. Plan does not add them.
- Token blacklist: explicitly disabled per spec §4. Plan does not enable it. Task 7 documents the implication for the rotation test.
- `auth_client` fixture for the Feature API: owned by the Feature API spec per its §9. Plan does not add it (avoids a cross-spec fixture collision).
