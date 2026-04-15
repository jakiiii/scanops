from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html

from apps.accounts.audit import AuditLogAdminMixin
from apps.accounts.models import User, UserLogs

from apps.accounts.forms import UserAdminCreationForm, UserAdminChangeForm


@admin.register(User)
class UserAdmin(AuditLogAdminMixin, DjangoUserAdmin):
    add_form = UserAdminCreationForm
    form = UserAdminChangeForm
    model = User

    list_display = ['username', 'first_name', 'last_name', 'email', 'is_superuser', 'is_staff', 'is_administrator', 'is_operator', 'is_active']
    list_filter = ['is_superuser', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['last_login', 'date_joined']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_superuser', 'is_staff', 'is_administrator', 'is_operator',)}),
        ('Others', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_active', 'is_superuser', 'is_staff', 'is_administrator', 'is_operator')}
         ),
    )


admin.site.unregister(Group)


@admin.register(UserLogs)
class UserLogsAdmin(admin.ModelAdmin):
    list_display = [
        "username_display",
        "action_type_badge",
        "success_badge",
        "ip_address",
        "description",
        "action_datetime",
        "path_display",
    ]
    list_filter = ["action_type", "is_success", "action_datetime"]
    search_fields = [
        "user__username",
        "user__email",
        "username_snapshot",
        "ip_address",
        "description",
        "path",
        "target_model",
        "object_repr",
    ]
    readonly_fields = [
        "user",
        "username_snapshot",
        "action_type_badge",
        "success_badge",
        "description",
        "ip_address",
        "request_method",
        "path",
        "device",
        "operating_system",
        "browser",
        "user_agent",
        "target_model",
        "target_object_id",
        "object_repr",
        "action_datetime",
    ]
    fieldsets = (
        ("Event", {
            "fields": (
                ("user", "username_snapshot"),
                ("action_type_badge", "success_badge"),
                "description",
                "action_datetime",
            ),
        }),
        ("Request Context", {
            "fields": (
                ("ip_address", "request_method"),
                "path",
                ("browser", "operating_system", "device"),
                "user_agent",
            ),
        }),
        ("Target Object", {
            "fields": (
                ("target_model", "target_object_id"),
                "object_repr",
            ),
            "classes": ("collapse",),
        }),
    )
    date_hierarchy = "action_datetime"
    ordering = ("-action_datetime", "-id")
    list_select_related = ("user",)
    list_per_page = 25
    actions = None

    def username_display(self, obj):
        return obj.username_snapshot or obj.user

    username_display.short_description = "Username"
    username_display.admin_order_field = "username_snapshot"

    @staticmethod
    def _badge(label, tone):
        return format_html('<span class="audit-badge audit-badge--{}">{}</span>', tone, label)

    def action_type_badge(self, obj):
        tone_map = {
            UserLogs.ActionType.LOGIN: "info",
            UserLogs.ActionType.LOGOUT: "warning",
            UserLogs.ActionType.LOGIN_FAILED: "danger",
            UserLogs.ActionType.ADMIN_CREATE: "success",
            UserLogs.ActionType.ADMIN_UPDATE: "info",
            UserLogs.ActionType.ADMIN_DELETE: "danger",
        }
        label = obj.get_action_type_display() or obj.action_type
        return self._badge(label, tone_map.get(obj.action_type, "info"))

    action_type_badge.short_description = "Action"
    action_type_badge.admin_order_field = "action_type"

    def success_badge(self, obj):
        return self._badge("Success" if obj.is_success else "Failed", "success" if obj.is_success else "danger")

    success_badge.short_description = "Result"
    success_badge.admin_order_field = "is_success"

    def path_display(self, obj):
        return format_html("<code>{}</code>", obj.path or "/")

    path_display.short_description = "Path"
    path_display.admin_order_field = "path"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.none()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def get_model_perms(self, request):
        if not self.has_module_permission(request):
            return {}
        return {"add": False, "change": False, "delete": False, "view": True}
