from __future__ import annotations

from django.conf import settings
from django.db import models


class ScanSchedule(models.Model):
    class ScanType(models.TextChoices):
        HOST_DISCOVERY = "host_discovery", "Host Discovery"
        QUICK_TCP = "quick_tcp", "Quick TCP"
        TOP_100 = "top_100", "Top 100"
        TOP_1000 = "top_1000", "Top 1000"
        SERVICE_DETECTION = "service_detection", "Service Detection"
        SAFE_BASIC = "safe_basic", "Safe Basic"

    class TimingProfile(models.TextChoices):
        NORMAL = "normal", "Normal"
        BALANCED = "balanced", "Balanced"
        FAST = "fast", "Fast"

    class ScheduleType(models.TextChoices):
        ONE_TIME = "one_time", "One Time"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=160)
    target = models.ForeignKey("targets.Target", related_name="scan_schedules", on_delete=models.PROTECT)
    profile = models.ForeignKey(
        "scans.ScanProfile",
        related_name="scan_schedules",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    scan_type = models.CharField(max_length=32, choices=ScanType.choices, default=ScanType.SAFE_BASIC)
    port_input = models.CharField(max_length=255, blank=True, default="")
    enable_host_discovery = models.BooleanField(default=True)
    enable_service_detection = models.BooleanField(default=True)
    enable_version_detection = models.BooleanField(default=False)
    enable_os_detection = models.BooleanField(default=False)
    enable_traceroute = models.BooleanField(default=False)
    enable_dns_resolution = models.BooleanField(default=True)
    timing_profile = models.CharField(max_length=16, choices=TimingProfile.choices, default=TimingProfile.NORMAL)
    schedule_type = models.CharField(max_length=16, choices=ScheduleType.choices, default=ScheduleType.DAILY)
    recurrence_rule = models.CharField(max_length=255, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    last_run_at = models.DateTimeField(blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    notification_enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_scan_schedules",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["is_enabled", "next_run_at"]),
            models.Index(fields=["schedule_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return self.name


class ScheduleRunLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        TRIGGERED = "triggered", "Triggered"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    schedule = models.ForeignKey(ScanSchedule, related_name="run_logs", on_delete=models.CASCADE)
    execution = models.ForeignKey(
        "scans.ScanExecution",
        related_name="schedule_run_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    run_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True)
    generated_report = models.ForeignKey(
        "reports.GeneratedReport",
        related_name="schedule_run_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-run_at",)
        indexes = [
            models.Index(fields=["status", "run_at"]),
            models.Index(fields=["schedule", "run_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.schedule.name} @ {self.run_at:%Y-%m-%d %H:%M:%S}"

