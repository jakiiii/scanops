from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.notifications.services.notification_service import create_notification
from apps.schedules.forms import ScheduleFilterForm, ScheduleForm
from apps.schedules.models import ScanSchedule, ScheduleRunLog
from apps.schedules.services.schedule_service import apply_next_run, build_schedule_summary, trigger_schedule_run


def _redirect_back(request, fallback: str):
    return redirect(request.META.get("HTTP_REFERER") or fallback)


class ScheduleListView(LoginRequiredMixin, ListView):
    model = ScanSchedule
    template_name = "schedules/list.html"
    context_object_name = "schedules"
    paginate_by = 15

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["partials/schedules_table.html"]
        return [self.template_name]

    def get_queryset(self):
        queryset = ScanSchedule.objects.select_related("target", "profile", "created_by").order_by("-created_at")
        self.filter_form = ScheduleFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            cleaned = self.filter_form.cleaned_data
            q = (cleaned.get("q") or "").strip()
            if q:
                queryset = queryset.filter(
                    Q(name__icontains=q)
                    | Q(target__target_value__icontains=q)
                    | Q(profile__name__icontains=q)
                    | Q(created_by__username__icontains=q)
                )
            if cleaned.get("schedule_type"):
                queryset = queryset.filter(schedule_type=cleaned["schedule_type"])
            if cleaned.get("enabled") == "true":
                queryset = queryset.filter(is_enabled=True)
            if cleaned.get("enabled") == "false":
                queryset = queryset.filter(is_enabled=False)
            if cleaned.get("owner"):
                queryset = queryset.filter(created_by=cleaned["owner"])
            if cleaned.get("next_run_from"):
                queryset = queryset.filter(next_run_at__date__gte=cleaned["next_run_from"])
            if cleaned.get("next_run_to"):
                queryset = queryset.filter(next_run_at__date__lte=cleaned["next_run_to"])
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        now = timezone.now()
        due_soon = now + timedelta(hours=24)
        source = ScanSchedule.objects.all()
        context["summary"] = {
            "total": source.count(),
            "active": source.filter(is_enabled=True).count(),
            "paused": source.filter(is_enabled=False).count(),
            "due_soon": source.filter(is_enabled=True, next_run_at__isnull=False, next_run_at__lte=due_soon).count(),
        }
        context["breadcrumbs"] = [
            {"label": "Schedule", "url": ""},
        ]
        return context


class ScheduleCreateView(LoginRequiredMixin, CreateView):
    model = ScanSchedule
    form_class = ScheduleForm
    template_name = "schedules/form.html"

    def form_valid(self, form):
        self.object: ScanSchedule = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.save()
        apply_next_run(self.object)
        create_notification(
            recipient=self.request.user,
            title=f"Schedule created: {self.object.name}",
            message=f"New schedule for {self.object.target.target_value} created.",
            notification_type="schedule_triggered",
            severity="success",
            related_schedule=self.object,
            action_url=reverse("schedules:edit", kwargs={"pk": self.object.pk}),
        )
        messages.success(self.request, "Schedule created successfully.")
        return redirect("schedules:edit", pk=self.object.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        schedule_summary = {}
        if form is not None and form.is_bound and form.is_valid():
            temp_schedule = ScanSchedule(**form.cleaned_data)
            temp_schedule.next_run_at = None
            schedule_summary = build_schedule_summary(temp_schedule)
        context["mode"] = "create"
        context["schedule_summary"] = schedule_summary
        context["breadcrumbs"] = [
            {"label": "Schedule", "url": reverse("schedules:list")},
            {"label": "Create", "url": ""},
        ]
        return context


class ScheduleUpdateView(LoginRequiredMixin, UpdateView):
    model = ScanSchedule
    form_class = ScheduleForm
    template_name = "schedules/form.html"
    context_object_name = "schedule"

    def form_valid(self, form):
        self.object = form.save()
        apply_next_run(self.object)
        if self.object.created_by:
            create_notification(
                recipient=self.object.created_by,
                title=f"Schedule updated: {self.object.name}",
                message=f"Schedule configuration was updated by {self.request.user.username}.",
                notification_type="schedule_triggered",
                severity="info",
                related_schedule=self.object,
                action_url=reverse("schedules:edit", kwargs={"pk": self.object.pk}),
            )
        messages.success(self.request, "Schedule updated.")
        return redirect("schedules:edit", pk=self.object.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        if form is not None and form.is_bound and form.is_valid():
            temp_schedule = ScanSchedule(**form.cleaned_data)
            temp_schedule.next_run_at = None
            schedule_summary = build_schedule_summary(temp_schedule)
        else:
            schedule_summary = build_schedule_summary(self.object)
        context["mode"] = "edit"
        context["schedule_summary"] = schedule_summary
        context["breadcrumbs"] = [
            {"label": "Schedule", "url": reverse("schedules:list")},
            {"label": self.object.name, "url": ""},
        ]
        return context


class SchedulePreviewView(LoginRequiredMixin, View):
    def post(self, request):
        form = ScheduleForm(request.POST)
        if form.is_valid():
            temp_schedule = ScanSchedule(**form.cleaned_data)
            temp_schedule.next_run_at = None
            summary = build_schedule_summary(temp_schedule)
            return render(request, "partials/schedule_summary.html", {"summary": summary, "errors": {}})
        return render(request, "partials/schedule_summary.html", {"summary": {}, "errors": form.errors})


class ScheduleRunNowView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        schedule = get_object_or_404(ScanSchedule, pk=pk)
        log = trigger_schedule_run(schedule, user=request.user)
        if log.status == ScheduleRunLog.Status.FAILED:
            messages.error(request, log.message)
        elif log.status == ScheduleRunLog.Status.SKIPPED:
            messages.warning(request, log.message)
        else:
            messages.success(request, log.message)
        return _redirect_back(request, reverse("schedules:list"))


class ScheduleToggleView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        schedule = get_object_or_404(ScanSchedule, pk=pk)
        schedule.is_enabled = not schedule.is_enabled
        if not schedule.is_enabled:
            schedule.next_run_at = None
        else:
            apply_next_run(schedule, save=False)
        schedule.save(update_fields=["is_enabled", "next_run_at", "updated_at"])
        messages.info(request, f"{schedule.name} is now {'enabled' if schedule.is_enabled else 'disabled'}.")
        return _redirect_back(request, reverse("schedules:list"))


class ScheduleDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        schedule = get_object_or_404(ScanSchedule, pk=pk)
        name = schedule.name
        schedule.delete()
        messages.warning(request, f"Deleted schedule: {name}")
        return _redirect_back(request, reverse("schedules:list"))


class ScheduleHistoryView(LoginRequiredMixin, ListView):
    model = ScheduleRunLog
    template_name = "schedules/history.html"
    context_object_name = "run_logs"
    paginate_by = 20

    def get_queryset(self):
        queryset = ScheduleRunLog.objects.select_related("schedule", "execution", "generated_report").order_by("-run_at")
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        schedule_id = (self.request.GET.get("schedule") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(schedule__name__icontains=q)
                | Q(message__icontains=q)
                | Q(execution__execution_id__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if schedule_id.isdigit():
            queryset = queryset.filter(schedule_id=int(schedule_id))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = ScheduleRunLog.Status.choices
        context["schedule_choices"] = ScanSchedule.objects.order_by("name")
        context["breadcrumbs"] = [
            {"label": "Schedule", "url": reverse("schedules:list")},
            {"label": "History", "url": ""},
        ]
        return context
