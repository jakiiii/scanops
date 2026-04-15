from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import RedirectView, TemplateView

from apps.accounts.audit import create_user_log
from apps.accounts.forms import OperatorLoginForm
from apps.accounts.models import UserLogs


class HomeRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse_lazy("dashboard:home")
        return reverse_lazy("accounts:login")


class OperatorLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = OperatorLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("dashboard:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        create_user_log(
            action_type=UserLogs.ActionType.LOGIN,
            description="User logged in successfully.",
            request=self.request,
            user=self.request.user,
            is_success=True,
        )
        messages.success(self.request, "Authentication successful.")
        return response

    def form_invalid(self, form):
        username = form.data.get("username", "")
        create_user_log(
            action_type=UserLogs.ActionType.LOGIN_FAILED,
            description=f"Failed login attempt for '{username}'.",
            request=self.request,
            user=None,
            username_snapshot=username,
            is_success=False,
        )
        messages.error(self.request, "Invalid credentials. Please try again.")
        return super().form_invalid(form)


class OperatorLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")
    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            create_user_log(
                action_type=UserLogs.ActionType.LOGOUT,
                description="User logged out.",
                request=request,
                user=request.user,
                is_success=True,
            )
        messages.info(request, "You have been logged out.")
        return super().dispatch(request, *args, **kwargs)


class AccessDeniedView(TemplateView):
    template_name = "accounts/access_denied.html"
