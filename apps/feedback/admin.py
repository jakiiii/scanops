from django.contrib import admin
from django.utils.html import format_html

from apps.feedback.models import Issue, Suggestion


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "status", "created_at", "submitted_by")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "suggestion")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("submitted_by",)


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("title", "email", "status", "created_at", "submitted_by", "attachment_link")
    list_filter = ("status", "created_at")
    search_fields = ("title", "email", "description")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "attachment_link")
    autocomplete_fields = ("submitted_by",)

    @admin.display(description="Attachment")
    def attachment_link(self, obj):
        if not obj or not obj.attachment:
            return "-"
        return format_html('<a href="{}" target="_blank" rel="noopener">View</a>', obj.attachment.url)
