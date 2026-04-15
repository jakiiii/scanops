from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.notifications.forms import NotificationFilterForm
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import (
    bulk_mark_read,
    bulk_mark_unread,
    mark_as_read,
    mark_as_unread,
)


def _redirect_back(request, fallback: str):
    return redirect(request.META.get("HTTP_REFERER") or fallback)


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/notifications_list.html"]
        return [self.template_name]

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user).select_related(
            "related_execution",
            "related_result",
            "related_schedule",
            "related_asset",
        )
        self.filter_form = NotificationFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            if q:
                queryset = queryset.filter(
                    Q(title__icontains=q)
                    | Q(message__icontains=q)
                    | Q(related_execution__execution_id__icontains=q)
                    | Q(related_asset__name__icontains=q)
                )
            if cleaned.get("is_read") == "true":
                queryset = queryset.filter(is_read=True)
            if cleaned.get("is_read") == "false":
                queryset = queryset.filter(is_read=False)
            if cleaned.get("notification_type"):
                queryset = queryset.filter(notification_type=cleaned["notification_type"])
            if cleaned.get("severity"):
                queryset = queryset.filter(severity=cleaned["severity"])
            if cleaned.get("date_from"):
                queryset = queryset.filter(created_at__date__gte=cleaned["date_from"])
            if cleaned.get("date_to"):
                queryset = queryset.filter(created_at__date__lte=cleaned["date_to"])
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        source = Notification.objects.filter(recipient=self.request.user)
        context["summary"] = {
            "total": source.count(),
            "unread": source.filter(is_read=False).count(),
            "critical": source.filter(severity=Notification.Severity.ERROR, is_read=False).count(),
        }
        context["breadcrumbs"] = [
            {"label": "Notifications", "url": ""},
        ]
        return context


class NotificationDetailView(LoginRequiredMixin, DetailView):
    model = Notification
    template_name = "notifications/detail.html"
    context_object_name = "notification"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related(
            "related_execution",
            "related_result",
            "related_schedule",
            "related_asset",
        )

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        mark_as_read(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Notifications", "url": reverse("notifications:list")},
            {"label": "Detail", "url": ""},
        ]
        return context


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        mark_as_read(notification)
        return _redirect_back(request, reverse("notifications:list"))


class NotificationMarkUnreadView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        mark_as_unread(notification)
        return _redirect_back(request, reverse("notifications:list"))


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        count = bulk_mark_read(Notification.objects.filter(recipient=request.user, is_read=False))
        messages.success(request, f"Marked {count} notifications as read.")
        return _redirect_back(request, reverse("notifications:list"))


class NotificationBulkActionView(LoginRequiredMixin, View):
    def post(self, request):
        ids = [int(x) for x in request.POST.getlist("notification_ids") if x.isdigit()]
        action = request.POST.get("action")
        queryset = Notification.objects.filter(recipient=request.user, pk__in=ids)
        if action == "read":
            count = bulk_mark_read(queryset)
            messages.success(request, f"Marked {count} notifications as read.")
        elif action == "unread":
            count = bulk_mark_unread(queryset)
            messages.info(request, f"Marked {count} notifications as unread.")
        return _redirect_back(request, reverse("notifications:list"))

