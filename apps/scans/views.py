from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView

from apps.core.services.scan_policy import build_scan_summary, validate_scan_options
from apps.scans.forms import ScanRequestForm
from apps.scans.models import ScanRequest
from apps.targets.models import Target


class ScanRequestCreateView(LoginRequiredMixin, CreateView):
    model = ScanRequest
    form_class = ScanRequestForm
    template_name = "scans/new_scan.html"

    def get_initial(self):
        initial = super().get_initial()
        initial.update(
            {
                "scan_type": ScanRequest._meta.get_field("scan_type").default,
                "timing_profile": ScanRequest._meta.get_field("timing_profile").default,
                "enable_host_discovery": True,
                "enable_service_detection": True,
                "enable_version_detection": False,
                "enable_os_detection": False,
                "enable_traceroute": False,
                "enable_dns_resolution": True,
            }
        )
        return initial

    def form_valid(self, form):
        self.object: ScanRequest = form.save(commit=False)
        self.object.requested_by = self.request.user
        self.object.status = ScanRequest.Status.PENDING
        summary = form.summary or build_scan_summary(form.cleaned_data, form.policy_result)
        self.object.validation_summary = json.dumps(summary)
        self.object.save()

        messages.success(self.request, "Scan request created and queued for validation.")
        if form.policy_result:
            for warning in form.policy_result.warnings:
                messages.warning(self.request, warning)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("scans:new")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial_payload = self.get_initial()
        initial_payload["target"] = None
        initial_policy = validate_scan_options(initial_payload)
        context["scan_preview"] = build_scan_summary(initial_payload, initial_policy)
        context["breadcrumbs"] = [
            {"label": "Scans", "url": ""},
            {"label": "New Request", "url": ""},
        ]
        return context


class ScanPreviewView(LoginRequiredMixin, View):
    template_name = "partials/scan_preview.html"

    @staticmethod
    def _coerce_checkbox(raw_value: str | None) -> bool:
        return (raw_value or "").lower() in {"1", "true", "on", "yes"}

    def post(self, request, *args, **kwargs) -> HttpResponse:
        target = None
        target_id = request.POST.get("target")
        if target_id and target_id.isdigit():
            target = Target.objects.filter(pk=int(target_id)).first()

        payload = {
            "target": target,
            "scan_type": request.POST.get("scan_type", ""),
            "port_input": request.POST.get("port_input", ""),
            "enable_host_discovery": self._coerce_checkbox(request.POST.get("enable_host_discovery")),
            "enable_service_detection": self._coerce_checkbox(request.POST.get("enable_service_detection")),
            "enable_version_detection": self._coerce_checkbox(request.POST.get("enable_version_detection")),
            "enable_os_detection": self._coerce_checkbox(request.POST.get("enable_os_detection")),
            "enable_traceroute": self._coerce_checkbox(request.POST.get("enable_traceroute")),
            "enable_dns_resolution": self._coerce_checkbox(request.POST.get("enable_dns_resolution")),
            "timing_profile": request.POST.get("timing_profile", ""),
        }
        policy = validate_scan_options(payload)
        summary = build_scan_summary(payload, policy)
        return render(
            request,
            self.template_name,
            {
                "summary": summary,
            },
        )
