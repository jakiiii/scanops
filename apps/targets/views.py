from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from apps.ops.models import PermissionRule
from apps.ops.rbac import CapabilityRequiredMixin
from apps.ops.services import data_visibility_service
from apps.targets.forms import TargetFilterForm, TargetForm
from apps.targets.models import Target


class TargetListView(CapabilityRequiredMixin, ListView):
    capability_key = PermissionRule.PermissionKey.VIEW_TARGETS
    model = Target
    template_name = "targets/target_list.html"
    context_object_name = "targets"
    paginate_by = 10

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/targets_table.html"]
        return [self.template_name]

    def get_queryset(self):
        queryset = Target.objects.select_related("owner", "created_by").order_by("-updated_at")
        queryset = data_visibility_service.get_user_visible_targets(self.request.user, queryset=queryset)
        self.filter_form = TargetFilterForm(self.request.GET or None, user=self.request.user)
        return self.filter_form.apply(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        context["scope_label"] = "All" if data_visibility_service.user_can_view_all_data(self.request.user) else "My"
        return context


class TargetCreateView(CapabilityRequiredMixin, CreateView):
    capability_key = PermissionRule.PermissionKey.MANAGE_TARGETS
    model = Target
    form_class = TargetForm
    template_name = "targets/target_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        target = form.save(commit=False)
        target.created_by = self.request.user
        if target.owner_id is None:
            target.owner = self.request.user
        target.save()
        messages.success(self.request, "Target created successfully.")
        for warning in form.get_warnings():
            messages.warning(self.request, warning)
        self.object = target
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("targets:detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Targets", "url": reverse("targets:list")},
            {"label": "Add New", "url": ""},
        ]
        return context


class TargetDetailView(CapabilityRequiredMixin, DetailView):
    capability_key = PermissionRule.PermissionKey.VIEW_TARGETS
    model = Target
    template_name = "targets/target_detail.html"
    context_object_name = "target"

    def get_queryset(self):
        queryset = Target.objects.select_related("owner", "created_by")
        return data_visibility_service.get_user_visible_targets(self.request.user, queryset=queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.object
        context["breadcrumbs"] = [
            {"label": "Targets", "url": reverse("targets:list")},
            {"label": target.name or target.target_value, "url": ""},
        ]
        if hasattr(target, "scan_requests"):
            recent_requests = target.scan_requests.select_related("requested_by").order_by("-requested_at")
            recent_requests = data_visibility_service.get_user_visible_scan_requests(
                self.request.user,
                queryset=recent_requests,
            )
            context["recent_scan_requests"] = recent_requests[:8]
        else:
            context["recent_scan_requests"] = []
        return context
