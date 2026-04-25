from __future__ import annotations

from django.conf import settings
from django.db import models


class Asset(models.Model):
    class RiskLevel(models.TextChoices):
        INFO = "info", "Info"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        MONITORING = "monitoring", "Monitoring"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=160)
    target = models.ForeignKey(
        "targets.Target",
        related_name="assets",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    hostname = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    canonical_identifier = models.CharField(max_length=255, unique=True, blank=True, null=True)
    operating_system = models.CharField(max_length=255, blank=True)
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, default=RiskLevel.INFO)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_assets",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    owner_name = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    last_scanned_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.MONITORING)
    current_open_ports_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["risk_level", "status"]),
            models.Index(fields=["last_scanned_at"]),
            models.Index(fields=["canonical_identifier"]),
        ]

    def __str__(self) -> str:
        return self.name


class AssetSnapshot(models.Model):
    asset = models.ForeignKey(Asset, related_name="snapshots", on_delete=models.CASCADE)
    source_result = models.ForeignKey(
        "scans.ScanResult",
        related_name="asset_snapshots",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    hostname = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    operating_system = models.CharField(max_length=255, blank=True)
    open_ports_json = models.JSONField(default=list, blank=True)
    services_json = models.JSONField(default=list, blank=True)
    raw_summary_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["asset", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Snapshot {self.asset.name} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class AssetChangeLog(models.Model):
    class ChangeType(models.TextChoices):
        PORTS_ADDED = "ports_added", "Ports Added"
        PORTS_REMOVED = "ports_removed", "Ports Removed"
        SERVICE_CHANGED = "service_changed", "Service Changed"
        OS_CHANGED = "os_changed", "OS Changed"
        ASSET_CREATED = "asset_created", "Asset Created"
        ASSET_UPDATED = "asset_updated", "Asset Updated"

    asset = models.ForeignKey(Asset, related_name="change_logs", on_delete=models.CASCADE)
    previous_snapshot = models.ForeignKey(
        AssetSnapshot,
        related_name="next_change_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    current_snapshot = models.ForeignKey(
        AssetSnapshot,
        related_name="current_change_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    change_type = models.CharField(max_length=32, choices=ChangeType.choices)
    summary = models.TextField()
    diff_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["asset", "change_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.asset.name}: {self.get_change_type_display()}"
