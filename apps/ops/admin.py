from django.contrib import admin

from apps.ops.models import (
    AdminAuditLog,
    AppSetting,
    PermissionRule,
    Role,
    SystemHealthSnapshot,
    UserProfile,
    WorkerStatusSnapshot,
)


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "category", "label", "is_active", "updated_by", "updated_at")
    list_filter = ("category", "is_active", "updated_at")
    search_fields = ("key", "label", "description", "value_text")
    ordering = ("category", "key")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("updated_by",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_system", "updated_at")
    list_filter = ("is_system",)
    search_fields = ("name", "slug", "description")
    ordering = ("is_system", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PermissionRule)
class PermissionRuleAdmin(admin.ModelAdmin):
    list_display = ("role", "permission_key", "is_allowed", "updated_at")
    list_filter = ("permission_key", "is_allowed")
    search_fields = ("role__name", "role__slug", "permission_key")
    ordering = ("role__name", "permission_key")
    autocomplete_fields = ("role",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "role", "is_approved", "is_internal_operator", "last_seen_at")
    list_filter = ("is_approved", "is_internal_operator", "role")
    search_fields = ("user__username", "user__email", "display_name", "allowed_workspace")
    ordering = ("user__username",)
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    autocomplete_fields = ("user", "role")


@admin.register(WorkerStatusSnapshot)
class WorkerStatusSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "worker_name",
        "status",
        "active_jobs_count",
        "queued_jobs_count",
        "failed_jobs_count",
        "heartbeat_at",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("worker_name", "metadata_json")
    ordering = ("-created_at", "worker_name")


@admin.register(SystemHealthSnapshot)
class SystemHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ("service_name", "status", "summary", "checked_at", "created_at")
    list_filter = ("service_name", "status", "checked_at")
    search_fields = ("service_name", "summary", "metadata_json")
    ordering = ("-checked_at",)


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id", "summary")
    list_filter = ("action", "target_type", "created_at")
    search_fields = ("actor__username", "summary", "target_type", "target_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    autocomplete_fields = ("actor",)
