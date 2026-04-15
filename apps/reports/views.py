from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.notifications.services.notification_service import notify_report_generated
from apps.reports.forms import ReportFilterForm, ReportGenerateForm
from apps.reports.models import GeneratedReport
from apps.reports.services.report_service import (
    build_report_payload,
    generate_report_from_cleaned_data,
    regenerate_report,
)


def _redirect_back(request, fallback: str):
    return redirect(request.META.get("HTTP_REFERER") or fallback)


class ReportListView(LoginRequiredMixin, ListView):
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
        self.filter_form = ReportFilterForm(self.request.GET or None)
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
        summary_source = GeneratedReport.objects.all()
        context["summary"] = {
            "total": summary_source.count(),
            "generated": summary_source.filter(status=GeneratedReport.Status.GENERATED).count(),
            "failed": summary_source.filter(status=GeneratedReport.Status.FAILED).count(),
            "archived": summary_source.filter(status=GeneratedReport.Status.ARCHIVED).count(),
        }
        context["breadcrumbs"] = [
            {"label": "Reports", "url": ""},
        ]
        return context


class ReportGenerateView(LoginRequiredMixin, FormView):
    form_class = ReportGenerateForm
    template_name = "reports/generate.html"

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
            source_result=self.form_class().fields["source_result"].queryset.first(),
            include_sections={"summary": True, "ports": True, "services": True, "findings": True, "timeline": False},
        )
        context["preview_payload"] = sample_payload
        return context


class ReportPreviewView(LoginRequiredMixin, View):
    def post(self, request):
        form = ReportGenerateForm(request.POST)
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


class ReportDetailView(LoginRequiredMixin, DetailView):
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


class ReportPrintView(LoginRequiredMixin, DetailView):
    model = GeneratedReport
    template_name = "reports/printable.html"
    context_object_name = "report"


class ReportArchiveView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        report = get_object_or_404(GeneratedReport, pk=pk)
        report.status = GeneratedReport.Status.ARCHIVED
        report.save(update_fields=["status", "updated_at"])
        messages.info(request, f"Archived report: {report.title}")
        return _redirect_back(request, reverse("reports:list"))


class ReportRegenerateView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        report = get_object_or_404(GeneratedReport, pk=pk)
        report = regenerate_report(report, user=request.user)
        notify_report_generated(report)
        messages.success(request, f"Regenerated report: {report.title}")
        return _redirect_back(request, reverse("reports:detail", kwargs={"pk": report.pk}))


class ReportDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk: int):
        report = get_object_or_404(GeneratedReport, pk=pk)
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

