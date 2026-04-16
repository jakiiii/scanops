from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.ops.forms import (
    AdminProfileFilterForm,
    AllowedTargetsSettingsForm,
    ExportSettingsForm,
    GeneralSettingsForm,
    NotificationSettingsForm,
    RoleForm,
    RolePermissionToggleForm,
    ScanPolicySettingsForm,
    ThemeSettingsForm,
    UserAdminForm,
    UserFilterForm,
)
from apps.ops.models import AppSetting, PermissionRule, Role
from apps.ops.rbac import CapabilityRequiredMixin
from apps.ops.services import app_settings_service, permission_service, profile_governance_service, user_management_service
from apps.ops.services.admin_audit_service import log_admin_action
from apps.ops.services.system_health_service import overall_status, recent_alerts, recent_timeline, run_health_checks
from apps.ops.services.worker_status_service import collect_worker_dashboard_context
from apps.scans.models import ScanProfile

User = get_user_model()


def _redirect_back(request: HttpRequest, fallback_url: str) -> HttpResponse:
    return redirect(request.META.get("HTTP_REFERER") or fallback_url)


def settings_tabs(active_slug: str) -> list[dict]:
    return [
        {"slug": "general", "label": "General", "url": reverse("ops:settings-general"), "icon": "tune"},
        {"slug": "scan_policy", "label": "Scan Policy", "url": reverse("ops:settings-scan-policy"), "icon": "gavel"},
        {"slug": "allowed_targets", "label": "Allowed Targets", "url": reverse("ops:settings-allowed-targets"), "icon": "my_location"},
        {"slug": "notifications", "label": "Notifications", "url": reverse("ops:settings-notifications"), "icon": "notifications"},
        {"slug": "exports", "label": "Export", "url": reverse("ops:settings-exports"), "icon": "download"},
        {"slug": "ui", "label": "Theme & UI", "url": reverse("ops:settings-theme"), "icon": "palette"},
    ]


class BaseCategorySettingsView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.MANAGE_SETTINGS
    template_name = "ops/settings/category.html"
    category: str = AppSetting.Category.GENERAL
    category_slug: str = "general"
    form_class = GeneralSettingsForm
    page_title = "General Settings"
    page_description = "Manage application defaults."
    policy_note = "Changes apply globally and are captured in admin audit logs."
    wide_fields: tuple[str, ...] = ()

    def get_initial(self) -> dict:
        values = app_settings_service.get_category_values(self.category)
        if "whitelist_ranges" in values:
            values["whitelist_ranges"] = "\n".join(values["whitelist_ranges"])
        if "blocked_ranges" in values:
            values["blocked_ranges"] = "\n".join(values["blocked_ranges"])
        return values

    def get_form(self, data=None):
        return self.form_class(data=data, initial=None if data is not None else self.get_initial())

    def _normalized_payload(self, form):
        payload = dict(form.cleaned_data)
        if "whitelist_ranges" in payload:
            payload["whitelist_ranges"] = [line.strip() for line in payload["whitelist_ranges"].splitlines() if line.strip()]
        if "blocked_ranges" in payload:
            payload["blocked_ranges"] = [line.strip() for line in payload["blocked_ranges"].splitlines() if line.strip()]
        return payload

    def _render(self, request, form, *, saved=False, reset=False):
        context = self.get_context_data(form=form, saved=saved, reset=reset)
        if request.headers.get("HX-Request"):
            return render(request, "partials/settings_form_block.html", context)
        return render(request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        return self._render(request, form)

    def post(self, request, *args, **kwargs):
        if request.POST.get("reset_defaults") == "1":
            app_settings_service.reset_category_to_defaults(self.category, user=request.user)
            log_admin_action(
                actor=request.user,
                action=f"settings.reset.{self.category}",
                summary=f"Reset {self.category} settings to defaults.",
                metadata={"category": self.category},
                request=request,
            )
            messages.info(request, f"{self.page_title} reset to defaults.")
            form = self.get_form()
            return self._render(request, form, reset=True)

        form = self.get_form(data=request.POST)
        if not form.is_valid():
            return self._render(request, form)

        payload = self._normalized_payload(form)
        app_settings_service.update_category_values(self.category, payload, user=request.user)
        log_admin_action(
            actor=request.user,
            action=f"settings.update.{self.category}",
            summary=f"Updated {self.category} settings.",
            metadata={"category": self.category, "keys": sorted(payload.keys())},
            request=request,
        )
        messages.success(request, f"{self.page_title} updated.")
        form = self.get_form()
        return self._render(request, form, saved=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form": kwargs["form"],
                "saved": kwargs.get("saved", False),
                "reset": kwargs.get("reset", False),
                "page_title": self.page_title,
                "page_description": self.page_description,
                "policy_note": self.policy_note,
                "settings_tabs": settings_tabs(self.category_slug),
                "active_tab": self.category_slug,
                "wide_fields": self.wide_fields,
                "breadcrumbs": [
                    {"label": "Settings", "url": reverse("ops:settings-general")},
                    {"label": self.page_title, "url": ""},
                ],
            }
        )
        return context


