from django.urls import path
from django.views.generic import RedirectView

from apps.ops.views import (
    AdminProfileDeleteView,
    AdminProfileDisableView,
    AdminProfilePublishView,
    AdminScanProfileManagementView,
    AllowedTargetsSettingsView,
    ExportSettingsView,
    GeneralSettingsView,
    NotificationSettingsView,
    QueueWorkerStatusView,
    RoleMatrixPartialView,
    RolePermissionToggleView,
    RolePermissionView,
    ScanPolicySettingsView,
    SystemHealthAlertsPartialView,
    SystemHealthCardsPartialView,
    SystemHealthView,
    ThemeSettingsView,
    UserCreateView,
    UserFlagPasswordResetView,
    UserListView,
    UserToggleActiveView,
    UserUpdateView,
)

app_name = "ops"


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="ops:settings-general", permanent=False), name="home"),
    path("settings/", RedirectView.as_view(pattern_name="ops:settings-general", permanent=False), name="settings"),
    path("settings/general/", GeneralSettingsView.as_view(), name="settings-general"),
    path("settings/scan-policy/", ScanPolicySettingsView.as_view(), name="settings-scan-policy"),
    path("settings/allowed-targets/", AllowedTargetsSettingsView.as_view(), name="settings-allowed-targets"),
    path("settings/notifications/", NotificationSettingsView.as_view(), name="settings-notifications"),
    path("settings/exports/", ExportSettingsView.as_view(), name="settings-exports"),
    path("settings/theme/", ThemeSettingsView.as_view(), name="settings-theme"),
    path("users/", UserListView.as_view(), name="users-list"),
    path("users/create/", UserCreateView.as_view(), name="users-create"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="users-edit"),
    path("users/<int:pk>/toggle-active/", UserToggleActiveView.as_view(), name="users-toggle-active"),
    path("users/<int:pk>/flag-password-reset/", UserFlagPasswordResetView.as_view(), name="users-flag-password-reset"),
    path("roles/", RolePermissionView.as_view(), name="roles"),
    path("roles/matrix/", RoleMatrixPartialView.as_view(), name="roles-matrix"),
    path("roles/toggle/", RolePermissionToggleView.as_view(), name="roles-toggle"),
    path("profiles/", AdminScanProfileManagementView.as_view(), name="admin-profiles"),
    path("profiles/<int:pk>/publish/", AdminProfilePublishView.as_view(), name="admin-profiles-publish"),
    path("profiles/<int:pk>/disable/", AdminProfileDisableView.as_view(), name="admin-profiles-disable"),
    path("profiles/<int:pk>/delete/", AdminProfileDeleteView.as_view(), name="admin-profiles-delete"),
    path("health/queue-workers/", QueueWorkerStatusView.as_view(), name="health-queue-workers"),
    path("health/system/", SystemHealthView.as_view(), name="health-system"),
    path("health/system/cards/", SystemHealthCardsPartialView.as_view(), name="health-system-cards"),
    path("health/system/alerts/", SystemHealthAlertsPartialView.as_view(), name="health-system-alerts"),
]
