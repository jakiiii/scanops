from __future__ import annotations

from django.conf import settings
from django.db import models


class ReportTemplate(models.Model):
    class ReportType(models.TextChoices):
        EXECUTIVE_SUMMARY = "executive_summary", "Executive Summary"
        TECHNICAL_REPORT = "technical_report", "Technical Report"
        COMPARISON_REPORT = "comparison_report", "Comparison Report"
        PER_HOST_REPORT = "per_host_report", "Per-Host Report"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=32, choices=ReportType.choices)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("is_system", "name")

    def __str__(self) -> str:
        return self.name


class GeneratedReport(models.Model):
    class ReportType(models.TextChoices):
        EXECUTIVE_SUMMARY = "executive_summary", "Executive Summary"
        TECHNICAL_REPORT = "technical_report", "Technical Report"
        COMPARISON_REPORT = "comparison_report", "Comparison Report"
        PER_HOST_REPORT = "per_host_report", "Per-Host Report"

    class Format(models.TextChoices):
        HTML = "html", "HTML"
        PDF = "pdf", "PDF"
        JSON = "json", "JSON"
        TXT = "txt", "TXT"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        GENERATED = "generated", "Generated"
        FAILED = "failed", "Failed"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=180)
    report_type = models.CharField(max_length=32, choices=ReportType.choices)
    report_template = models.ForeignKey(
        ReportTemplate,
        related_name="generated_reports",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    source_result = models.ForeignKey(
        "scans.ScanResult",
        related_name="reports_from_result",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    source_execution = models.ForeignKey(
        "scans.ScanExecution",
        related_name="reports_from_execution",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    comparison_left_result = models.ForeignKey(
        "scans.ScanResult",
        related_name="reports_as_comparison_left",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    comparison_right_result = models.ForeignKey(
        "scans.ScanResult",
        related_name="reports_as_comparison_right",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    asset = models.ForeignKey(
        "assets.Asset",
        related_name="generated_reports",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="generated_reports",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    format = models.CharField(max_length=16, choices=Format.choices, default=Format.HTML)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.GENERATED)
    summary = models.TextField(blank=True)
    report_payload_json = models.JSONField(default=dict, blank=True)
    rendered_html = models.TextField(blank=True)
    generated_file_path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["report_type", "status", "created_at"]),
            models.Index(fields=["format", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_report_type_display()})"

