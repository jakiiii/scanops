from __future__ import annotations

import ipaddress

from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import UserLogs
from apps.notifications.models import Notification
from apps.ops.models import PermissionRule, Role
from apps.ops.services import permission_service
from apps.reports.models import GeneratedReport
from apps.scans.models import ScanProfile

User = get_user_model()


def _decorate_fields(form: forms.Form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = "h-4 w-4 rounded border-slate-700 bg-slate-900 text-blue-500"
        else:
            field.widget.attrs["class"] = "scanops-input"


class GeneralSettingsForm(forms.Form):
    app_brand_name = forms.CharField(max_length=120)
    default_landing_page = forms.ChoiceField(
        choices=(
            ("dashboard", "Dashboard"),
            ("targets", "Targets"),
            ("new_scan", "New Scan"),
            ("running", "Running"),
            ("results", "Results"),
            ("reports", "Reports"),
        )
    )
    time_zone = forms.CharField(max_length=64)
    language = forms.ChoiceField(choices=(("en-us", "English (US)"), ("en-gb", "English (UK)")))
    scan_retention_days = forms.IntegerField(min_value=1, max_value=3650)
    audit_retention_days = forms.IntegerField(min_value=1, max_value=3650)
    compact_sidebar = forms.BooleanField(required=False)
    show_help_tips = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)


class ScanPolicySettingsForm(forms.Form):
    SCAN_TYPE_CHOICES = (
        ("host_discovery", "Host Discovery"),
        ("quick_tcp", "Quick TCP"),
        ("top_100", "Top 100"),
        ("top_1000", "Top 1000"),
        ("service_detection", "Service Detection"),
        ("safe_basic", "Safe Basic"),
    )

    allowed_scan_types = forms.MultipleChoiceField(
        required=False,
        choices=SCAN_TYPE_CHOICES,
        widget=forms.SelectMultiple,
    )
    blocked_scan_types = forms.MultipleChoiceField(
        required=False,
        choices=SCAN_TYPE_CHOICES,
        widget=forms.SelectMultiple,
    )
    max_ports_per_scan = forms.IntegerField(min_value=1, max_value=65535)
    scan_timeout_seconds = forms.IntegerField(min_value=30, max_value=86400)
    max_concurrency = forms.IntegerField(min_value=1, max_value=500)
    safe_default_options = forms.BooleanField(required=False)
    aggressive_requires_approval = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)

    def clean(self):
        cleaned = super().clean()
        allowed = set(cleaned.get("allowed_scan_types") or [])
        blocked = set(cleaned.get("blocked_scan_types") or [])
        overlap = sorted(allowed.intersection(blocked))
        if overlap:
            self.add_error("blocked_scan_types", f"Cannot block and allow the same scan type(s): {', '.join(overlap)}")
        return cleaned


class AllowedTargetsSettingsForm(forms.Form):
    whitelist_ranges = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))
    blocked_ranges = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))
    restrict_public_targets = forms.BooleanField(required=False)
    strict_target_validation = forms.BooleanField(required=False)
    approval_required_new_targets = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)

    @staticmethod
    def _parse_ranges(raw: str) -> list[str]:
        ranges: list[str] = []
        for line in (raw or "").splitlines():
            item = line.strip()
            if not item:
                continue
            ranges.append(item)
        return ranges

    def clean_whitelist_ranges(self):
        values = self._parse_ranges(self.cleaned_data.get("whitelist_ranges", ""))
        for item in values:
            try:
                ipaddress.ip_network(item, strict=False)
            except ValueError:
                raise forms.ValidationError(f"Invalid whitelist CIDR range: {item}")
        return "\n".join(values)

    def clean_blocked_ranges(self):
        values = self._parse_ranges(self.cleaned_data.get("blocked_ranges", ""))
        for item in values:
            try:
                ipaddress.ip_network(item, strict=False)
            except ValueError:
                raise forms.ValidationError(f"Invalid blocked CIDR range: {item}")
        return "\n".join(values)


class NotificationSettingsForm(forms.Form):
    in_app_enabled = forms.BooleanField(required=False)
    email_enabled = forms.BooleanField(required=False)
    severity_preferences = forms.MultipleChoiceField(
        required=False,
        choices=Notification.Severity.choices,
        widget=forms.SelectMultiple,
    )
    daily_digest_enabled = forms.BooleanField(required=False)
    digest_hour_utc = forms.IntegerField(min_value=0, max_value=23)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)


class ExportSettingsForm(forms.Form):
    default_report_format = forms.ChoiceField(choices=GeneratedReport.Format.choices)
    branded_template = forms.CharField(max_length=140)
    pdf_header_text = forms.CharField(max_length=180, required=False)
    pdf_footer_text = forms.CharField(max_length=180, required=False)
    export_retention_days = forms.IntegerField(min_value=1, max_value=3650)
    file_naming_pattern = forms.CharField(max_length=180)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)


class ThemeSettingsForm(forms.Form):
    default_theme = forms.ChoiceField(choices=(("dark", "Dark"), ("light", "Light"), ("system", "System")))
    compact_mode = forms.BooleanField(required=False)
    data_density = forms.ChoiceField(choices=(("comfortable", "Comfortable"), ("compact", "Compact")))
    table_page_size = forms.IntegerField(min_value=10, max_value=200)
    dashboard_card_style = forms.ChoiceField(
        choices=(("standard", "Standard"), ("dense", "Dense"), ("minimal", "Minimal"))
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)


