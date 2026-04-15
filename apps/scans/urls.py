from django.urls import path

from apps.scans.history_views import (
    ArchivedHistoryView,
    HistoryArchiveExecutionView,
    HistoryCloneSettingsView,
    HistoryCompareRedirectView,
    HistoryDeleteExecutionView,
    HistoryRerunView,
    HistoryRestoreExecutionView,
    MyHistoryView,
    ScanHistoryView,
)
from apps.scans.results_views import (
    HostDetailView,
    ResultPortsPartialView,
    ScanParsedOutputView,
    ScanRawOutputView,
    ScanResultCompareView,
    ScanResultDetailView,
    ScanResultListView,
)
from apps.scans.running_views import (
    ExecutionCancelView,
    ExecutionRetryView,
    MonitorLogPartialView,
    MonitorStatusPartialView,
    RunningScanListView,
    ScanMonitorDetailView,
    ScanQueueView,
)
from apps.scans.views import ScanPreviewView, ScanRequestCreateView

app_name = "scans"


urlpatterns = [
    # phase 1
    path("new/", ScanRequestCreateView.as_view(), name="new"),
    path("preview/", ScanPreviewView.as_view(), name="preview"),

    # running
    path("running/", RunningScanListView.as_view(), name="running"),
    path("queue/", ScanQueueView.as_view(), name="queue"),
    path("monitor/<int:pk>/", ScanMonitorDetailView.as_view(), name="monitor"),
    path("monitor/<int:pk>/status/", MonitorStatusPartialView.as_view(), name="monitor-status"),
    path("monitor/<int:pk>/logs/", MonitorLogPartialView.as_view(), name="monitor-logs"),
    path("execution/<int:pk>/cancel/", ExecutionCancelView.as_view(), name="execution-cancel"),
    path("execution/<int:pk>/retry/", ExecutionRetryView.as_view(), name="execution-retry"),

    # results
    path("results/", ScanResultListView.as_view(), name="results"),
    path("results/<int:pk>/", ScanResultDetailView.as_view(), name="result-detail"),
    path("results/<int:pk>/raw/", ScanRawOutputView.as_view(), name="result-raw"),
    path("results/<int:pk>/parsed/", ScanParsedOutputView.as_view(), name="result-parsed"),
    path("results/<int:pk>/ports/", ResultPortsPartialView.as_view(), name="result-ports"),
    path("results/compare/", ScanResultCompareView.as_view(), name="result-compare"),
    path("results/<int:pk>/compare/", ScanResultCompareView.as_view(), name="result-compare-current"),
    path("hosts/<int:pk>/", HostDetailView.as_view(), name="host-detail"),

    # history
    path("history/", ScanHistoryView.as_view(), name="history"),
    path("history/me/", MyHistoryView.as_view(), name="history-me"),
    path("history/archived/", ArchivedHistoryView.as_view(), name="history-archived"),
    path("history/<int:pk>/archive/", HistoryArchiveExecutionView.as_view(), name="history-archive"),
    path("history/<int:pk>/restore/", HistoryRestoreExecutionView.as_view(), name="history-restore"),
    path("history/<int:pk>/delete/", HistoryDeleteExecutionView.as_view(), name="history-delete"),
    path("history/<int:pk>/clone/", HistoryCloneSettingsView.as_view(), name="history-clone"),
    path("history/<int:pk>/rerun/", HistoryRerunView.as_view(), name="history-rerun"),
    path("history/<int:pk>/compare/", HistoryCompareRedirectView.as_view(), name="history-compare"),
]
