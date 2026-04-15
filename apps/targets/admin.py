from django.contrib import admin

from apps.targets.models import Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = (
        "target_value",
        "target_type",
        "status",
        "owner",
        "created_by",
        "created_at",
    )
    list_filter = ("target_type", "status", "created_at")
    search_fields = ("name", "target_value", "normalized_value", "tags", "owner__username")
    ordering = ("-created_at",)
