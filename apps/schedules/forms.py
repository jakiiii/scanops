from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from apps.ops.rbac import scope_queryset_for_user, user_is_scoped
from apps.schedules.models import ScanSchedule
from apps.targets.models import Target

User = get_user_model()


class ScheduleFilterForm(forms.Form):
    q = forms.CharField(required=False)
    schedule_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Frequencies")] + list(ScanSchedule.ScheduleType.choices),
    )
    enabled = forms.ChoiceField(
        required=False,
        choices=[("", "All States"), ("true", "Enabled"), ("false", "Disabled")],
    )
    owner = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="All Owners")
    next_run_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    next_run_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("username")
        if user is not None and user_is_scoped(user):
            self.fields["owner"].queryset = self.fields["owner"].queryset.filter(pk=user.pk)
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Search by schedule, target, profile..."


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = ScanSchedule
        fields = [
            "name",
            "target",
            "profile",
            "scan_type",
            "port_input",
            "enable_host_discovery",
            "enable_service_detection",
            "enable_version_detection",
            "enable_os_detection",
            "enable_traceroute",
            "enable_dns_resolution",
            "timing_profile",
            "schedule_type",
            "recurrence_rule",
            "start_at",
            "end_at",
            "is_enabled",
            "notification_enabled",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "port_input": forms.TextInput(attrs={"placeholder": "80,443,8080 or 1-1024"}),
            "recurrence_rule": forms.TextInput(attrs={"placeholder": "For custom: e.g. 6h, 2d, cron-like note"}),
            "name": forms.TextInput(attrs={"placeholder": "Nightly DMZ Sweep"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = Target.objects.order_by("target_value")
        if user is not None:
            self.fields["target"].queryset = scope_queryset_for_user(
                self.fields["target"].queryset,
                user,
                ("owner", "created_by"),
            )
        self.fields["profile"].queryset = self.fields["profile"].queryset.filter(is_active=True).order_by("name")
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "h-4 w-4 rounded border-slate-700 bg-slate-900 text-blue-500"
            else:
                field.widget.attrs["class"] = "scanops-input"

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")
        schedule_type = cleaned_data.get("schedule_type")
        recurrence_rule = (cleaned_data.get("recurrence_rule") or "").strip()

        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "End time must be later than start time.")
        if schedule_type == ScanSchedule.ScheduleType.CUSTOM and not recurrence_rule:
            self.add_error("recurrence_rule", "Custom schedules require a recurrence rule.")
        if schedule_type != ScanSchedule.ScheduleType.CUSTOM and recurrence_rule and len(recurrence_rule) > 255:
            self.add_error("recurrence_rule", "Recurrence rule is too long.")
        return cleaned_data
