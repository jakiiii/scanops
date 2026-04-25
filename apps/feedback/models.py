from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.feedback.validators import validate_issue_attachment


class Suggestion(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=160)
    email = models.EmailField()
    suggestion = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="submitted_suggestions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["email", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Suggestion #{self.pk} by {self.name}"


def issue_attachment_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return f"feedback/issues/{uuid4().hex}{extension}"


class Issue(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        INVESTIGATING = "investigating", "Investigating"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    email = models.EmailField()
    attachment = models.FileField(
        upload_to=issue_attachment_upload_to,
        blank=True,
        null=True,
        validators=[validate_issue_attachment],
    )
    description = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="submitted_issues",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["email", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Issue #{self.pk}: {self.title}"
