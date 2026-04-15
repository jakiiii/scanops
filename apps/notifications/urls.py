from django.urls import path

from apps.notifications.views import (
    NotificationBulkActionView,
    NotificationDetailView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationMarkUnreadView,
)

app_name = "notifications"


urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("bulk-action/", NotificationBulkActionView.as_view(), name="bulk-action"),
    path("mark-all-read/", NotificationMarkAllReadView.as_view(), name="mark-all-read"),
    path("<int:pk>/", NotificationDetailView.as_view(), name="detail"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="mark-read"),
    path("<int:pk>/unread/", NotificationMarkUnreadView.as_view(), name="mark-unread"),
]

