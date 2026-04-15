from django.contrib import admin

from apps.schedules.models import ScanSchedule, ScheduleRunLog


@admin.register(ScanSchedule)
class ScanScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "target",
        "profile",
        "schedule_type",
        "next_run_at",
        "is_enabled",
        "notification_enabled",
        "created_by",
    )
    list_filter = ("schedule_type", "is_enabled", "notification_enabled", "timing_profile")
    search_fields = ("name", "target__target_value", "profile__name", "created_by__username")
    ordering = ("-created_at",)
    autocomplete_fields = ("target", "profile", "created_by")


@admin.register(ScheduleRunLog)
class ScheduleRunLogAdmin(admin.ModelAdmin):
    list_display = ("schedule", "run_at", "status", "execution", "generated_report")
    list_filter = ("status", "run_at")
    search_fields = ("schedule__name", "execution__execution_id", "message")
    ordering = ("-run_at",)
    autocomplete_fields = ("schedule", "execution", "generated_report")

