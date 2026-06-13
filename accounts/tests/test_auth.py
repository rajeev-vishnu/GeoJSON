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


def test_register_success(api_client: APIClient, db: object) -> None:
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


def test_register_password_mismatch(api_client: APIClient, db: object) -> None:
    """Password != password_confirm → 400."""
    payload = {
        "email": "bob@example.com",
        "password": "correct-horse-battery-staple",
        "password_confirm": "different-password",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == 400
    assert "password_confirm" in response.json()


def test_register_password_too_short(api_client: APIClient, db: object) -> None:
    """7-char password → 400 (validators run from validate(), errors surface as non_field_errors)."""
    payload = {
        "email": "carol@example.com",
        "password": "abcdefg",
        "password_confirm": "abcdefg",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == 400
    body = response.json()
    non_field = body.get("non_field_errors", [])
    assert any("too short" in str(error).lower() for error in non_field)


def test_register_duplicate_email(api_client: APIClient, db: object) -> None:
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


def test_login_success(api_client: APIClient, user: User) -> None:
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


def test_login_wrong_password(api_client: APIClient, user: User) -> None:
    """Wrong password → 401 with the generic message (no enumeration leak)."""
    response = _login(api_client, "alice@example.com", "wrong-password")

    assert response.status_code == 401
    assert response.json() == {"detail": "No active account found with the given credentials"}


def test_login_unknown_email(api_client: APIClient, db: object) -> None:
    """Unknown email → 401 with the same generic message as wrong_password."""
    response = _login(api_client, "nobody@example.com", "irrelevant")

    assert response.status_code == 401
    assert response.json() == {"detail": "No active account found with the given credentials"}


def test_login_messages_match_for_wrong_password_and_unknown_email(api_client: APIClient, user: User) -> None:
    """The two failure responses are byte-identical (no enumeration via body)."""
    wrong = _login(api_client, "alice@example.com", "wrong-password")
    unknown = _login(api_client, "nobody@example.com", "irrelevant")

    assert wrong.json() == unknown.json()


def test_refresh_rotates_tokens(api_client: APIClient, user: User) -> None:
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


def test_me_returns_current_user(api_client: APIClient, user: User) -> None:
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


def _auth_client(api_client: APIClient, user: User) -> APIClient:
    """Return an APIClient with a valid JWT in the Authorization header."""
    login_response = _login(api_client, user.email, "correct-horse-battery-staple")
    access = login_response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api_client
