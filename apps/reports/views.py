from __future__ import annotations

import json

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.notifications.services.notification_service import notify_report_generated
from apps.ops.models import PermissionRule
from apps.ops.rbac import CapabilityRequiredMixin
from apps.ops.services import data_visibility_service
from apps.reports.forms import ReportFilterForm, ReportGenerateForm
from apps.reports.models import GeneratedReport
from apps.reports.services.report_service import (
    build_report_payload,
    generate_report_from_cleaned_data,
    regenerate_report,
)


def _redirect_back(request, fallback: str):
    return redirect(request.META.get("HTTP_REFERER") or fallback)


class ReportListView(CapabilityRequiredMixin, ListView):
    capability_key = PermissionRule.PermissionKey.VIEW_REPORTS
    model = GeneratedReport
    template_name = "reports/list.html"
    context_object_name = "reports"
    paginate_by = 15

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/reports_table.html"]
        return [self.template_name]

    def get_queryset(self):
        queryset = (
            GeneratedReport.objects.select_related(
                "generated_by",
                "source_result__execution__scan_request__target",
                "source_execution__scan_request__target",
                "asset",
            )
            .order_by("-created_at")
        )
        queryset = data_visibility_service.get_user_visible_reports(self.request.user, queryset=queryset)
        self.filter_form = ReportFilterForm(self.request.GET or None, user=self.request.user)
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            if q:
                queryset = queryset.filter(
                    Q(title__icontains=q)
                    | Q(summary__icontains=q)
                    | Q(source_result__target_snapshot__icontains=q)
                    | Q(source_execution__execution_id__icontains=q)
                    | Q(asset__name__icontains=q)
                )
            if cleaned.get("report_type"):
                queryset = queryset.filter(report_type=cleaned["report_type"])
            if cleaned.get("format"):
                queryset = queryset.filter(format=cleaned["format"])
            if cleaned.get("status"):
                queryset = queryset.filter(status=cleaned["status"])
            if cleaned.get("generated_by"):
                queryset = queryset.filter(generated_by=cleaned["generated_by"])
            if cleaned.get("date_from"):
                queryset = queryset.filter(created_at__date__gte=cleaned["date_from"])
            if cleaned.get("date_to"):
                queryset = queryset.filter(created_at__date__lte=cleaned["date_to"])
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        summary_source = data_visibility_service.get_user_visible_reports(
            self.request.user,
            queryset=GeneratedReport.objects.all(),
        )
        context["summary"] = {
            "total": summary_source.count(),
            "generated": summary_source.filter(status=GeneratedReport.Status.GENERATED).count(),
            "failed": summary_source.filter(status=GeneratedReport.Status.FAILED).count(),
            "archived": summary_source.filter(status=GeneratedReport.Status.ARCHIVED).count(),
        }
        context["breadcrumbs"] = [
            {"label": "Reports", "url": ""},
        ]
        context["scope_label"] = "All" if data_visibility_service.user_can_view_all_data(self.request.user) else "My"
        return context


class ReportGenerateView(CapabilityRequiredMixin, FormView):
    capability_key = PermissionRule.PermissionKey.GENERATE_REPORTS
    form_class = ReportGenerateForm
    template_name = "reports/generate.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial.update(
            {
                "source_type": ReportGenerateForm.SourceType.RESULT,
                "report_type": GeneratedReport.ReportType.EXECUTIVE_SUMMARY,
                "format": GeneratedReport.Format.HTML,
                "include_summary": True,
                "include_ports": True,
                "include_services": True,
                "include_findings": True,
            }
        )
        return initial

    def form_valid(self, form):
        report = generate_report_from_cleaned_data(form.cleaned_data, user=self.request.user)
        notify_report_generated(report)
        messages.success(self.request, f"Report generated: {report.title}")
        return redirect("reports:detail", pk=report.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Reports", "url": reverse("reports:list")},
            {"label": "Generate", "url": ""},
        ]
        sample_payload = build_report_payload(
            report_type=GeneratedReport.ReportType.EXECUTIVE_SUMMARY,
            source_result=self.form_class(user=self.request.user).fields["source_result"].queryset.first(),
            include_sections={"summary": True, "ports": True, "services": True, "findings": True, "timeline": False},
        )
        context["preview_payload"] = sample_payload
        return context


