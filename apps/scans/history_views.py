from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.ops.models import PermissionRule
from apps.ops.rbac import CapabilityRequiredMixin, scope_queryset_for_user
from apps.scans.forms import HistoryFilterForm
from apps.scans.models import ScanExecution
from apps.scans.services.execution_service import archive_execution, restore_execution
from apps.scans.services.history_service import (
    apply_execution_filters,
    clone_scan_request_from_execution,
    permanently_delete_execution,
    rerun_execution,
)
from apps.scans.services.result_service import get_previous_result


def _redirect_back(request: HttpRequest, fallback: str) -> HttpResponse:
    return redirect(request.META.get("HTTP_REFERER") or fallback)


class _BaseHistoryListView(CapabilityRequiredMixin, ListView):
    capability_key = PermissionRule.PermissionKey.VIEW_HISTORY
    model = ScanExecution
    context_object_name = "executions"
    paginate_by = 15
    include_user_filter = True
    page_mode = "history"
    page_title = "Scan History"
    page_subtitle = "Complete operational audit trail for scan executions."

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/history_table.html"]
        return [self.template_name]

    def base_queryset(self):
        queryset = ScanExecution.objects.select_related(
            "scan_request",
            "scan_request__target",
            "scan_request__profile",
            "scan_request__requested_by",
        ).prefetch_related("result")
        return scope_queryset_for_user(queryset, self.request.user, ("scan_request__requested_by",))

    def get_queryset(self):
        queryset = self.base_queryset()
        self.filter_form = HistoryFilterForm(
            self.request.GET or None,
            user=self.request.user,
            include_user_filter=self.include_user_filter,
        )
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            queryset = apply_execution_filters(
                queryset,
                q=cleaned.get("q") or "",
                status=cleaned.get("status") or "",
                target=cleaned.get("target"),
                profile=cleaned.get("profile"),
                requested_by=cleaned.get("requested_by"),
                date_from=cleaned.get("date_from"),
                date_to=cleaned.get("date_to"),
            )
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        context["include_user_filter"] = "requested_by" in self.filter_form.fields
        context["page_mode"] = self.page_mode
        context["page_title"] = self.page_title
        context["page_subtitle"] = self.page_subtitle
        context["breadcrumbs"] = [
            {"label": "History", "url": reverse("scans:history")},
            {"label": self.page_title, "url": ""},
        ]
        return context


class ScanHistoryView(_BaseHistoryListView):
    template_name = "scans/history.html"
    page_mode = "history"
    page_title = "Scan History"
    page_subtitle = "Full execution history across all operators."

    def get_queryset(self):
        return super().get_queryset().filter(is_archived=False)


class MyHistoryView(_BaseHistoryListView):
    template_name = "scans/my_history.html"
    include_user_filter = False
    page_mode = "my_history"
    page_title = "My History"
    page_subtitle = "Your recent and favorited execution trail."

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            is_archived=False,
            scan_request__requested_by=self.request.user,
        )
        return queryset


class ArchivedHistoryView(_BaseHistoryListView):
    template_name = "scans/archived_history.html"
    page_mode = "archived"
    page_title = "Archived History"
    page_subtitle = "Archived execution records with restore and deletion controls."

    def get_queryset(self):
        return super().get_queryset().filter(is_archived=True)


class HistoryArchiveExecutionView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_HISTORY

    def post(self, request, pk: int) -> HttpResponse:
        queryset = scope_queryset_for_user(ScanExecution.objects.all(), request.user, ("scan_request__requested_by",))
        execution = get_object_or_404(queryset, pk=pk)
        archive_execution(execution)
        messages.success(request, f"{execution.execution_id} archived.")
        return _redirect_back(request, reverse("scans:history"))


class HistoryRestoreExecutionView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_HISTORY

    def post(self, request, pk: int) -> HttpResponse:
        queryset = scope_queryset_for_user(ScanExecution.objects.all(), request.user, ("scan_request__requested_by",))
        execution = get_object_or_404(queryset, pk=pk)
        restore_execution(execution)
        messages.success(request, f"{execution.execution_id} restored from archive.")
        return _redirect_back(request, reverse("scans:history-archived"))


class HistoryDeleteExecutionView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_HISTORY

    def post(self, request, pk: int) -> HttpResponse:
        queryset = scope_queryset_for_user(ScanExecution.objects.all(), request.user, ("scan_request__requested_by",))
        execution = get_object_or_404(queryset, pk=pk)
        execution_id = execution.execution_id
        permanently_delete_execution(execution)
        messages.warning(request, f"{execution_id} was permanently deleted.")
        return _redirect_back(request, reverse("scans:history-archived"))


class HistoryCloneSettingsView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.CREATE_SCAN_REQUEST

    def post(self, request, pk: int) -> HttpResponse:
        queryset = scope_queryset_for_user(ScanExecution.objects.all(), request.user, ("scan_request__requested_by",))
        execution = get_object_or_404(queryset, pk=pk)
        cloned_request = clone_scan_request_from_execution(execution, user=request.user)
        messages.success(request, f"Settings cloned into request #{cloned_request.pk}.")
        return _redirect_back(request, reverse("scans:new"))


class HistoryRerunView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.CONTROL_SCAN_EXECUTIONS

    def post(self, request, pk: int) -> HttpResponse:
        queryset = scope_queryset_for_user(ScanExecution.objects.all(), request.user, ("scan_request__requested_by",))
        execution = get_object_or_404(queryset, pk=pk)
        new_execution = rerun_execution(execution, user=request.user)
        messages.success(request, f"Re-run queued as {new_execution.execution_id}.")
        return _redirect_back(request, reverse("scans:running"))


class HistoryCompareRedirectView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.COMPARE_RESULTS

    def post(self, request, pk: int) -> HttpResponse:
        queryset = scope_queryset_for_user(
            ScanExecution.objects.select_related("result"),
            request.user,
            ("scan_request__requested_by",),
        )
        execution = get_object_or_404(queryset, pk=pk)
        result = getattr(execution, "result", None)
        if result is None:
            messages.error(request, "No result available yet for this execution.")
            return _redirect_back(request, reverse("scans:history"))
        previous_result = get_previous_result(result)
        if previous_result is None:
            messages.info(request, "No previous result found for comparison.")
            return redirect("scans:result-compare-current", pk=result.pk)
        return redirect(
            f"{reverse('scans:result-compare')}?left_result={previous_result.pk}&right_result={result.pk}"
        )
