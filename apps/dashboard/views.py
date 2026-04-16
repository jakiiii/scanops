from __future__ import annotations

from django.views.generic import TemplateView

from apps.dashboard.services import build_dashboard_context
from apps.ops.models import PermissionRule
from apps.ops.rbac import CapabilityRequiredMixin


class DashboardView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.VIEW_DASHBOARD
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_dashboard_context(self.request.user))
        return context
