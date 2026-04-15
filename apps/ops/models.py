from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class AppSetting(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "General"
        SCAN_POLICY = "scan_policy", "Scan Policy"
        ALLOWED_TARGETS = "allowed_targets", "Allowed Targets"
        NOTIFICATIONS = "notifications", "Notifications"
        EXPORTS = "exports", "Exports"
        UI = "ui", "Theme & UI"

    key = models.CharField(max_length=120, unique=True)
    value_text = models.TextField(blank=True, default="")
    value_json = models.JSONField(default=dict, blank=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    label = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="updated_app_settings",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("category", "key")
        indexes = [
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.category}:{self.key}"


class Role(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("is_system", "name")

    def __str__(self) -> str:
        return self.name


class PermissionRule(models.Model):
    class PermissionKey(models.TextChoices):
        MANAGE_USERS = "manage_users", "Manage Users"
        MANAGE_SETTINGS = "manage_settings", "Manage Settings"
        MANAGE_PROFILES = "manage_profiles", "Manage Profiles"
        MANAGE_SCHEDULES = "manage_schedules", "Manage Schedules"
        VIEW_SYSTEM_HEALTH = "view_system_health", "View System Health"
        RUN_SCANS = "run_scans", "Run Scans"
        ARCHIVE_RESULTS = "archive_results", "Archive Results"
        GENERATE_REPORTS = "generate_reports", "Generate Reports"

    role = models.ForeignKey(Role, related_name="permission_rules", on_delete=models.CASCADE)
    permission_key = models.CharField(max_length=64, choices=PermissionKey.choices)
    is_allowed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("role__name", "permission_key")
        constraints = [
            models.UniqueConstraint(fields=["role", "permission_key"], name="uniq_role_permission_rule"),
        ]

    def __str__(self) -> str:
        return f"{self.role.slug}:{self.permission_key}={self.is_allowed}"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE)
    display_name = models.CharField(max_length=160, blank=True, default="")
    role = models.ForeignKey(Role, related_name="user_profiles", on_delete=models.SET_NULL, blank=True, null=True)
    is_approved = models.BooleanField(default=True)
    is_internal_operator = models.BooleanField(default=True)
    allowed_workspace = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    force_password_reset = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("user__username",)

    def __str__(self) -> str:
        return self.display_name or self.user.get_full_name() or self.user.username


class WorkerStatusSnapshot(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        DEGRADED = "degraded", "Degraded"
        OFFLINE = "offline", "Offline"

    worker_name = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ONLINE)
    active_jobs_count = models.PositiveIntegerField(default=0)
    queued_jobs_count = models.PositiveIntegerField(default=0)
    failed_jobs_count = models.PositiveIntegerField(default=0)
    heartbeat_at = models.DateTimeField(default=timezone.now)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "worker_name")
        indexes = [
            models.Index(fields=["worker_name", "created_at"]),
            models.Index(fields=["status", "heartbeat_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.worker_name} ({self.status})"


class SystemHealthSnapshot(models.Model):
    class ServiceName(models.TextChoices):
        DJANGO_APP = "django_app", "Django App"
        DATABASE = "database", "Database"
        NMAP_BINARY = "nmap_binary", "Nmap Binary"
        QUEUE_SERVICE = "queue_service", "Queue Service"
        SCHEDULER = "scheduler", "Scheduler"
        STORAGE = "storage", "Storage"

    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        UNKNOWN = "unknown", "Unknown"

    service_name = models.CharField(max_length=64, choices=ServiceName.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNKNOWN)
    summary = models.TextField(blank=True, default="")
    metadata_json = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-checked_at", "-id")
        indexes = [
            models.Index(fields=["service_name", "checked_at"]),
            models.Index(fields=["status", "checked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.service_name}:{self.status}"


class AdminAuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="ops_admin_audit_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=120)
    target_id = models.CharField(max_length=64, blank=True, default="")
    summary = models.TextField()
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self) -> str:
        actor = getattr(self.actor, "username", "system")
        return f"{actor}: {self.action}"
