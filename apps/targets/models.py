from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.services.target_validation import normalize_target_value

class TargetQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Target.Status.ACTIVE)


class Target(models.Model):
    class TargetType(models.TextChoices):
        IP = "ip", "IP"
        DOMAIN = "domain", "Domain"
        CIDR = "cidr", "CIDR"
        IPV6 = "ipv6", "IPv6"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        RESTRICTED = "restricted", "Restricted"

    name = models.CharField(max_length=120, blank=True)
    target_value = models.CharField(max_length=255)
    normalized_value = models.CharField(max_length=255, editable=False, db_index=True)
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    notes = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_targets",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_targets",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TargetQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["target_type", "normalized_value"],
                name="uniq_target_target_type_normalized_value",
            )
        ]
        indexes = [
            models.Index(fields=["target_type", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.name or self.target_value

    def save(self, *args, **kwargs):
        if self.target_value:
            self.normalized_value = normalize_target_value(self.target_type, self.target_value)
        super().save(*args, **kwargs)
