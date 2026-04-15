from django.contrib import admin

from apps.reports.models import GeneratedReport, ReportTemplate


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "report_type", "is_system", "is_active", "updated_at")
    list_filter = ("report_type", "is_system", "is_active")
    search_fields = ("name", "slug", "description")
    ordering = ("is_system", "name")


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ("title", "report_type", "format", "status", "generated_by", "created_at")
    list_filter = ("report_type", "format", "status", "created_at")
    search_fields = (
        "title",
        "summary",
        "source_execution__execution_id",
        "source_result__target_snapshot",
        "asset__name",
    )
    ordering = ("-created_at",)
    autocomplete_fields = (
        "report_template",
        "source_result",
        "source_execution",
        "comparison_left_result",
        "comparison_right_result",
        "asset",
        "generated_by",
    )