class ReportPreviewView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.GENERATE_REPORTS

    def post(self, request):
        form = ReportGenerateForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, "partials/report_preview.html", {"preview": {}, "errors": form.errors})
        preview_payload = build_report_payload(
            report_type=form.cleaned_data["report_type"],
            source_result=form.cleaned_data.get("source_result"),
            source_execution=form.cleaned_data.get("source_execution"),
            comparison_left_result=form.cleaned_data.get("comparison_left_result"),
            comparison_right_result=form.cleaned_data.get("comparison_right_result"),
            asset=form.cleaned_data.get("asset"),
            include_sections={
                "summary": bool(form.cleaned_data.get("include_summary")),
                "ports": bool(form.cleaned_data.get("include_ports")),
                "services": bool(form.cleaned_data.get("include_services")),
                "findings": bool(form.cleaned_data.get("include_findings")),
                "timeline": bool(form.cleaned_data.get("include_timeline")),
            },
            summary_notes=form.cleaned_data.get("summary_notes", ""),
        )
        return render(request, "partials/report_preview.html", {"preview": preview_payload, "errors": {}})


class ReportDetailView(CapabilityRequiredMixin, DetailView):
    capability_key = PermissionRule.PermissionKey.VIEW_REPORTS
    model = GeneratedReport
    template_name = "reports/detail.html"
    context_object_name = "report"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Reports", "url": reverse("reports:list")},
            {"label": self.object.title, "url": ""},
        ]
        return context

    def get_queryset(self):
        queryset = GeneratedReport.objects.select_related(
            "generated_by",
            "source_result__execution__scan_request__requested_by",
            "source_execution__scan_request__requested_by",
            "comparison_left_result__execution__scan_request__requested_by",
            "comparison_right_result__execution__scan_request__requested_by",
        )
        return data_visibility_service.get_user_visible_reports(self.request.user, queryset=queryset)


class ReportPrintView(CapabilityRequiredMixin, DetailView):
    capability_key = PermissionRule.PermissionKey.VIEW_REPORTS
    model = GeneratedReport
    template_name = "reports/printable.html"
    context_object_name = "report"

    def get_queryset(self):
        queryset = GeneratedReport.objects.select_related(
            "generated_by",
            "source_result__execution__scan_request__requested_by",
            "source_execution__scan_request__requested_by",
            "comparison_left_result__execution__scan_request__requested_by",
            "comparison_right_result__execution__scan_request__requested_by",
        )
        return data_visibility_service.get_user_visible_reports(self.request.user, queryset=queryset)


class ReportArchiveView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_REPORTS

    def post(self, request, pk: int):
        queryset = data_visibility_service.get_user_visible_reports(request.user, queryset=GeneratedReport.objects.all())
        report = get_object_or_404(queryset, pk=pk)
        report.status = GeneratedReport.Status.ARCHIVED
        report.save(update_fields=["status", "updated_at"])
        messages.info(request, f"Archived report: {report.title}")
        return _redirect_back(request, reverse("reports:list"))


class ReportRegenerateView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_REPORTS

    def post(self, request, pk: int):
        queryset = data_visibility_service.get_user_visible_reports(request.user, queryset=GeneratedReport.objects.all())
        report = get_object_or_404(queryset, pk=pk)
        report = regenerate_report(report, user=request.user)
        notify_report_generated(report)
        messages.success(request, f"Regenerated report: {report.title}")
        return _redirect_back(request, reverse("reports:detail", kwargs={"pk": report.pk}))


class ReportDownloadView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.VIEW_REPORTS

    def get(self, request, pk: int):
        queryset = data_visibility_service.get_user_visible_reports(request.user, queryset=GeneratedReport.objects.all())
        report = get_object_or_404(queryset, pk=pk)
        if report.format == GeneratedReport.Format.JSON:
            return HttpResponse(
                json.dumps(report.report_payload_json, indent=2),
                content_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="report-{report.pk}.json"'},
            )
        if report.format == GeneratedReport.Format.TXT:
            return HttpResponse(
                report.summary or "Generated report",
                content_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="report-{report.pk}.txt"'},
            )
        return HttpResponse(
            report.rendered_html,
            content_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="report-{report.pk}.html"'},
        )