class GeneralSettingsView(BaseCategorySettingsView):
    category = "general"
    category_slug = "general"
    form_class = GeneralSettingsForm
    page_title = "General Settings"
    page_description = "Configure branding, language, timezone, and retention defaults."


class ScanPolicySettingsView(BaseCategorySettingsView):
    category = "scan_policy"
    category_slug = "scan_policy"
    form_class = ScanPolicySettingsForm
    page_title = "Scan Policy Settings"
    page_description = "Control allowed scan modes, limits, and approval guardrails."
    wide_fields = ("allowed_scan_types", "blocked_scan_types")


class AllowedTargetsSettingsView(BaseCategorySettingsView):
    category = "allowed_targets"
    category_slug = "allowed_targets"
    form_class = AllowedTargetsSettingsForm
    page_title = "Allowed Targets Settings"
    page_description = "Enforce whitelist/blocked network policy and target validation."
    wide_fields = ("whitelist_ranges", "blocked_ranges")


class NotificationSettingsView(BaseCategorySettingsView):
    category = "notifications"
    category_slug = "notifications"
    form_class = NotificationSettingsForm
    page_title = "Notification Settings"
    page_description = "Configure app/email notification policy and digest behavior."


class ExportSettingsView(BaseCategorySettingsView):
    category = "exports"
    category_slug = "exports"
    form_class = ExportSettingsForm
    page_title = "Export Settings"
    page_description = "Set report format defaults, PDF branding, and export retention."


class ThemeSettingsView(BaseCategorySettingsView):
    category = "ui"
    category_slug = "ui"
    form_class = ThemeSettingsForm
    page_title = "Theme & UI Settings"
    page_description = "Adjust theme behavior, density, and table defaults."


class UserListView(CapabilityRequiredMixin, ListView):
    capability_key = PermissionRule.PermissionKey.MANAGE_USERS
    model = User
    template_name = "ops/users/list.html"
    context_object_name = "users"
    paginate_by = 15

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/user_table.html"]
        return [self.template_name]

    def get_queryset(self):
        permission_service.bootstrap_default_roles()
        queryset = User.objects.select_related("profile__role").order_by("-date_joined")
        self.filter_form = UserFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            if q:
                queryset = queryset.filter(
                    Q(username__icontains=q)
                    | Q(email__icontains=q)
                    | Q(first_name__icontains=q)
                    | Q(last_name__icontains=q)
                    | Q(profile__display_name__icontains=q)
                    | Q(profile__allowed_workspace__icontains=q)
                )
            if cleaned.get("role"):
                queryset = queryset.filter(profile__role=cleaned["role"])
            if cleaned.get("is_active") == "true":
                queryset = queryset.filter(is_active=True)
            elif cleaned.get("is_active") == "false":
                queryset = queryset.filter(is_active=False)

            if cleaned.get("is_approved") == "true":
                queryset = queryset.filter(profile__is_approved=True)
            elif cleaned.get("is_approved") == "false":
                queryset = queryset.filter(Q(profile__isnull=True) | Q(profile__is_approved=False))
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form

        page_users = list(context["page_obj"].object_list)
        activity_map = user_management_service.summarize_user_activity_bulk([user.id for user in page_users])
        for user in page_users:
            try:
                user.profile_cached = user.profile
            except Exception:
                user.profile_cached = user_management_service.ensure_profile(user)
            user.activity_summary = activity_map.get(user.id)
            user.can_manage_account = permission_service.can_manage_user_account(self.request.user, user)

        source = User.objects.select_related("profile__role")
        context["summary"] = {
            "total": source.count(),
            "active": source.filter(is_active=True).count(),
            "approved": source.filter(profile__is_approved=True).count(),
            "admins": source.filter(
                Q(is_superuser=True)
                | Q(profile__role__slug__in=[permission_service.SUPER_ADMIN, permission_service.SECURITY_ADMIN])
            ).count(),
        }
        context["breadcrumbs"] = [
            {"label": "User Management", "url": ""},
        ]
        return context


