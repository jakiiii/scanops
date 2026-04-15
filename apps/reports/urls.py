from django.urls import path

from apps.reports.views import (
    ReportArchiveView,
    ReportDetailView,
    ReportDownloadView,
    ReportGenerateView,
    ReportListView,
    ReportPreviewView,
    ReportPrintView,
    ReportRegenerateView,
)

app_name = "reports"


urlpatterns = [
    path("", ReportListView.as_view(), name="list"),
    path("generate/", ReportGenerateView.as_view(), name="generate"),
    path("preview/", ReportPreviewView.as_view(), name="preview"),
    path("<int:pk>/", ReportDetailView.as_view(), name="detail"),
    path("<int:pk>/print/", ReportPrintView.as_view(), name="print"),
    path("<int:pk>/download/", ReportDownloadView.as_view(), name="download"),
    path("<int:pk>/archive/", ReportArchiveView.as_view(), name="archive"),
    path("<int:pk>/regenerate/", ReportRegenerateView.as_view(), name="regenerate"),
]

