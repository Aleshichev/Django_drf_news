from django.shortcuts import render
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login

from .models import User
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserUpdateSerializer,
    UserProfileSerializer,
    PasswordChangeSerializer,
)
from drf_spectacular.utils import extend_schema


@extend_schema(
    tags=["Authentication"],
    summary="Register a new user",
    description="Create a new user account and return JWT access and refresh tokens upon successful registration.",
)
class RegisterView(generics.CreateAPIView):
    """Register a new user and return JWT tokens upon successful registration."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "message": "User regirstered successfully",
            },
            status=status.HTTP_201_CREATED,
        )

@extend_schema(
    tags=["Authentication"],
    summary="User login",
    description="Authenticate a user with email/username and password, returning JWT access and refresh tokens upon successful login."
)
class LoginView(generics.GenericAPIView):
    """User login"""

    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        login(request, user)
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "message": "User login successfully",
            },
            status=status.HTTP_200_OK,
        )

@extend_schema(
    tags=["Authentication"],
    summary="Retrieve and update user profile",
    description="Get the authenticated user's profile information or update their profile details."
)
class ProfileView(generics.RetrieveUpdateAPIView):
    """View and update user profile"""

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PUT" or self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserProfileSerializer

@extend_schema(
    tags=["Authentication"],
    summary="Change user password",
    description="Allow the authenticated user to change their password. Requires providing the old password and a new password."
)
class ChangePasswordView(generics.UpdateAPIView):
    """Password change view"""

    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Password changed successfully"}, status=status.HTTP_200_OK
        )

@extend_schema(
    tags=["Authentication"],
    summary="User logout",
    description="Invalidate the current session or JWT token for the authenticated user."
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """Logout"""
    try:
        refresh_token = request.data.get("refresh_token")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
    except Exception:
        return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
