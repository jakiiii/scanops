from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.assets.models import Asset
from apps.ops.rbac import scope_queryset_for_user, user_is_scoped
from apps.reports.models import GeneratedReport
from apps.scans.models import ScanExecution, ScanResult

User = get_user_model()


class ReportFilterForm(forms.Form):
    q = forms.CharField(required=False)
    report_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Types")] + list(GeneratedReport.ReportType.choices),
    )
    format = forms.ChoiceField(
        required=False,
        choices=[("", "All Formats")] + list(GeneratedReport.Format.choices),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(GeneratedReport.Status.choices),
    )
    generated_by = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="All Analysts")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["generated_by"].queryset = User.objects.filter(is_active=True).order_by("username")
        if user is not None and user_is_scoped(user):
            self.fields["generated_by"].queryset = self.fields["generated_by"].queryset.filter(pk=user.pk)
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Search report title, target, execution ID..."


class ReportGenerateForm(forms.Form):
    class SourceType(models.TextChoices):
        RESULT = "result", "Scan Result"
        EXECUTION = "execution", "Scan Execution"
        COMPARISON = "comparison", "Comparison"
        ASSET = "asset", "Asset"

    title = forms.CharField(max_length=180, required=False)
    source_type = forms.ChoiceField(choices=SourceType.choices)
    report_type = forms.ChoiceField(choices=GeneratedReport.ReportType.choices)
    format = forms.ChoiceField(choices=GeneratedReport.Format.choices, initial=GeneratedReport.Format.HTML)
    source_result = forms.ModelChoiceField(queryset=ScanResult.objects.none(), required=False)
    source_execution = forms.ModelChoiceField(queryset=ScanExecution.objects.none(), required=False)
    comparison_left_result = forms.ModelChoiceField(queryset=ScanResult.objects.none(), required=False)
    comparison_right_result = forms.ModelChoiceField(queryset=ScanResult.objects.none(), required=False)
    asset = forms.ModelChoiceField(queryset=Asset.objects.none(), required=False)
    include_summary = forms.BooleanField(required=False, initial=True)
    include_ports = forms.BooleanField(required=False, initial=True)
    include_services = forms.BooleanField(required=False, initial=True)
    include_findings = forms.BooleanField(required=False, initial=True)
    include_timeline = forms.BooleanField(required=False, initial=False)
    summary_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        result_queryset = ScanResult.objects.select_related("execution__scan_request__target").order_by("-generated_at")
        execution_queryset = ScanExecution.objects.select_related("scan_request__target").order_by("-created_at")
        asset_queryset = Asset.objects.order_by("name")
        if user is not None:
            result_queryset = scope_queryset_for_user(result_queryset, user, ("execution__scan_request__requested_by",))
            execution_queryset = scope_queryset_for_user(execution_queryset, user, ("scan_request__requested_by",))
            asset_queryset = scope_queryset_for_user(asset_queryset, user, ("target__owner", "target__created_by"))
        self.fields["source_result"].queryset = result_queryset
        self.fields["comparison_left_result"].queryset = result_queryset
        self.fields["comparison_right_result"].queryset = result_queryset
        self.fields["source_execution"].queryset = execution_queryset
        self.fields["asset"].queryset = asset_queryset
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "h-4 w-4 rounded border-slate-700 bg-slate-900 text-blue-500"
            else:
                field.widget.attrs["class"] = "scanops-input"
        self.fields["title"].widget.attrs["placeholder"] = "Optional custom report title"

    def clean(self):
        cleaned_data = super().clean()
        source_type = cleaned_data.get("source_type")
        if source_type == self.SourceType.RESULT and not cleaned_data.get("source_result"):
            self.add_error("source_result", "Choose a source result.")
        if source_type == self.SourceType.EXECUTION and not cleaned_data.get("source_execution"):
            self.add_error("source_execution", "Choose a source execution.")
        if source_type == self.SourceType.ASSET and not cleaned_data.get("asset"):
            self.add_error("asset", "Choose an asset.")
        if source_type == self.SourceType.COMPARISON:
            left = cleaned_data.get("comparison_left_result")
            right = cleaned_data.get("comparison_right_result")
            if not left:
                self.add_error("comparison_left_result", "Choose the baseline result.")
            if not right:
                self.add_error("comparison_right_result", "Choose the current result.")
            if left and right and left.pk == right.pk:
                self.add_error("comparison_right_result", "Select a different result for comparison.")

        if not cleaned_data.get("title"):
            report_type = dict(GeneratedReport.ReportType.choices).get(
                cleaned_data.get("report_type"),
                "Report",
            )
            cleaned_data["title"] = f"{report_type} - {timezone.now():%Y-%m-%d %H:%M}"
        return cleaned_data
