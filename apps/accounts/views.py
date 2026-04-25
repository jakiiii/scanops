from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, RedirectView, TemplateView

from apps.accounts.audit import create_user_log
from apps.accounts.forms.auth import (
    OperatorLoginForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
    UserRegistrationForm,
)
from apps.accounts.models import UserLogs
from apps.ops.models import Role, UserProfile
from apps.ops.services import permission_service


User = get_user_model()


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = [chunk for chunk in (full_name or "").strip().split(" ") if chunk]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _registration_enabled() -> bool:
    return bool(getattr(settings, "SCANOPS_SELF_REGISTRATION_ENABLED", True))


def _registration_requires_approval() -> bool:
    return bool(getattr(settings, "SCANOPS_SELF_REGISTRATION_REQUIRES_APPROVAL", False))


def _get_registration_role() -> Role | None:
    permission_service.bootstrap_default_roles()
    requested_slug = (getattr(settings, "SCANOPS_SELF_REGISTRATION_DEFAULT_ROLE", "") or "").strip()
    fallback_slug = permission_service.VIEWER
    role = Role.objects.filter(slug=requested_slug).first() if requested_slug else None
    if role is None:
        role = Role.objects.filter(slug=fallback_slug).first()
    return role


def _sync_role_group_membership(user, role: Role | None):
    if role is None:
        return
    managed_role_names = list(Role.objects.values_list("name", flat=True))
    if managed_role_names:
        groups_to_remove = list(user.groups.filter(name__in=managed_role_names))
        if groups_to_remove:
            user.groups.remove(*groups_to_remove)
    role_group = Group.objects.filter(name=role.name).first()
    if role_group is not None:
        user.groups.add(role_group)


def _build_profile_notes(*, form: UserRegistrationForm) -> str:
    lines: list[str] = []
    job_title = (form.cleaned_data.get("job_title") or "").strip()
    phone_number = (form.cleaned_data.get("phone_number") or "").strip()
    free_notes = (form.cleaned_data.get("profile_notes") or "").strip()
    if job_title:
        lines.append(f"Job Title: {job_title}")
    if phone_number:
        lines.append(f"Phone: {phone_number}")
    if free_notes:
        lines.append(free_notes)
    return "\n".join(lines)


class AnonymousOnlyMixin:
    authenticated_redirect_url = reverse_lazy("dashboard:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.authenticated_redirect_url)
        return super().dispatch(request, *args, **kwargs)


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
        profile = getattr(self.request.user, "profile", None)
        if profile and profile.force_password_reset:
            messages.warning(self.request, "Password update required before accessing ScanOps.")
            return reverse_lazy("accounts:password_change")
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


class RegistrationView(AnonymousOnlyMixin, FormView):
    template_name = "accounts/register.html"
    form_class = UserRegistrationForm
    success_url = reverse_lazy("accounts:register_success")

    def dispatch(self, request, *args, **kwargs):
        if not _registration_enabled():
            raise PermissionDenied("Self registration is disabled.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        full_name = (form.cleaned_data.get("full_name") or "").strip()
        first_name, last_name = _split_full_name(full_name)
        requires_approval = _registration_requires_approval()
        default_role = _get_registration_role()
        organization = (form.cleaned_data.get("organization") or "").strip()

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password1"],
                    first_name=first_name,
                    last_name=last_name,
                    is_active=not requires_approval,
                    is_administrator=False,
                    is_operator=False,
                    is_staff=False,
                    is_superuser=False,
                )

                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.display_name = full_name or user.get_full_name() or user.username
                profile.role = default_role
                profile.is_approved = not requires_approval
                profile.is_internal_operator = True
                profile.allowed_workspace = organization[:120]
                profile.notes = _build_profile_notes(form=form)
                profile.save()

                if default_role is not None:
                    permission_service.assign_role_to_user(user, default_role)
                    _sync_role_group_membership(user, default_role)
        except IntegrityError:
            form.add_error(None, "A user with this username or email already exists.")
            return self.form_invalid(form)

        if requires_approval:
            messages.success(
                self.request,
                "Registration submitted. Your account is pending approval by an administrator.",
            )
        else:
            messages.success(self.request, "Registration successful. You can now sign in.")
        return super().form_valid(form)


class RegistrationSuccessView(AnonymousOnlyMixin, TemplateView):
    template_name = "accounts/register_success.html"


class AccountPasswordResetView(AnonymousOnlyMixin, PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    form_class = StyledPasswordResetForm
    email_template_name = "accounts/password_reset_email.txt"
    html_email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class AccountPasswordResetDoneView(AnonymousOnlyMixin, PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class AccountPasswordResetConfirmView(AnonymousOnlyMixin, PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = getattr(form.user, "profile", None)
        if profile and profile.force_password_reset:
            profile.force_password_reset = False
            profile.save(update_fields=["force_password_reset", "updated_at"])
        messages.success(self.request, "Password reset complete. You can now sign in.")
        return response


class AccountPasswordResetCompleteView(AnonymousOnlyMixin, PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class AccountPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = getattr(self.request.user, "profile", None)
        if profile and profile.force_password_reset:
            profile.force_password_reset = False
            profile.save(update_fields=["force_password_reset", "updated_at"])
        messages.success(self.request, "Your password has been updated.")
        return response


class AccountPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"
