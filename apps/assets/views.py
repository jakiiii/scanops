from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.assets.forms import AssetFilterForm
from apps.assets.models import Asset, AssetChangeLog
from apps.assets.services.asset_service import (
    build_asset_detail_context,
    global_asset_changes,
    sync_assets_from_results,
)
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import create_notification
from apps.ops.models import PermissionRule
from apps.ops.rbac import CapabilityRequiredMixin, scope_queryset_for_user


class AssetListView(CapabilityRequiredMixin, ListView):
    capability_key = PermissionRule.PermissionKey.VIEW_ASSETS
    model = Asset
    template_name = "assets/list.html"
    context_object_name = "assets"
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/assets_table.html"]
        return [self.template_name]

    def get_queryset(self):
        if settings.DEBUG and not Asset.objects.exists():
            sync_assets_from_results(limit=40)

        queryset = Asset.objects.select_related("target").order_by("-updated_at")
        queryset = scope_queryset_for_user(queryset, self.request.user, ("target__owner", "target__created_by"))
        self.filter_form = AssetFilterForm(self.request.GET or None, user=self.request.user)
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            if q:
                queryset = queryset.filter(
                    Q(name__icontains=q)
                    | Q(hostname__icontains=q)
                    | Q(ip_address__icontains=q)
                    | Q(canonical_identifier__icontains=q)
                )
            if cleaned.get("target"):
                queryset = queryset.filter(target=cleaned["target"])
            if cleaned.get("owner_name"):
                queryset = queryset.filter(owner_name__icontains=cleaned["owner_name"])
            if cleaned.get("risk_level"):
                queryset = queryset.filter(risk_level=cleaned["risk_level"])
            if cleaned.get("status"):
                queryset = queryset.filter(status=cleaned["status"])
            if cleaned.get("last_seen_from"):
                queryset = queryset.filter(last_seen_at__date__gte=cleaned["last_seen_from"])
            if cleaned.get("last_seen_to"):
                queryset = queryset.filter(last_seen_at__date__lte=cleaned["last_seen_to"])
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        source = scope_queryset_for_user(
            Asset.objects.all(),
            self.request.user,
            ("target__owner", "target__created_by"),
        )
        context["summary"] = {
            "total": source.count(),
            "critical": source.filter(risk_level=Asset.RiskLevel.CRITICAL).count(),
            "high": source.filter(risk_level=Asset.RiskLevel.HIGH).count(),
            "monitoring": source.filter(status=Asset.Status.MONITORING).count(),
        }
        context["breadcrumbs"] = [
            {"label": "Assets", "url": ""},
        ]
        return context


class AssetDetailView(CapabilityRequiredMixin, DetailView):
    capability_key = PermissionRule.PermissionKey.VIEW_ASSETS
    model = Asset
    template_name = "assets/detail.html"
    context_object_name = "asset"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_asset_detail_context(self.object))
        context["tab"] = self.request.GET.get("tab", "overview")
        context["breadcrumbs"] = [
            {"label": "Assets", "url": reverse("assets:list")},
            {"label": self.object.name, "url": ""},
        ]
        return context

    def get_queryset(self):
        queryset = Asset.objects.select_related("target")
        return scope_queryset_for_user(queryset, self.request.user, ("target__owner", "target__created_by"))


class AssetChangeHistoryView(CapabilityRequiredMixin, TemplateView):
    capability_key = PermissionRule.PermissionKey.VIEW_ASSETS
    template_name = "assets/change_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        asset = None
        pk = self.kwargs.get("pk")
        if pk:
            scoped_assets = scope_queryset_for_user(
                Asset.objects.all(),
                self.request.user,
                ("target__owner", "target__created_by"),
            )
            asset = get_object_or_404(scoped_assets, pk=pk)
            changes = asset.change_logs.select_related("previous_snapshot", "current_snapshot").order_by("-created_at")
            context["breadcrumbs"] = [
                {"label": "Assets", "url": reverse("assets:list")},
                {"label": asset.name, "url": reverse("assets:detail", kwargs={"pk": asset.pk})},
                {"label": "Change History", "url": ""},
            ]
        else:
            changes = scope_queryset_for_user(
                global_asset_changes(),
                self.request.user,
                ("asset__target__owner", "asset__target__created_by"),
            )
            context["breadcrumbs"] = [
                {"label": "Assets", "url": reverse("assets:list")},
                {"label": "Change History", "url": ""},
            ]

        q = (self.request.GET.get("q") or "").strip()
        change_type = (self.request.GET.get("change_type") or "").strip()
        if q:
            changes = changes.filter(
                Q(asset__name__icontains=q)
                | Q(summary__icontains=q)
            )
        if change_type:
            changes = changes.filter(change_type=change_type)

        summary_source = changes
        context["asset"] = asset
        context["changes"] = summary_source[:200]
        context["summary"] = {
            "total": summary_source.count(),
            "ports_added": summary_source.filter(change_type=AssetChangeLog.ChangeType.PORTS_ADDED).count(),
            "ports_removed": summary_source.filter(change_type=AssetChangeLog.ChangeType.PORTS_REMOVED).count(),
            "service_or_os": summary_source.filter(
                change_type__in=[
                    AssetChangeLog.ChangeType.SERVICE_CHANGED,
                    AssetChangeLog.ChangeType.OS_CHANGED,
                ]
            ).count(),
        }
        context["change_type_choices"] = AssetChangeLog.ChangeType.choices
        return context


class AssetChangesPartialView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.VIEW_ASSETS

    def get(self, request, pk: int):
        scoped_assets = scope_queryset_for_user(Asset.objects.all(), request.user, ("target__owner", "target__created_by"))
        asset = get_object_or_404(scoped_assets, pk=pk)
        changes = asset.change_logs.select_related("previous_snapshot", "current_snapshot").order_by("-created_at")[:50]
        return render(request, "partials/asset_changes_timeline.html", {"asset": asset, "changes": changes})


class AssetSyncView(CapabilityRequiredMixin, View):
    capability_key = PermissionRule.PermissionKey.MANAGE_ASSETS

    def post(self, request):
        count = sync_assets_from_results(limit=100)
        create_notification(
            recipient=request.user,
            title="Asset sync completed",
            message=f"Asset inventory synchronized from {count} recent scan results.",
            notification_type=Notification.NotificationType.ASSET_CHANGED,
            severity=Notification.Severity.INFO,
            action_url=reverse("assets:list"),
            metadata={"synced_count": count},
        )
        messages.success(request, f"Synchronized {count} assets from scan results.")
        if request.headers.get("HX-Request"):
            return render(request, "partials/messages.html")
        return redirect("assets:list")
