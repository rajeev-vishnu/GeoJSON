"""Auth API views.

`RegisterView`, `LoginView`, and `MeView` are project-owned. The
`TokenRefreshView` alias lives in `accounts/urls.py` so the four
endpoints share the same JWTAuthentication-only configuration (auth
spec §6). `LoginView` re-asserts that config on the SimpleJWT view.
"""

from __future__ import annotations

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — public; creates a user.

    The response is `{id, email}` (UserSerializer shape). The
    RegisterSerializer is used only for input validation; the freshly
    created user is re-serialized with UserSerializer to produce the
    spec-required output.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Validate input, create the user, and return `{id, email}`."""
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        user = input_serializer.save()
        output_serializer = UserSerializer(user)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


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
