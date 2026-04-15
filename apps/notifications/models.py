from __future__ import annotations

from django.conf import settings
from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        SCAN_COMPLETED = "scan_completed", "Scan Completed"
        SCAN_FAILED = "scan_failed", "Scan Failed"
        SCHEDULE_TRIGGERED = "schedule_triggered", "Schedule Triggered"
        REPORT_GENERATED = "report_generated", "Report Generated"
        ASSET_CHANGED = "asset_changed", "Asset Changed"
        POLICY_ALERT = "policy_alert", "Policy Alert"
        SYSTEM_ALERT = "system_alert", "System Alert"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=180)
    message = models.TextField()
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    is_read = models.BooleanField(default=False)
    related_execution = models.ForeignKey(
        "scans.ScanExecution",
        related_name="notifications",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    related_result = models.ForeignKey(
        "scans.ScanResult",
        related_name="notifications",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    related_schedule = models.ForeignKey(
        "schedules.ScanSchedule",
        related_name="notifications",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    related_asset = models.ForeignKey(
        "assets.Asset",
        related_name="notifications",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    action_url = models.CharField(max_length=255, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["notification_type", "severity"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} -> {self.recipient}"

