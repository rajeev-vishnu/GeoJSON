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