class UserLogAnalyticsFilterForm(forms.Form):
    PERIOD_TODAY = "today"
    PERIOD_YESTERDAY = "yesterday"
    PERIOD_THIS_WEEK = "this_week"
    PERIOD_THIS_MONTH = "this_month"
    PERIOD_THIS_YEAR = "this_year"
    PERIOD_CUSTOM = "custom"

    period = forms.ChoiceField(
        required=False,
        initial=PERIOD_THIS_WEEK,
        choices=(
            (PERIOD_TODAY, "Today"),
            (PERIOD_YESTERDAY, "Yesterday"),
            (PERIOD_THIS_WEEK, "This Week"),
            (PERIOD_THIS_MONTH, "This Month"),
            (PERIOD_THIS_YEAR, "This Year"),
            (PERIOD_CUSTOM, "Custom"),
        ),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    username = forms.CharField(required=False)
    action_type = forms.ChoiceField(
        required=False,
        choices=(("", "All Actions"), *UserLogs.ActionType.choices),
    )
    result = forms.ChoiceField(
        required=False,
        choices=(("", "All Results"), ("success", "Success"), ("failed", "Failed")),
    )
    ip_contains = forms.CharField(required=False)
    path_contains = forms.CharField(required=False)
    actor_type = forms.ChoiceField(
        required=False,
        choices=(("", "All Users"), ("authenticated", "Authenticated"), ("anonymous", "Anonymous/System")),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)
        self.fields["username"].widget.attrs["placeholder"] = "Username or email..."
        self.fields["ip_contains"].widget.attrs["placeholder"] = "IP contains..."
        self.fields["path_contains"].widget.attrs["placeholder"] = "Path contains..."

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        period = cleaned.get("period")

        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "End date must be on or after start date.")

        if period == self.PERIOD_CUSTOM and not start_date and not end_date:
            self.add_error("start_date", "Provide a start date or end date for custom period.")

        return cleaned


class UserFilterForm(forms.Form):
    q = forms.CharField(required=False)
    role = forms.ModelChoiceField(queryset=Role.objects.none(), required=False, empty_label="All Roles")
    is_active = forms.ChoiceField(
        required=False,
        choices=(("", "All States"), ("true", "Active"), ("false", "Inactive")),
    )
    is_approved = forms.ChoiceField(
        required=False,
        choices=(("", "All Approval"), ("true", "Approved"), ("false", "Pending")),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.order_by("name")
        _decorate_fields(self)
        self.fields["q"].widget.attrs["placeholder"] = "Search name, username, email, workspace..."


class UserAdminForm(forms.Form):
    display_name = forms.CharField(max_length=160)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ModelChoiceField(queryset=Role.objects.none(), required=True)
    is_active = forms.BooleanField(required=False, initial=True)
    is_approved = forms.BooleanField(required=False, initial=True)
    is_internal_operator = forms.BooleanField(required=False, initial=True)
    allowed_workspace = forms.CharField(max_length=120, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    new_password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    force_password_reset = forms.BooleanField(required=False)

    def __init__(self, *args, user_instance=None, actor=None, **kwargs):
        self.user_instance = user_instance
        self.actor = actor
        super().__init__(*args, **kwargs)
        if actor is not None:
            self.fields["role"].queryset = permission_service.get_assignable_roles(actor)
        else:
            self.fields["role"].queryset = Role.objects.order_by("name")
        _decorate_fields(self)
        if self.user_instance and not self.is_bound:
            profile = getattr(self.user_instance, "profile", None)
            initial = {
                "display_name": (getattr(profile, "display_name", "") or self.user_instance.get_full_name() or self.user_instance.username),
                "username": self.user_instance.username,
                "email": self.user_instance.email,
                "role": getattr(profile, "role", None),
                "is_active": self.user_instance.is_active,
                "is_approved": getattr(profile, "is_approved", True),
                "is_internal_operator": getattr(profile, "is_internal_operator", True),
                "allowed_workspace": getattr(profile, "allowed_workspace", ""),
                "notes": getattr(profile, "notes", ""),
                "force_password_reset": getattr(profile, "force_password_reset", False),
            }
            for key, value in initial.items():
                self.fields[key].initial = value

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        queryset = User.objects.filter(username__iexact=username)
        if self.user_instance:
            queryset = queryset.exclude(pk=self.user_instance.pk)
        if queryset.exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        queryset = User.objects.filter(email__iexact=email)
        if self.user_instance:
            queryset = queryset.exclude(pk=self.user_instance.pk)
        if queryset.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if self.actor is not None and not permission_service.can_assign_role(self.actor, role):
            raise forms.ValidationError("You are not allowed to assign this role.")
        return role


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["name", "slug", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate_fields(self)


class AdminProfileFilterForm(forms.Form):
    q = forms.CharField(required=False)
    profile_type = forms.ChoiceField(
        required=False,
        choices=(("", "All Types"), ("system", "System"), ("shared", "Shared")),
    )
    active = forms.ChoiceField(
        required=False,
        choices=(("", "All Status"), ("true", "Active"), ("false", "Inactive")),
    )
    owner = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="All Owners")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("username")
        _decorate_fields(self)
        self.fields["q"].widget.attrs["placeholder"] = "Search profile name, owner, description..."


class RolePermissionToggleForm(forms.Form):
    role_id = forms.IntegerField(min_value=1)
    permission_key = forms.ChoiceField(choices=PermissionRule.PermissionKey.choices)
    is_allowed = forms.BooleanField(required=False)

    def clean_role_id(self):
        role_id = self.cleaned_data["role_id"]
        if not Role.objects.filter(pk=role_id).exists():
            raise forms.ValidationError("Invalid role.")
        return role_id
