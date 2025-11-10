from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from django.urls import path

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "change-password/", views.ChangePasswordView.as_view(), name="change_password"
    ),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
