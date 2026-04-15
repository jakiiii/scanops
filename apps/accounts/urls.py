from django.urls import path

from apps.accounts.views import (
    AccessDeniedView,
    HomeRedirectView,
    OperatorLoginView,
    OperatorLogoutView,
)

app_name = "accounts"


urlpatterns = [
    path("", HomeRedirectView.as_view(), name="root"),
    path("login/", OperatorLoginView.as_view(), name="login"),
    path("logout/", OperatorLogoutView.as_view(), name="logout"),
    path("access-denied/", AccessDeniedView.as_view(), name="permission_denied"),
]