class UserCreateView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.MANAGE_USERS
    template_name = "ops/users/form.html"

    def get(self, request, *args, **kwargs):
        permission_service.bootstrap_default_roles()
        form = UserAdminForm(actor=request.user)
        return render(request, self.template_name, self.get_context_data(form=form, mode="create"))

    def post(self, request, *args, **kwargs):
        permission_service.bootstrap_default_roles()
        form = UserAdminForm(request.POST, actor=request.user)
        if not form.is_valid():
            return render(request, self.template_name, self.get_context_data(form=form, mode="create"))
        try:
            user = user_management_service.create_user(form.cleaned_data, actor=request.user)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, self.get_context_data(form=form, mode="create"))
        log_admin_action(
            actor=request.user,
            action="user.create",
            target=user,
            summary=f"Created user {user.username}.",
            metadata={"username": user.username, "email": user.email},
            request=request,
        )
        messages.success(request, f"User '{user.username}' created.")
        return redirect("ops:users-edit", pk=user.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mode = kwargs.get("mode", "create")
        context.update(
            {
                "form": kwargs["form"],
                "mode": mode,
                "user_obj": None,
                "breadcrumbs": [
                    {"label": "User Management", "url": reverse("ops:users-list")},
                    {"label": "Create User", "url": ""},
                ],
            }
        )
        return context


class UserUpdateView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.MANAGE_USERS
    template_name = "ops/users/form.html"

    def get_user(self):
        user_obj = get_object_or_404(User.objects.select_related("profile__role"), pk=self.kwargs["pk"])
        if not permission_service.can_manage_user_account(self.request.user, user_obj):
            raise PermissionDenied("You do not have permission to manage this user.")
        return user_obj

    def get(self, request, *args, **kwargs):
        permission_service.bootstrap_default_roles()
        user_obj = self.get_user()
        form = UserAdminForm(user_instance=user_obj, actor=request.user)
        return render(request, self.template_name, self.get_context_data(form=form, mode="edit", user_obj=user_obj))

    def post(self, request, *args, **kwargs):
        permission_service.bootstrap_default_roles()
        user_obj = self.get_user()
        form = UserAdminForm(request.POST, user_instance=user_obj, actor=request.user)
        if not form.is_valid():
            return render(request, self.template_name, self.get_context_data(form=form, mode="edit", user_obj=user_obj))
        try:
            user_management_service.update_user(user_obj, form.cleaned_data, actor=request.user)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, self.get_context_data(form=form, mode="edit", user_obj=user_obj))
        log_admin_action(
            actor=request.user,
            action="user.update",
            target=user_obj,
            summary=f"Updated user {user_obj.username}.",
            metadata={"username": user_obj.username},
            request=request,
        )
        messages.success(request, f"User '{user_obj.username}' updated.")
        return redirect("ops:users-edit", pk=user_obj.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = kwargs["user_obj"]
        context.update(
            {
                "form": kwargs["form"],
                "mode": kwargs.get("mode", "edit"),
                "user_obj": user_obj,
                "breadcrumbs": [
                    {"label": "User Management", "url": reverse("ops:users-list")},
                    {"label": user_obj.username, "url": ""},
                ],
            }
        )
        return context


class UserToggleActiveView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_USERS

    def post(self, request, pk: int):
        user = get_object_or_404(User.objects.select_related("profile__role"), pk=pk)
        if not permission_service.can_manage_user_account(request.user, user):
            raise PermissionDenied("You do not have permission to manage this user.")
        user_management_service.set_user_active(user, is_active=not user.is_active, actor=request.user)
        log_admin_action(
            actor=request.user,
            action="user.toggle_active",
            target=user,
            summary=f"Set user {user.username} active={user.is_active}.",
            metadata={"is_active": user.is_active},
            request=request,
        )
        messages.info(request, f"{user.username} is now {'active' if user.is_active else 'inactive'}.")
        return _redirect_back(request, reverse("ops:users-list"))


class UserFlagPasswordResetView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_USERS

    def post(self, request, pk: int):
        user = get_object_or_404(User.objects.select_related("profile__role"), pk=pk)
        if not permission_service.can_manage_user_account(request.user, user):
            raise PermissionDenied("You do not have permission to manage this user.")
        user_management_service.mark_password_reset_required(user, required=True, actor=request.user)
        log_admin_action(
            actor=request.user,
            action="user.flag_password_reset",
            target=user,
            summary=f"Flagged user {user.username} for password reset.",
            metadata={"force_password_reset": True},
            request=request,
        )
        messages.warning(request, f"{user.username} flagged for password reset.")
        return _redirect_back(request, reverse("ops:users-list"))


class RolePermissionView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.MANAGE_ROLES
    template_name = "ops/users/roles.html"

    def _get_edit_role(self):
        role_id = self.request.GET.get("edit")
        if role_id and role_id.isdigit():
            return Role.objects.filter(pk=int(role_id)).first()
        return None

    def get(self, request, *args, **kwargs):
        permission_service.bootstrap_default_roles()
        editing_role = self._get_edit_role()
        role_form = RoleForm(instance=editing_role) if editing_role else RoleForm()
        return render(request, self.template_name, self.get_context_data(role_form=role_form, editing_role=editing_role))

    def post(self, request, *args, **kwargs):
        role_id = request.POST.get("role_id")
        instance = Role.objects.filter(pk=int(role_id)).first() if role_id and role_id.isdigit() else None
        role_form = RoleForm(request.POST, instance=instance)
        if role_form.is_valid():
            role = role_form.save()
            permission_service.seed_role_permission_rules(role)
            log_admin_action(
                actor=request.user,
                action="role.update" if instance else "role.create",
                target=role,
                summary=f"{'Updated' if instance else 'Created'} role {role.slug}.",
                metadata={"slug": role.slug},
                request=request,
            )
            messages.success(request, f"Role '{role.name}' {'updated' if instance else 'created'}.")
            return redirect("ops:roles")
        return render(request, self.template_name, self.get_context_data(role_form=role_form, editing_role=instance))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        roles = list(Role.objects.prefetch_related("permission_rules").order_by("is_system", "name"))
        matrix_rows = permission_service.build_permission_matrix(roles)
        context.update(
            {
                "roles": roles,
                "matrix_rows": matrix_rows,
                "role_form": kwargs["role_form"],
                "editing_role": kwargs.get("editing_role"),
                "breadcrumbs": [
                    {"label": "User Management", "url": reverse("ops:users-list")},
                    {"label": "Roles & Permissions", "url": ""},
                ],
            }
        )
        return context


class RoleMatrixPartialView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_ROLES

    def get(self, request):
        roles = list(Role.objects.prefetch_related("permission_rules").order_by("is_system", "name"))
        matrix_rows = permission_service.build_permission_matrix(roles)
        return render(request, "partials/role_matrix.html", {"roles": roles, "matrix_rows": matrix_rows})


class RolePermissionToggleView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_ROLES

    def post(self, request):
        form = RolePermissionToggleForm(request.POST)
        if form.is_valid():
            role = Role.objects.get(pk=form.cleaned_data["role_id"])
            is_allowed = bool(form.cleaned_data.get("is_allowed"))
            rule, _ = PermissionRule.objects.get_or_create(
                role=role,
                permission_key=form.cleaned_data["permission_key"],
                defaults={"is_allowed": is_allowed},
            )
            if rule.is_allowed != is_allowed:
                rule.is_allowed = is_allowed
                rule.save(update_fields=["is_allowed", "updated_at"])
            log_admin_action(
                actor=request.user,
                action="role.permission.toggle",
                target=role,
                summary=f"Updated role permission {role.slug}:{rule.permission_key}={is_allowed}.",
                metadata={"permission_key": rule.permission_key, "is_allowed": is_allowed},
                request=request,
            )
        roles = list(Role.objects.prefetch_related("permission_rules").order_by("is_system", "name"))
        matrix_rows = permission_service.build_permission_matrix(roles)
        return render(request, "partials/role_matrix.html", {"roles": roles, "matrix_rows": matrix_rows})


class AdminScanProfileManagementView(CapabilityRequiredMixin, ListView):
    capability_key = PermissionRule.PermissionKey.MANAGE_PROFILES
    model = ScanProfile
    template_name = "ops/users/admin_profiles.html"
    context_object_name = "profiles"
    paginate_by = 15

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/admin_profiles_table.html"]
        return [self.template_name]

    def get_queryset(self):
        self.filter_form = AdminProfileFilterForm(self.request.GET or None)
        q = ""
        profile_type = ""
        active = ""
        owner_id = None
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            profile_type = cleaned.get("profile_type") or ""
            active = cleaned.get("active") or ""
            owner = cleaned.get("owner")
            owner_id = owner.id if owner else None
        return profile_governance_service.list_admin_profiles(
            q=q,
            profile_type=profile_type,
            active=active,
            owner_id=owner_id,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        source = profile_governance_service.list_admin_profiles()
        context["summary"] = profile_governance_service.summarize_profiles(source)
        context["breadcrumbs"] = [
            {"label": "User Management", "url": reverse("ops:users-list")},
            {"label": "Admin Scan Profiles", "url": ""},
        ]
        return context


class AdminProfilePublishView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_PROFILES

    def post(self, request, pk: int):
        profile = get_object_or_404(ScanProfile, pk=pk)
        profile_governance_service.publish_profile(profile)
        log_admin_action(
            actor=request.user,
            action="scan_profile.publish",
            target=profile,
            summary=f"Published scan profile '{profile.name}'.",
            metadata={"is_active": True},
            request=request,
        )
        messages.success(request, f"Published profile '{profile.name}'.")
        return _redirect_back(request, reverse("ops:admin-profiles"))


class AdminProfileDisableView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_PROFILES

    def post(self, request, pk: int):
        profile = get_object_or_404(ScanProfile, pk=pk)
        profile_governance_service.disable_profile(profile)
        log_admin_action(
            actor=request.user,
            action="scan_profile.disable",
            target=profile,
            summary=f"Disabled scan profile '{profile.name}'.",
            metadata={"is_active": False},
            request=request,
        )
        messages.warning(request, f"Disabled profile '{profile.name}'.")
        return _redirect_back(request, reverse("ops:admin-profiles"))


class AdminProfileDeleteView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_PROFILES

    def post(self, request, pk: int):
        profile = get_object_or_404(ScanProfile, pk=pk)
        profile_name = profile.name
        try:
            profile_governance_service.delete_profile(profile)
        except ValueError as exc:
            messages.error(request, str(exc))
            return _redirect_back(request, reverse("ops:admin-profiles"))

        log_admin_action(
            actor=request.user,
            action="scan_profile.delete",
            summary=f"Deleted scan profile '{profile_name}'.",
            metadata={"profile_name": profile_name},
            request=request,
        )
        messages.error(request, f"Deleted profile '{profile_name}'.")
        return _redirect_back(request, reverse("ops:admin-profiles"))


class QueueWorkerStatusView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH
    template_name = "ops/health/queue_workers.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if request.headers.get("HX-Request"):
            return render(request, "partials/worker_status_cards.html", context)
        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker_context = collect_worker_dashboard_context(persist=True)
        context.update(worker_context)
        context["breadcrumbs"] = [
            {"label": "System Health", "url": reverse("ops:health-system")},
            {"label": "Queue & Worker Status", "url": ""},
        ]
        return context


class SystemHealthView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH
    template_name = "ops/health/system.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = run_health_checks(persist=True)
        context.update(
            {
                "services": services,
                "overall_status": overall_status(services),
                "checked_at": services[0]["checked_at"] if services else None,
                "alerts": recent_alerts(8),
                "timeline": recent_timeline(20),
                "breadcrumbs": [
                    {"label": "System Health", "url": ""},
                ],
            }
        )
        return context


class SystemHealthCardsPartialView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH

    def get(self, request):
        services = run_health_checks(persist=True)
        context = {
            "services": services,
            "overall_status": overall_status(services),
            "checked_at": services[0]["checked_at"] if services else None,
        }
        return render(request, "partials/system_health_cards.html", context)


class SystemHealthAlertsPartialView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH

    def get(self, request):
        return render(request, "partials/system_health_alerts.html", {"alerts": recent_alerts(8)})
