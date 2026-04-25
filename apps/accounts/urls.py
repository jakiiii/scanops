from django.urls import path
from django.views.generic import RedirectView

from apps.accounts.views import (
    AccessDeniedView,
    AccountPasswordChangeDoneView,
    AccountPasswordChangeView,
    AccountPasswordResetCompleteView,
    AccountPasswordResetConfirmView,
    AccountPasswordResetDoneView,
    AccountPasswordResetView,
    HomeRedirectView,
    OperatorLoginView,
    OperatorLogoutView,
    RegistrationSuccessView,
    RegistrationView,
)

app_name = "accounts"


urlpatterns = [
    path("", HomeRedirectView.as_view(), name="root"),
    path("login/", OperatorLoginView.as_view(), name="login"),
    path("logout/", OperatorLogoutView.as_view(), name="logout"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("register/success/", RegistrationSuccessView.as_view(), name="register_success"),
    path("password-reset/", AccountPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", AccountPasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", AccountPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", AccountPasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("password-change/", AccountPasswordChangeView.as_view(), name="password_change"),
    path("password-change/done/", AccountPasswordChangeDoneView.as_view(), name="password_change_done"),
    path(
        "password-changed/",
        RedirectView.as_view(pattern_name="accounts:password_change", permanent=False),
        name="password_changed",
    ),
    # Prefixed compatibility aliases
    path("accounts/register/", RedirectView.as_view(pattern_name="accounts:register", permanent=False)),
    path(
        "accounts/register/success/",
        RedirectView.as_view(pattern_name="accounts:register_success", permanent=False),
    ),
    path(
        "accounts/password-reset/",
        RedirectView.as_view(pattern_name="accounts:password_reset", permanent=False),
    ),
    path(
        "accounts/password-reset/done/",
        RedirectView.as_view(pattern_name="accounts:password_reset_done", permanent=False),
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        RedirectView.as_view(pattern_name="accounts:password_reset_confirm", permanent=False),
    ),
    path(
        "accounts/reset/done/",
        RedirectView.as_view(pattern_name="accounts:password_reset_complete", permanent=False),
    ),
    path(
        "accounts/password-change/",
        RedirectView.as_view(pattern_name="accounts:password_change", permanent=False),
    ),
    path(
        "accounts/password-change/done/",
        RedirectView.as_view(pattern_name="accounts:password_change_done", permanent=False),
    ),
    path("access-denied/", AccessDeniedView.as_view(), name="permission_denied"),
]
