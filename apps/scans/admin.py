from django.contrib import admin

from apps.scans.models import ScanEventLog, ScanExecution, ScanPortResult, ScanProfile, ScanRequest, ScanResult


@admin.register(ScanProfile)
class ScanProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "scan_type", "timing_profile", "is_system", "is_active", "updated_at")
    list_filter = ("scan_type", "timing_profile", "is_system", "is_active")
    search_fields = ("name", "description")
    ordering = ("is_system", "name")


@admin.register(ScanRequest)
class ScanRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target",
        "scan_type",
        "timing_profile",
        "status",
        "requested_by",
        "requested_at",
    )
    list_filter = ("status", "scan_type", "timing_profile", "requested_at")
    search_fields = ("target__target_value", "notes", "requested_by__username")
    ordering = ("-requested_at",)
    autocomplete_fields = ("target", "profile", "requested_by")


@admin.register(ScanExecution)
class ScanExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "execution_id",
        "scan_request",
        "status",
        "queue_status",
        "progress_percent",
        "worker_name",
        "is_archived",
        "created_at",
    )
    list_filter = ("status", "queue_status", "is_archived", "created_at")
    search_fields = ("execution_id", "scan_request__target__target_value", "worker_name")
    ordering = ("-created_at",)
    autocomplete_fields = ("scan_request",)


class ScanPortResultInline(admin.TabularInline):
    model = ScanPortResult
    extra = 0
    fields = ("port", "protocol", "state", "service_name", "service_version", "risk_level")
    show_change_link = True


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "execution",
        "target_snapshot",
        "host_status",
        "total_open_ports",
        "total_services_detected",
        "generated_at",
    )
    list_filter = ("host_status", "generated_at")
    search_fields = ("execution__execution_id", "target_snapshot", "os_guess")
    ordering = ("-generated_at",)
    autocomplete_fields = ("execution",)
    inlines = [ScanPortResultInline]


@admin.register(ScanPortResult)
class ScanPortResultAdmin(admin.ModelAdmin):
    list_display = (
        "result",
        "port",
        "protocol",
        "state",
        "service_name",
        "risk_level",
    )
    list_filter = ("protocol", "state", "risk_level")
    search_fields = ("result__execution__execution_id", "service_name", "service_version")
    ordering = ("result", "port")
    autocomplete_fields = ("result",)


@admin.register(ScanEventLog)
class ScanEventLogAdmin(admin.ModelAdmin):
    list_display = ("execution", "event_type", "message", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("execution__execution_id", "message")
    ordering = ("-created_at",)
    autocomplete_fields = ("execution",)
