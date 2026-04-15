from django.contrib import admin

from apps.assets.models import Asset, AssetChangeLog, AssetSnapshot


class AssetSnapshotInline(admin.TabularInline):
    model = AssetSnapshot
    extra = 0
    fields = ("created_at", "hostname", "ip_address", "operating_system", "source_result")
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "ip_address",
        "operating_system",
        "risk_score",
        "risk_level",
        "status",
        "owner_name",
        "last_scanned_at",
    )
    list_filter = ("risk_level", "status", "last_scanned_at")
    search_fields = ("name", "hostname", "ip_address", "canonical_identifier", "owner_name")
    ordering = ("-updated_at",)
    autocomplete_fields = ("target",)
    inlines = [AssetSnapshotInline]


@admin.register(AssetSnapshot)
class AssetSnapshotAdmin(admin.ModelAdmin):
    list_display = ("asset", "created_at", "hostname", "ip_address", "operating_system", "source_result")
    list_filter = ("created_at",)
    search_fields = ("asset__name", "hostname", "ip_address")
    ordering = ("-created_at",)
    autocomplete_fields = ("asset", "source_result")


@admin.register(AssetChangeLog)
class AssetChangeLogAdmin(admin.ModelAdmin):
    list_display = ("asset", "change_type", "summary", "created_at")
    list_filter = ("change_type", "created_at")
    search_fields = ("asset__name", "summary")
    ordering = ("-created_at",)
    autocomplete_fields = ("asset", "previous_snapshot", "current_snapshot")

