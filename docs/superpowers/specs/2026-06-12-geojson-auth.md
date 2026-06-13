# GeoJSON API — Auth Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** [Foundation](./2026-06-12-geojson-foundation.md)
**Required by:** Feature API, Frontend

## 1. Purpose

The `accounts` app: custom `User` model, password validators, four
auth endpoints (register, login, refresh, me), JWT configuration,
serializers, and the auth test suite.

## 2. The `accounts.User` model

Custom user model. Inherits `AbstractBaseUser` only (no
`PermissionsMixin`, no `is_staff` / `is_superuser` — admin is
deferred, see [Overview §18](./2026-06-12-geojson-api-design.md#18-out-of-scope-for-v1)).
`USERNAME_FIELD = "email"`. `REQUIRED_FIELDS = []` (no username).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `UUIDField` (PK, default `uuid4`) | Stable IDs. |
| `email` | `EmailField` (unique) | Login identifier. |
| `password` | `CharField` | Hashed by `set_password()`. |
| `is_active` | `BooleanField` (default True) | Standard. |

No `username`, no `is_staff`, no `is_superuser`, no `last_login`, no
`date_joined`. Django's `BaseUserManager` is subclassed with
`create_user(email, password)`; `create_superuser` is **not**
defined. Users are created via the public register endpoint (see
§4).

## 3. Password validators

`AUTH_PASSWORD_VALIDATORS` in `config/settings/base.py` configures
Django's 4 built-in validators, in this order:

1. `UserAttributeSimilarityValidator` — rejects passwords too
   similar to the user's email.
2. `MinimumLengthValidator(min_length=8)` — minimum length, per
   NIST SP 800-63B. 12+ is recommended but 8 is the hard floor.
3. `CommonPasswordValidator` — rejects Django's bundled top-20k
   list of common passwords.
4. `NumericPasswordValidator` — rejects all-numeric passwords.

Policy decisions, justified by NIST SP 800-63B:

- **No composition rules** (no "must contain uppercase + number +
  symbol"). These rules are counterproductive; they push users to
  `Password1!`.
- **No maximum length** beyond Django's 4096-char input cap.
- **All characters allowed**, including spaces and Unicode.
- **No periodic rotation** (the "rotate every 90 days" rule is
  deprecated).

The same validators run on user creation and on future password
change (v2). `RegisterSerializer` calls `validate_password()` from
`django.contrib.auth.password_validation` (see §5) so the 4
`AUTH_PASSWORD_VALIDATORS` defined here run on register.

## 4. Auth endpoints

Base path: `/api/auth/`. Auth: `Authorization: Bearer <access_token>`
header (not used by register/login/refresh — those are public).

| Method | Path | Auth | Body | Response |
| --- | --- | --- | --- | --- |
| `POST` | `/api/auth/register/` | none | `{email, password, password_confirm}` | `201 {id, email}` |
| `POST` | `/api/auth/login/` | none | `{email, password}` | `200 {access, refresh}` |
| `POST` | `/api/auth/refresh/` | none | `{refresh}` | `200 {access, refresh}` (rotated) |
| `GET` | `/api/auth/me/` | required | — | `200 {id, email}` |

**JWT lifetimes:** access 15 min, refresh 7 days,
`ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=False` in
v1 (no token blacklist). The frontend deletes tokens from
`localStorage` on logout. Standard error responses:

- `401 Unauthorized` for missing or invalid `Authorization` header.
- `401 Unauthorized` for an expired access token.
- `401 Unauthorized` for a refresh token that has been rotated
  already.
- `403 Forbidden` if we ever add permission classes (not used in
  v1).

### Login enumeration

The login endpoint returns the same generic
`401 {"detail": "No active account found with the given credentials"}`
whether the email doesn't exist or the password is wrong. The
`LoginSerializer` does not include the user object in errors, and
the `validate()` method returns the SimpleJWT auth failure
unchanged. This prevents attackers from using the login endpoint
to enumerate which emails are registered.

## 5. Serializers

In `accounts/serializers.py`:

- `UserSerializer` — read-only `{id, email}`.
- `RegisterSerializer` — `{email, password, password_confirm}`.
  Validates `password == password_confirm`, email uniqueness, and
  calls `validate_password()` from
  `django.contrib.auth.password_validation` so the 4
  `AUTH_PASSWORD_VALIDATORS` (defined in §3) run on register.
  On success, creates the user via
  `User.objects.create_user(email, password)`.
- `LoginSerializer` — `{email, password}`. Fields-only validation;
  SimpleJWT does the auth. Returns the same generic failure
  whether the email is unknown or the password is wrong (see
  "Login enumeration" in §4).

## 6. URL routing and authentication classes

`accounts/urls.py` routes the 4 auth endpoints. The `TokenObtainPairView`,
`TokenRefreshView`, `RegisterView`, and `MeView` all set
`authentication_classes = [JWTAuthentication]` only —
`SessionAuthentication` is not used, so the API is unaffected by
CSRF (JWT in the `Authorization` header is not auto-attached by
browsers, so CSRF doesn't apply). The [Feature API
spec](./2026-06-12-geojson-feature-api.md) follows the same
convention for its views.

The frontend templates (login form, register form) use Django's
standard CSRF protection via `{% csrf_token %}` and POST to the
auth endpoints with the token in a form-encoded body — those
requests are protected by Django's CSRF middleware.

## 7. Tests

`accounts/tests/conftest.py`:

- `user` — a regular user (the standard fixture; used by all
  auth tests; also re-used by the [Feature API
  spec](./2026-06-12-geojson-feature-api.md)).
- `other_user` — a second user, for tests that need two
  principals.

### `accounts/tests/test_auth.py` (~6 tests)

- `test_register_success` — POST `{email, password, password_confirm}`
  → 201 with `{id, email}`; user is created in the DB; password is
  hashed.
- `test_register_password_mismatch` — `password != password_confirm`
  → 400.
- `test_register_password_too_short` — 7-char password → 400 from
  `MinimumLengthValidator`.
- `test_register_duplicate_email` — registering twice with the
  same email → 400.
- `test_login_success` — POST credentials → 200 with `{access,
  refresh}`; access token is a valid JWT.
- `test_login_wrong_password` — wrong password → 401 with the
  generic message (no enumeration leak).
- `test_login_unknown_email` — unknown email → 401 with the same
  generic message as `test_login_wrong_password`.
- `test_refresh_rotates_tokens` — POST `/refresh/` → 200 with
  new `{access, refresh}`; old refresh is no longer valid.
- `test_me_requires_auth` — GET `/me/` without `Authorization` →
  401.
- `test_me_returns_current_user` — GET `/me/` with a valid JWT →
  200 with `{id, email}` matching the authenticated user.
