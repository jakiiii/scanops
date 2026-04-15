from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "notification_type", "severity", "is_read", "created_at")
    list_filter = ("notification_type", "severity", "is_read", "created_at")
    search_fields = ("title", "message", "recipient__username", "related_execution__execution_id", "related_asset__name")
    ordering = ("-created_at",)
    autocomplete_fields = (
        "recipient",
        "related_execution",
        "related_result",
        "related_schedule",
        "related_asset",
    )

