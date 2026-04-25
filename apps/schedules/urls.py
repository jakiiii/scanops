from django.urls import path

from apps.schedules.views import (
    ScheduleCreateView,
    ScheduleDeleteView,
    ScheduleDetailView,
    ScheduleHistoryView,
    ScheduleListView,
    SchedulePreviewView,
    ScheduleRunNowView,
    ScheduleToggleView,
    ScheduleUpdateView,
)

app_name = "schedules"


urlpatterns = [
    path("", ScheduleListView.as_view(), name="list"),
    path("create/", ScheduleCreateView.as_view(), name="create"),
    path("<int:pk>/", ScheduleDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ScheduleUpdateView.as_view(), name="edit"),
    path("preview/", SchedulePreviewView.as_view(), name="preview"),
    path("<int:pk>/run-now/", ScheduleRunNowView.as_view(), name="run-now"),
    path("<int:pk>/toggle/", ScheduleToggleView.as_view(), name="toggle"),
    path("<int:pk>/delete/", ScheduleDeleteView.as_view(), name="delete"),
    path("history/", ScheduleHistoryView.as_view(), name="history"),
]
