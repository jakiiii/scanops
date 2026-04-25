from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from apps.core.services.scan_policy import build_scan_summary, validate_scan_options
from apps.ops.rbac import user_is_scoped
from apps.ops.services import data_visibility_service
from apps.scans.models import ScanExecution, ScanPortResult, ScanProfile, ScanRequest, ScanResult
from apps.targets.models import Target

User = get_user_model()


class ScanRequestForm(forms.ModelForm):
    class Meta:
        model = ScanRequest
        fields = [
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
            "notes",
        ]
        widgets = {
            "target": forms.Select(attrs={"class": "scanops-input"}),
            "profile": forms.Select(attrs={"class": "scanops-input"}),
            "scan_type": forms.Select(attrs={"class": "scanops-input"}),
            "port_input": forms.TextInput(
                attrs={
                    "class": "scanops-input",
                    "placeholder": "80,443,8443 or 1-1024",
                }
            ),
            "timing_profile": forms.Select(attrs={"class": "scanops-input"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "scanops-input",
                    "rows": 3,
                    "placeholder": "Optional scan notes and approval context",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        is_authenticated_user = bool(getattr(user, "is_authenticated", False))

        target_queryset = Target.objects.filter(status=Target.Status.ACTIVE).order_by("target_value")
        if is_authenticated_user:
            target_queryset = data_visibility_service.get_user_visible_targets(user, queryset=target_queryset)
        else:
            target_queryset = target_queryset.none()
        self.fields["target"].queryset = target_queryset

        profile_queryset = ScanProfile.objects.filter(is_active=True).order_by("is_system", "name")
        if is_authenticated_user:
            profile_queryset = data_visibility_service.get_user_visible_scan_profiles(user, queryset=profile_queryset)
        else:
            profile_queryset = profile_queryset.filter(is_system=True)
        self.fields["profile"].queryset = profile_queryset
        for checkbox_name in (
            "enable_host_discovery",
            "enable_service_detection",
            "enable_version_detection",
            "enable_os_detection",
            "enable_traceroute",
            "enable_dns_resolution",
        ):
            self.fields[checkbox_name].widget.attrs.update(
                {"class": "h-4 w-4 rounded border-slate-700 bg-slate-900 text-blue-500"}
            )

        if not is_authenticated_user:
            readonly_fields = (
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
                "notes",
            )
            for field_name in readonly_fields:
                self.fields[field_name].disabled = True
            self.fields["target"].help_text = "Sign in to select your targets."
            self.fields["profile"].help_text = "System profiles are shown for reference only."

        self.policy_result = None
        self.summary = None

    def clean(self):
        cleaned_data = super().clean()

        profile = cleaned_data.get("profile")
        if profile and not self.data.get("scan_type"):
            cleaned_data["scan_type"] = profile.scan_type
        if profile and not self.data.get("timing_profile"):
            cleaned_data["timing_profile"] = profile.timing_profile

        self.policy_result = validate_scan_options(cleaned_data)
        if not self.policy_result.is_valid:
            raise forms.ValidationError(self.policy_result.errors)

        cleaned_data["port_input"] = self.policy_result.normalized_port_input
        self.summary = build_scan_summary(cleaned_data, self.policy_result)
        return cleaned_data


class RunningFilterForm(forms.Form):
    q = forms.CharField(required=False)
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(ScanExecution.Status.choices),
    )
    queue_status = forms.ChoiceField(
        required=False,
        choices=[("", "All Queue States")] + list(ScanExecution.QueueStatus.choices),
    )
    requested_by = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Users",
    )
    target = forms.ModelChoiceField(
        queryset=Target.objects.none(),
        required=False,
        empty_label="All Targets",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requested_by"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["target"].queryset = Target.objects.order_by("target_value")
        if user is not None:
            if user_is_scoped(user):
                self.fields["requested_by"].queryset = self.fields["requested_by"].queryset.filter(pk=user.pk)
                self.fields["requested_by"].initial = user.pk
            self.fields["target"].queryset = data_visibility_service.get_user_visible_targets(
                user,
                queryset=self.fields["target"].queryset,
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Target, execution ID, worker..."


class ResultFilterForm(forms.Form):
    q = forms.CharField(required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    target = forms.ModelChoiceField(queryset=Target.objects.none(), required=False, empty_label="All Targets")
    execution_status = forms.ChoiceField(
        required=False,
        choices=[("", "Any Status")] + list(ScanExecution.Status.choices),
    )
    profile = forms.ModelChoiceField(queryset=ScanProfile.objects.none(), required=False, empty_label="All Profiles")
    service = forms.CharField(required=False)
    risk_level = forms.ChoiceField(
        required=False,
        choices=[("", "Any Risk")] + list(ScanPortResult.RiskLevel.choices),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = Target.objects.order_by("target_value")
        self.fields["profile"].queryset = ScanProfile.objects.filter(is_active=True).order_by("name")
        if user is not None:
            self.fields["target"].queryset = data_visibility_service.get_user_visible_targets(
                user,
                queryset=self.fields["target"].queryset,
            )
            self.fields["profile"].queryset = data_visibility_service.get_user_visible_scan_profiles(
                user,
                queryset=self.fields["profile"].queryset,
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Scan ID, hostname, target snapshot..."
        self.fields["service"].widget.attrs["placeholder"] = "http, ssh, mysql..."


class HistoryFilterForm(forms.Form):
    q = forms.CharField(required=False)
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(ScanExecution.Status.choices),
    )
    target = forms.ModelChoiceField(queryset=Target.objects.none(), required=False, empty_label="All Targets")
    profile = forms.ModelChoiceField(queryset=ScanProfile.objects.none(), required=False, empty_label="All Profiles")
    requested_by = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="All Users")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user=None, include_user_filter=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = Target.objects.order_by("target_value")
        self.fields["profile"].queryset = ScanProfile.objects.filter(is_active=True).order_by("name")
        self.fields["requested_by"].queryset = User.objects.filter(is_active=True).order_by("username")
        if user is not None:
            self.fields["target"].queryset = data_visibility_service.get_user_visible_targets(
                user,
                queryset=self.fields["target"].queryset,
            )
            self.fields["profile"].queryset = data_visibility_service.get_user_visible_scan_profiles(
                user,
                queryset=self.fields["profile"].queryset,
            )
            if user_is_scoped(user):
                self.fields["requested_by"].queryset = self.fields["requested_by"].queryset.filter(pk=user.pk)
        if (not include_user_filter or (user is not None and user_is_scoped(user))) and "requested_by" in self.fields:
            self.fields.pop("requested_by")
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Execution ID, target, worker..."


class CompareResultsForm(forms.Form):
    left_result = forms.ModelChoiceField(queryset=ScanResult.objects.none(), required=True, label="Baseline")
    right_result = forms.ModelChoiceField(queryset=ScanResult.objects.none(), required=True, label="Current")

    def __init__(self, *args, target: Target | None = None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ScanResult.objects.select_related("execution__scan_request__target").order_by("-generated_at")
        if user is not None:
            queryset = data_visibility_service.get_user_visible_results(user, queryset=queryset)
        if target is not None:
            queryset = queryset.filter(execution__scan_request__target=target)
        self.fields["left_result"].queryset = queryset
        self.fields["right_result"].queryset = queryset
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
