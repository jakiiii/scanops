from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.scans.forms import CompareResultsForm, ResultFilterForm
from apps.scans.models import ScanExecution, ScanResult
from apps.scans.services.comparison_service import build_comparison_from_current, compare_results
from apps.scans.services.result_service import (
    build_host_detail_context,
    build_result_detail_context,
    generate_mock_result_for_execution,
)
from apps.targets.models import Target


class ScanResultListView(LoginRequiredMixin, ListView):
    model = ScanResult
    template_name = "scans/results_list.html"
    context_object_name = "results"
    paginate_by = 15

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/results_table.html"]
        return [self.template_name]

    def get_queryset(self):
        if settings.DEBUG:
            pending_results = ScanExecution.objects.filter(
                status=ScanExecution.Status.COMPLETED,
                result__isnull=True,
            )[:20]
            for execution in pending_results:
                generate_mock_result_for_execution(execution, force=False)

        queryset = (
            ScanResult.objects.select_related(
                "execution",
                "execution__scan_request",
                "execution__scan_request__target",
                "execution__scan_request__profile",
                "execution__scan_request__requested_by",
            )
            .prefetch_related("port_results")
            .filter(execution__is_archived=False)
            .order_by("-generated_at")
        )

        self.filter_form = ResultFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            if q:
                queryset = queryset.filter(
                    Q(target_snapshot__icontains=q)
                    | Q(execution__execution_id__icontains=q)
                    | Q(execution__scan_request__target__name__icontains=q)
                )
            if cleaned.get("date_from"):
                queryset = queryset.filter(generated_at__date__gte=cleaned["date_from"])
            if cleaned.get("date_to"):
                queryset = queryset.filter(generated_at__date__lte=cleaned["date_to"])
            if cleaned.get("target"):
                queryset = queryset.filter(execution__scan_request__target=cleaned["target"])
            if cleaned.get("execution_status"):
                queryset = queryset.filter(execution__status=cleaned["execution_status"])
            if cleaned.get("profile"):
                queryset = queryset.filter(execution__scan_request__profile=cleaned["profile"])
            if cleaned.get("service"):
                queryset = queryset.filter(port_results__service_name__icontains=cleaned["service"])
            if cleaned.get("risk_level"):
                queryset = queryset.filter(port_results__risk_level=cleaned["risk_level"])
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        summary_source = ScanResult.objects.filter(execution__is_archived=False)
        context["result_summary"] = {
            "total": summary_source.count(),
            "high_risk": summary_source.filter(port_results__risk_level="high").distinct().count(),
            "medium_risk": summary_source.filter(port_results__risk_level="medium").distinct().count(),
            "hosts_down": summary_source.filter(host_status=ScanResult.HostStatus.DOWN).count(),
        }
        context["breadcrumbs"] = [
            {"label": "Results", "url": ""},
        ]
        return context


class ScanResultDetailView(LoginRequiredMixin, DetailView):
    model = ScanResult
    template_name = "scans/result_detail.html"
    context_object_name = "result"

    def get_queryset(self):
        return ScanResult.objects.select_related(
            "execution",
            "execution__scan_request",
            "execution__scan_request__target",
            "execution__scan_request__profile",
            "execution__scan_request__requested_by",
        ).prefetch_related("port_results")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = context["result"]
        context.update(build_result_detail_context(result))
        context["tab"] = self.request.GET.get("tab", "overview")
        context["breadcrumbs"] = [
            {"label": "Results", "url": reverse("scans:results")},
            {"label": result.execution.execution_id, "url": ""},
        ]
        return context


class ScanRawOutputView(LoginRequiredMixin, DetailView):
    model = ScanResult
    template_name = "scans/raw_output.html"
    context_object_name = "result"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Results", "url": reverse("scans:results")},
            {"label": self.object.execution.execution_id, "url": reverse("scans:result-detail", kwargs={"pk": self.object.pk})},
            {"label": "Raw Output", "url": ""},
        ]
        return context


class ScanParsedOutputView(LoginRequiredMixin, DetailView):
    model = ScanResult
    template_name = "scans/parsed_output.html"
    context_object_name = "result"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["parsed"] = self.object.parsed_output_json or {}
        context["breadcrumbs"] = [
            {"label": "Results", "url": reverse("scans:results")},
            {"label": self.object.execution.execution_id, "url": reverse("scans:result-detail", kwargs={"pk": self.object.pk})},
            {"label": "Parsed Output", "url": ""},
        ]
        return context


class ScanResultCompareView(LoginRequiredMixin, TemplateView):
    template_name = "scans/result_compare.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.headers.get("HX-Request"):
            return render(request, "partials/comparison_summary.html", context)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_result = None
        target = None
        pk = self.kwargs.get("pk")
        if pk:
            current_result = get_object_or_404(ScanResult, pk=pk)
            target = current_result.execution.scan_request.target

        initial = {}
        if current_result and not self.request.GET:
            previous = build_comparison_from_current(current_result)
            if previous:
                initial = {
                    "left_result": previous["base_result"].pk,
                    "right_result": previous["current_result"].pk,
                }
            else:
                initial = {"right_result": current_result.pk}

        form = CompareResultsForm(self.request.GET or None, target=target, initial=initial)
        comparison = None
        if self.request.GET and form.is_valid():
            left_result = form.cleaned_data["left_result"]
            right_result = form.cleaned_data["right_result"]
            if left_result.pk == right_result.pk:
                messages.warning(self.request, "Choose two different results to compare.")
            else:
                comparison = compare_results(left_result, right_result)
        elif current_result and not self.request.GET:
            comparison = build_comparison_from_current(current_result)

        context.update(
            {
                "form": form,
                "current_result": current_result,
                "comparison": comparison,
                "breadcrumbs": [
                    {"label": "Results", "url": reverse("scans:results")},
                    {"label": "Compare", "url": ""},
                ],
            }
        )
        return context


class HostDetailView(LoginRequiredMixin, DetailView):
    model = Target
    template_name = "scans/host_detail.html"
    context_object_name = "target"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_host_detail_context(self.object))
        context["breadcrumbs"] = [
            {"label": "Results", "url": reverse("scans:results")},
            {"label": "Host Detail", "url": ""},
        ]
        return context


class ResultPortsPartialView(LoginRequiredMixin, View):
    def get(self, request, pk: int) -> HttpResponse:
        result = get_object_or_404(ScanResult, pk=pk)
        return render(
            request,
            "partials/result_ports_table.html",
            {"result": result, "port_results": result.port_results.all().order_by("port", "protocol")},
        )
